"""Focused contract tests for the high-level MCP v2 server."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from mcp import Client, MCPError
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult

from qxm import __version__
from qxm.core.engine import MatchingEngine
from qxm.core.events import EventBus
from qxm.core.models import (
    Instrument,
    InstrumentType,
    Order,
    OrderStatus,
    OrderType,
    Side,
)
from qxm.mcp_server import create_default_mcp_server, create_mcp_server
from qxm.mcp_server import server as server_module


def _runtime(
    *,
    tick_size: Decimal = Decimal("0.0100"),
    lot_size: Decimal = Decimal("1"),
) -> tuple[MatchingEngine, dict[str, Instrument]]:
    instruments = {
        "AAPL": Instrument(
            symbol="AAPL",
            name="Apple Inc.",
            instrument_type=InstrumentType.EQUITY,
            tick_size=tick_size,
            lot_size=lot_size,
            currency="USD",
            exchange="XQXM",
        ),
        "MSFT": Instrument(
            symbol="MSFT",
            name="Microsoft Corporation",
            instrument_type=InstrumentType.EQUITY,
            tick_size=tick_size,
            lot_size=lot_size,
            currency="USD",
            exchange="XQXM",
        ),
    }
    return MatchingEngine(EventBus(), instruments=instruments), instruments


def _structured(result: CallToolResult) -> dict[str, object]:
    payload = result.structured_content
    assert isinstance(payload, dict)
    return payload


def _assert_utc(value: object) -> None:
    assert isinstance(value, str)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.utcoffset() == timedelta(0)


@pytest.mark.asyncio
async def test_read_only_surface_schemas_and_annotations() -> None:
    engine, instruments = _runtime()
    server = create_mcp_server(engine, instruments)

    async with Client(server, raise_exceptions=True) as client:
        listed = await client.list_tools()
        tools = {tool.name: tool for tool in listed.tools}

        assert set(tools) == {"calculate_risk", "get_order_book", "list_instruments"}
        for tool in tools.values():
            assert tool.annotations is not None
            assert tool.annotations.read_only_hint is True
            assert tool.annotations.destructive_hint is False
            assert tool.annotations.idempotent_hint is True
            assert tool.annotations.open_world_hint is False

        assert tools["list_instruments"].input_schema["properties"]["limit"]["maximum"] == 50
        assert tools["get_order_book"].input_schema["properties"]["depth"]["maximum"] == 20
        risk_schema = json.dumps(tools["calculate_risk"].input_schema)
        assert '"maxItems": 256' in risk_schema

        invalid_depth = await client.call_tool("get_order_book", {"symbol": "AAPL", "depth": 21})
        assert invalid_depth.is_error is True
        oversized_history = await client.call_tool(
            "calculate_risk",
            {
                "portfolio_value": "1000",
                "pnl_history": ["-1"] * 257,
            },
        )
        assert oversized_history.is_error is True


@pytest.mark.asyncio
async def test_default_factory_loads_local_configuration_read_only() -> None:
    server = create_default_mcp_server()
    assert server.version == __version__

    async with Client(server, raise_exceptions=True) as client:
        tools = {tool.name for tool in (await client.list_tools()).tools}
        instruments = _structured(await client.call_tool("list_instruments", {"limit": 50}))

    assert tools == {"calculate_risk", "get_order_book", "list_instruments"}
    assert instruments["total"] == 10
    assert instruments["environment"] == "SIMULATION"


@pytest.mark.asyncio
async def test_decimal_utc_and_bounded_read_results() -> None:
    engine, instruments = _runtime(lot_size=Decimal("0.001"))
    await engine.submit_order(
        Order(
            order_id="bid-one",
            client_id="maker",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2.500"),
            price=Decimal("100.1000"),
        )
    )
    await engine.submit_order(
        Order(
            order_id="bid-two",
            client_id="maker",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.000"),
            price=Decimal("100.0900"),
        )
    )
    server = create_mcp_server(engine, instruments)

    async with Client(server, raise_exceptions=True) as client:
        listed = _structured(await client.call_tool("list_instruments", {"limit": 1}))
        assert listed["returned"] == 1
        assert len(listed["instruments"]) == 1
        first_instrument = listed["instruments"][0]
        assert isinstance(first_instrument, dict)
        assert first_instrument["tick_size"] == "0.0100"

        snapshot = _structured(
            await client.call_tool("get_order_book", {"symbol": "aapl", "depth": 1})
        )
        assert snapshot["symbol"] == "AAPL"
        assert len(snapshot["bids"]) == 1
        assert snapshot["bids"][0]["price"] == "100.1000"
        assert snapshot["bids"][0]["quantity"] == "2.500"
        _assert_utc(snapshot["as_of"])

        risk = _structured(
            await client.call_tool(
                "calculate_risk",
                {
                    "portfolio_value": "1000.00",
                    "daily_volatility": "0.02",
                    "pnl_history": ["10.00", "-25.50", "-5.25"],
                    "confidence": "0.95",
                    "holding_period": 1,
                },
            )
        )
        assert isinstance(risk["parametric_var"], str)
        assert isinstance(risk["historical_var"], str)
        assert isinstance(risk["conditional_var"], str)
        assert Decimal(risk["parametric_var"]) >= 0
        assert Decimal(risk["historical_var"]) >= 0
        assert Decimal(risk["conditional_var"]) >= 0
        _assert_utc(risk["as_of"])


@pytest.mark.asyncio
async def test_unknown_symbols_are_protocol_errors() -> None:
    engine, instruments = _runtime()
    server = create_mcp_server(engine, instruments)

    async with Client(server, raise_exceptions=True) as client:
        with pytest.raises(MCPError, match="Unknown simulated instrument: NOPE"):
            await client.call_tool("get_order_book", {"symbol": "NOPE"})


def test_writes_require_a_conservative_bound_client_identity() -> None:
    engine, instruments = _runtime()
    invalid_client_ids = (
        None,
        "",
        " leading",
        "trailing ",
        "contains space",
        "forged\nentry",
        "control\x00character",
        "non-ascii-\N{LATIN SMALL LETTER E WITH ACUTE}",
        "x" * 65,
    )
    for client_id in invalid_client_ids:
        with pytest.raises(ValueError, match="client_id"):
            create_mcp_server(
                engine,
                instruments,
                allow_writes=True,
                client_id=client_id,
            )


@pytest.mark.asyncio
async def test_opt_in_writes_execute_cancel_reject_and_enforce_identity() -> None:
    engine, instruments = _runtime()
    await engine.submit_order(
        Order(
            order_id="foreign-ask",
            client_id="external-maker",
            symbol="AAPL",
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2"),
            price=Decimal("99.90"),
        )
    )
    server = create_mcp_server(
        engine,
        instruments,
        allow_writes=True,
        client_id="workshop-client",
    )

    async with Client(server, raise_exceptions=True) as client:
        listed = await client.list_tools()
        tools = {tool.name: tool for tool in listed.tools}
        assert set(tools) == {
            "calculate_risk",
            "cancel_order",
            "get_order_book",
            "list_instruments",
            "submit_order",
        }
        submit_schema = tools["submit_order"].input_schema
        assert "client_id" not in submit_schema["properties"]
        assert "api_key" not in submit_schema["properties"]
        assert submit_schema["$defs"]["SupportedOrderType"]["enum"] == ["LIMIT", "MARKET"]
        assert submit_schema["$defs"]["SupportedTimeInForce"]["enum"] == ["GTC", "IOC", "FOK"]
        quantity_schema = submit_schema["properties"]["quantity"]
        assert quantity_schema["anyOf"][0]["maximum"] == 10_000
        assert tools["submit_order"].output_schema is not None
        output_properties = tools["submit_order"].output_schema["properties"]
        assert output_properties["trades"]["maxItems"] == 100
        assert output_properties["returned_trade_count"]["maximum"] == 100
        assert output_properties["rejection_reason"]["anyOf"][0]["maxLength"] == 256
        assert tools["submit_order"].annotations is not None
        assert tools["submit_order"].annotations.read_only_hint is False
        assert tools["submit_order"].annotations.destructive_hint is True
        assert tools["submit_order"].annotations.idempotent_hint is False
        assert tools["submit_order"].annotations.open_world_hint is False
        assert tools["cancel_order"].annotations is not None
        assert tools["cancel_order"].annotations.idempotent_hint is True

        order_count = engine.order_count
        oversized = await client.call_tool(
            "submit_order",
            {
                "order_id": "mcp-oversized",
                "symbol": "AAPL",
                "side": "BUY",
                "quantity": "10001",
                "price": "100.00",
            },
        )
        assert oversized.is_error is True
        assert engine.order_count == order_count

        fill = _structured(
            await client.call_tool(
                "submit_order",
                {
                    "order_id": "mcp-fill",
                    "symbol": "AAPL",
                    "side": "BUY",
                    "quantity": "1",
                    "order_type": "LIMIT",
                    "price": "100.00",
                },
            )
        )
        assert fill["status"] == OrderStatus.FILLED.value
        assert fill["accepted"] is True
        assert fill["rejection_reason"] is None
        assert fill["trade_count"] == 1
        assert fill["returned_trade_count"] == 1
        assert fill["trades_truncated"] is False
        assert fill["trades"][0]["price"] == "99.90"
        assert fill["trades"][0]["quantity"] == "1"
        _assert_utc(fill["trades"][0]["timestamp"])

        resting = _structured(
            await client.call_tool(
                "submit_order",
                {
                    "order_id": "mcp-resting",
                    "symbol": "AAPL",
                    "side": "BUY",
                    "quantity": "2",
                    "price": "90.00",
                },
            )
        )
        assert resting["status"] == OrderStatus.ACCEPTED.value
        cancelled = _structured(await client.call_tool("cancel_order", {"order_id": "mcp-resting"}))
        assert cancelled["status"] == OrderStatus.CANCELLED.value
        _assert_utc(cancelled["updated_at"])

        rejected = _structured(
            await client.call_tool(
                "submit_order",
                {
                    "order_id": "mcp-rejected",
                    "symbol": "AAPL",
                    "side": "BUY",
                    "quantity": "1.5",
                    "price": "90.00",
                },
            )
        )
        assert rejected["status"] == OrderStatus.REJECTED.value
        assert rejected["accepted"] is False
        assert rejected["rejection_reason"] == "Quantity 1.5 is not a multiple of lot size 1"
        assert rejected["trade_count"] == 0
        assert rejected["returned_trade_count"] == 0

        with pytest.raises(MCPError, match="already been submitted"):
            await client.call_tool(
                "submit_order",
                {
                    "order_id": "mcp-rejected",
                    "symbol": "AAPL",
                    "side": "BUY",
                    "quantity": "1",
                    "price": "90.00",
                },
            )

        with pytest.raises(MCPError, match="not found for this MCP client"):
            await client.call_tool("cancel_order", {"order_id": "foreign-ask"})
        book = engine.get_book("AAPL")
        assert book is not None
        assert book.contains("foreign-ask")


def test_rejection_reason_is_bounded_without_losing_engine_context() -> None:
    order = Order(
        order_id="bounded-rejection",
        client_id="mcp-client",
        symbol="AAPL",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1"),
        price=Decimal("90"),
        status=OrderStatus.REJECTED,
    )
    result = server_module._order_result(
        server_module.OrderSubmission(
            order=order,
            rejection_reason="risk policy: " + "x" * 300,
        )
    )

    assert result.rejection_reason is not None
    assert result.rejection_reason.startswith("risk policy: ")
    assert result.rejection_reason.endswith("...")
    assert len(result.rejection_reason) == server_module.MAX_REJECTION_REASON_LENGTH


@pytest.mark.asyncio
async def test_submit_order_bounds_serialized_trades_without_hiding_execution() -> None:
    engine, instruments = _runtime()
    for index in range(105):
        await engine.submit_order(
            Order(
                order_id=f"maker-{index:03}",
                client_id=f"maker-{index:03}",
                symbol="AAPL",
                side=Side.SELL,
                order_type=OrderType.LIMIT,
                quantity=Decimal("1.000"),
                price=Decimal("99.9900"),
            )
        )

    server = create_mcp_server(
        engine,
        instruments,
        allow_writes=True,
        client_id="bounded-output-client",
    )
    async with Client(server, raise_exceptions=True) as client:
        result = _structured(
            await client.call_tool(
                "submit_order",
                {
                    "order_id": "large-fill",
                    "symbol": "AAPL",
                    "side": "BUY",
                    "quantity": "105.000",
                    "price": "100.0000",
                },
            )
        )

    assert result["status"] == OrderStatus.FILLED.value
    assert result["filled_quantity"] == "105.000"
    assert result["trade_count"] == 105
    assert result["returned_trade_count"] == 100
    assert result["trades_truncated"] is True
    assert len(result["trades"]) == 100
    assert len(engine.trade_log) == 105
    for retained, executed in zip(result["trades"], engine.trade_log[:100], strict=True):
        assert retained["price"] == str(executed.price)
        assert retained["quantity"] == str(executed.quantity)
        assert retained["timestamp"] == executed.timestamp.isoformat().replace("+00:00", "Z")


@pytest.mark.asyncio
async def test_server_instances_do_not_share_runtime_state() -> None:
    engine_a, instruments_a = _runtime()
    engine_b, instruments_b = _runtime()
    server_a = create_mcp_server(
        engine_a,
        instruments_a,
        allow_writes=True,
        client_id="client-a",
    )
    server_b = create_mcp_server(
        engine_b,
        instruments_b,
        allow_writes=True,
        client_id="client-b",
    )

    async with (
        Client(server_a, raise_exceptions=True) as client_a,
        Client(server_b, raise_exceptions=True) as client_b,
    ):
        await client_a.call_tool(
            "submit_order",
            {
                "order_id": "isolated-order",
                "symbol": "AAPL",
                "side": "BUY",
                "quantity": "1",
                "price": "100.00",
            },
        )
        snapshot_a = _structured(await client_a.call_tool("get_order_book", {"symbol": "AAPL"}))
        snapshot_b = _structured(await client_b.call_tool("get_order_book", {"symbol": "AAPL"}))

    assert len(snapshot_a["bids"]) == 1
    assert snapshot_b["bids"] == []
    assert engine_a.order_count == 1
    assert engine_b.order_count == 0


@pytest.mark.asyncio
async def test_stdio_entrypoint_initializes_and_lists_read_only_tools() -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "qxm.mcp_server.server"],
        cwd=Path(__file__).resolve().parents[1],
    )
    async with Client(
        stdio_client(parameters),
        raise_exceptions=True,
        mode="legacy",
    ) as client:
        tools = {tool.name for tool in (await client.list_tools()).tools}

    assert tools == {"calculate_risk", "get_order_book", "list_instruments"}


def test_import_is_silent_and_entrypoint_uses_sync_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "import qxm.mcp_server.server"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert inspect.iscoroutinefunction(server_module.run_server) is False

    class StubServer:
        def __init__(self) -> None:
            self.ran = False

        def run(self) -> None:
            self.ran = True

    stub = StubServer()
    monkeypatch.setattr(server_module, "create_default_mcp_server", lambda: stub)
    server_module.run_server()
    assert stub.ran is True
