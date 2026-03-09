"""Shared test fixtures for QuantCore."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict

import pytest

from qxm.core.events import EventBus
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


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def instruments() -> Dict[str, Instrument]:
    return {
        "AAPL": Instrument(
            symbol="AAPL",
            name="Apple Inc.",
            instrument_type=InstrumentType.EQUITY,
            tick_size=0.01,
            lot_size=1,
        ),
        "GOOGL": Instrument(
            symbol="GOOGL",
            name="Alphabet Inc.",
            instrument_type=InstrumentType.EQUITY,
            tick_size=0.01,
            lot_size=1,
        ),
        "MSFT": Instrument(
            symbol="MSFT",
            name="Microsoft Corporation",
            instrument_type=InstrumentType.EQUITY,
            tick_size=0.01,
            lot_size=1,
        ),
    }


@pytest.fixture
def engine(event_bus: EventBus, instruments: Dict[str, Instrument]) -> MatchingEngine:
    return MatchingEngine(event_bus=event_bus, instruments=instruments)


@pytest.fixture
def portfolio(instruments: Dict[str, Instrument]) -> PortfolioAnalytics:
    return PortfolioAnalytics(instruments=instruments)


def make_order(
    symbol: str = "AAPL",
    side: Side = Side.BUY,
    quantity: int = 100,
    price: float = 150.0,
    order_type: OrderType = OrderType.LIMIT,
    client_id: str = "test_client",
) -> Order:
    """Helper to create test orders."""
    return Order(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        client_id=client_id,
        time_in_force=TimeInForce.GTC,
    )
