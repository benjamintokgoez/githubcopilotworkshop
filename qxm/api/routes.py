"""FastAPI routes — REST endpoints for the QuantCore trading platform.

Exposes order management, position queries, risk analytics, and
strategy control endpoints.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from qxm.core.engine import MatchingEngine
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
from qxm.utils.metrics import REGISTRY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["trading"])


# ---------------------------------------------------------------------------
# Dependency stubs (injected by main.py at startup)
# ---------------------------------------------------------------------------

_engine: Optional[MatchingEngine] = None
_portfolio: Optional[PortfolioAnalytics] = None


def get_engine() -> MatchingEngine:
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialised")
    return _engine


def get_portfolio() -> PortfolioAnalytics:
    if _portfolio is None:
        raise HTTPException(status_code=503, detail="Portfolio not initialised")
    return _portfolio


def set_engine(engine: MatchingEngine) -> None:
    global _engine
    _engine = engine


def set_portfolio(portfolio: PortfolioAnalytics) -> None:
    global _portfolio
    _portfolio = portfolio


# ---------------------------------------------------------------------------
# Order endpoints
# ---------------------------------------------------------------------------

@router.post("/orders")
async def submit_order(
    symbol: str,
    side: str,
    quantity: int,
    price: Optional[float] = None,
    order_type: str = "LIMIT",
    client_id: str = "api_user",
    engine: MatchingEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """Submit a new order to the matching engine.

    .. note::
        BUG (Challenge 5 — Security): No input validation on
        ``quantity`` (could be negative or zero) or ``price``
        (could be negative).  ``symbol`` is passed unchecked.
    """
    order = Order(
        symbol=symbol,
        side=Side(side.upper()),
        order_type=OrderType(order_type.upper()),
        quantity=quantity,
        price=price,
        client_id=client_id,
        time_in_force=TimeInForce.GTC,
    )
    trades = engine.submit_order(order)
    return {
        "order_id": order.order_id,
        "status": order.status.value,
        "trades": [t.dict() for t in trades],
    }


@router.delete("/orders/{order_id}")
async def cancel_order(
    order_id: str,
    engine: MatchingEngine = Depends(get_engine),
) -> Dict[str, str]:
    """Cancel an open order."""
    success = engine.cancel_order(order_id)
    if not success:
        raise HTTPException(status_code=404, detail="Order not found or already filled")
    return {"order_id": order_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# Position / Portfolio endpoints
# ---------------------------------------------------------------------------

@router.get("/positions")
async def get_positions(
    client_id: Optional[str] = None,
    engine: MatchingEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """Return current positions."""
    positions = engine.position_manager.get_positions(client_id)
    return {"positions": [p.dict() for p in positions.values()]}


@router.get("/portfolio/snapshot")
async def portfolio_snapshot(
    portfolio: PortfolioAnalytics = Depends(get_portfolio),
) -> Dict[str, Any]:
    """Return a full portfolio snapshot with risk metrics."""
    snap = portfolio.snapshot()
    return snap.dict()


@router.get("/portfolio/risk")
async def portfolio_risk(
    portfolio: PortfolioAnalytics = Depends(get_portfolio),
) -> Dict[str, Any]:
    """Return risk metrics (VaR, Greeks, Sharpe, drawdown)."""
    metrics = portfolio.risk_metrics()
    return metrics.dict()


# ---------------------------------------------------------------------------
# Instrument lookup
# ---------------------------------------------------------------------------

@router.get("/instruments/search")
async def search_instruments(
    request: Request,
    q: str = Query(..., description="Search query for instrument symbol or name"),
) -> Dict[str, Any]:
    """Search instruments by name or symbol.

    .. warning::
        BUG (Challenge 5 — Security): Constructs a raw SQL query by
        string concatenation using user-supplied input ``q``.
        Vulnerable to SQL injection.  Should use parameterised queries.
    """
    from sqlalchemy import text

    db = request.app.state.db_session
    # BUG: SQL injection — user input directly interpolated
    query = text(f"SELECT * FROM instruments WHERE symbol LIKE '%{q}%' OR name LIKE '%{q}%'")
    results = db.execute(query).fetchall()
    return {
        "results": [dict(row._mapping) for row in results],
        "count": len(results),
    }


# ---------------------------------------------------------------------------
# Strategy endpoints
# ---------------------------------------------------------------------------

@router.get("/strategies")
async def list_strategies() -> Dict[str, List[str]]:
    """List all registered strategy names."""
    return {"strategies": StrategyMeta.list_strategies()}


# ---------------------------------------------------------------------------
# Metrics endpoint
# ---------------------------------------------------------------------------

@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Return trading system metrics."""
    return REGISTRY.snapshot()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@router.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
