"""Tests for pydantic domain models — validation, serialisation, properties."""

from __future__ import annotations

from decimal import Decimal

import pytest

from qxm.core.models import (
    Instrument,
    InstrumentType,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
    TimeInForce,
    Trade,
)


class TestInstrument:
    def test_create_equity(self):
        inst = Instrument(
            symbol="AAPL",
            name="Apple Inc.",
            instrument_type=InstrumentType.EQUITY,
            tick_size=0.01,
            lot_size=1,
        )
        assert inst.symbol == "AAPL"
        assert inst.instrument_type == InstrumentType.EQUITY

    def test_tick_size_validation(self):
        with pytest.raises(ValueError):
            Instrument(
                symbol="BAD",
                name="Bad",
                instrument_type=InstrumentType.EQUITY,
                tick_size=-0.01,
                lot_size=1,
            )


class TestOrder:
    def test_new_order_status(self):
        order = Order(
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.0,
            client_id="test",
            time_in_force=TimeInForce.GTC,
        )
        assert order.status == OrderStatus.NEW
        assert order.remaining_quantity == 100

    def test_order_serialisation(self):
        order = Order(
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.0,
            client_id="test",
            time_in_force=TimeInForce.GTC,
        )
        d = order.dict()
        assert d["symbol"] == "AAPL"
        assert d["side"] == "BUY"

    def test_remaining_quantity(self):
        order = Order(
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.0,
            client_id="test",
            time_in_force=TimeInForce.GTC,
        )
        order.filled_quantity = 30
        assert order.remaining_quantity == 70


class TestPosition:
    def test_apply_buy_fill(self):
        pos = Position(symbol="AAPL", quantity=0, avg_price=0.0, unrealised_pnl=0.0)
        pos.apply_fill(Side.BUY, 100, 150.0)
        assert pos.quantity == 100
        assert pos.avg_price == 150.0

    def test_apply_sell_fill_closes_position(self):
        pos = Position(symbol="AAPL", quantity=100, avg_price=150.0, unrealised_pnl=0.0)
        pos.apply_fill(Side.SELL, 100, 160.0)
        assert pos.quantity == 0
        assert pos.realised_pnl == pytest.approx(1000.0)  # (160 - 150) * 100
