"""MCP Server for QuantCore — exposes trading tools via the Model
Context Protocol, enabling AI assistants to interact with the
trading engine, query risk analytics, and manage strategies.

This module is used in Challenge 6 where attendees build and extend
an MCP server.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from qxm.core.engine import MatchingEngine
from qxm.core.events import EventBus
from qxm.core.models import (
    Instrument,
    InstrumentType,
    Order,
    OrderType,
    Side,
    TimeInForce,
)
from qxm.risk.portfolio import PortfolioAnalytics
from qxm.strategy.base import StrategyMeta
from qxm.utils.serializer import to_json

logger = logging.getLogger(__name__)


def create_mcp_server(
    engine: MatchingEngine,
    portfolio: PortfolioAnalytics,
    instruments: Dict[str, Instrument],
) -> Server:
    """Create and configure the QuantCore MCP server.

    Tools exposed:
    - ``submit_order`` — Submit a buy/sell order.
    - ``cancel_order`` — Cancel an open order.
    - ``get_positions`` — Query current positions.
    - ``get_risk_metrics`` — Retrieve VaR and Greeks.
    - ``get_portfolio_snapshot`` — Full portfolio summary.
    - ``list_instruments`` — Available tradeable instruments.
    - ``list_strategies`` — Registered strategy names.
    - ``get_order_book`` — Current depth for a symbol.
    """

    server = Server("quantcore-mcp")

    # -- Tool definitions ----------------------------------------------------

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="submit_order",
                description="Submit a trading order (buy or sell) to the matching engine.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Instrument symbol (e.g. AAPL)"},
                        "side": {"type": "string", "enum": ["BUY", "SELL"], "description": "Order side"},
                        "quantity": {"type": "integer", "description": "Number of shares/contracts"},
                        "price": {"type": "number", "description": "Limit price (omit for market order)"},
                        "order_type": {"type": "string", "enum": ["LIMIT", "MARKET"], "default": "LIMIT"},
                    },
                    "required": ["symbol", "side", "quantity"],
                },
            ),
            Tool(
                name="cancel_order",
                description="Cancel an open order by its ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "The order ID to cancel"},
                    },
                    "required": ["order_id"],
                },
            ),
            Tool(
                name="get_positions",
                description="Get current trading positions, optionally filtered by client.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "Filter by client ID (optional)"},
                    },
                },
            ),
            Tool(
                name="get_risk_metrics",
                description="Retrieve portfolio risk metrics including VaR, Greeks, Sharpe ratio, and max drawdown.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_portfolio_snapshot",
                description="Get a comprehensive portfolio snapshot with positions, P&L, and risk data.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="list_instruments",
                description="List all available tradeable instruments with their properties.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="list_strategies",
                description="List all registered trading strategy names.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_order_book",
                description="Get the current order book depth for a symbol.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Instrument symbol"},
                        "depth": {"type": "integer", "description": "Number of price levels (default 5)"},
                    },
                    "required": ["symbol"],
                },
            ),
        ]

    # -- Tool implementations ------------------------------------------------

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            result = _dispatch_tool(name, arguments, engine, portfolio, instruments)
            return [TextContent(type="text", text=to_json(result, pretty=True))]
        except Exception as exc:
            logger.exception("MCP tool %s failed", name)
            return [TextContent(
                type="text",
                text=to_json({"error": str(exc), "tool": name}),
            )]

    return server


def _dispatch_tool(
    name: str,
    args: Dict[str, Any],
    engine: MatchingEngine,
    portfolio: PortfolioAnalytics,
    instruments: Dict[str, Instrument],
) -> Dict[str, Any]:
    """Route tool calls to the appropriate handler."""

    if name == "submit_order":
        symbol = args["symbol"]
        if symbol not in instruments:
            return {"error": f"Unknown instrument: {symbol}"}
        order = Order(
            symbol=symbol,
            side=Side(args["side"].upper()),
            order_type=OrderType(args.get("order_type", "LIMIT").upper()),
            quantity=args["quantity"],
            price=args.get("price"),
            client_id="mcp_user",
            time_in_force=TimeInForce.GTC,
        )
        trades = engine.submit_order(order)
        return {
            "order_id": order.order_id,
            "status": order.status.value,
            "fills": [t.dict() for t in trades],
        }

    elif name == "cancel_order":
        success = engine.cancel_order(args["order_id"])
        return {
            "order_id": args["order_id"],
            "cancelled": success,
        }

    elif name == "get_positions":
        client_id = args.get("client_id")
        positions = engine.position_manager.get_positions(client_id)
        return {
            "positions": {
                sym: pos.dict() for sym, pos in positions.items()
            }
        }

    elif name == "get_risk_metrics":
        metrics = portfolio.risk_metrics()
        return metrics.dict()

    elif name == "get_portfolio_snapshot":
        snap = portfolio.snapshot()
        return snap.dict()

    elif name == "list_instruments":
        return {
            "instruments": [
                inst.dict() for inst in instruments.values()
            ]
        }

    elif name == "list_strategies":
        return {"strategies": StrategyMeta.list_strategies()}

    elif name == "get_order_book":
        symbol = args["symbol"]
        depth = args.get("depth", 5)
        book = engine.books.get(symbol)
        if book is None:
            return {"error": f"No order book for {symbol}"}
        snapshot = book.depth_snapshot(depth)
        return snapshot

    else:
        return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Entry point for standalone MCP server
# ---------------------------------------------------------------------------

async def run_server(
    engine: MatchingEngine,
    portfolio: PortfolioAnalytics,
    instruments: Dict[str, Instrument],
) -> None:
    """Run the MCP server over stdio transport."""
    server = create_mcp_server(engine, portfolio, instruments)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
