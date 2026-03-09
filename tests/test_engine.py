"""Tests for the matching engine — order submission, FIFO matching, cancellation."""

from __future__ import annotations

import pytest

from qxm.core.engine import MatchingEngine
from qxm.core.models import OrderStatus, OrderType, Side
from tests.conftest import make_order


class TestOrderSubmission:
    """Test order lifecycle through the matching engine."""

    def test_limit_order_rests_when_no_match(self, engine: MatchingEngine):
        """A limit buy with no sells should rest on the book."""
        order = make_order(side=Side.BUY, price=150.0, quantity=100)
        trades = engine.submit_order(order)
        assert trades == []
        assert order.status == OrderStatus.OPEN

    def test_limit_orders_match(self, engine: MatchingEngine):
        """A sell order should match against a resting buy at the same price."""
        buy = make_order(side=Side.BUY, price=150.0, quantity=100)
        engine.submit_order(buy)

        sell = make_order(side=Side.SELL, price=150.0, quantity=100, client_id="seller")
        trades = engine.submit_order(sell)
        assert len(trades) == 1
        assert trades[0].quantity == 100
        assert trades[0].price == 150.0

    def test_partial_fill(self, engine: MatchingEngine):
        """Partial fills should leave residual on the book."""
        buy = make_order(side=Side.BUY, price=150.0, quantity=200)
        engine.submit_order(buy)

        sell = make_order(side=Side.SELL, price=150.0, quantity=80, client_id="seller")
        trades = engine.submit_order(sell)
        assert len(trades) == 1
        assert trades[0].quantity == 80
        assert buy.status == OrderStatus.PARTIALLY_FILLED
        assert buy.filled_quantity == 80

    def test_cancel_order(self, engine: MatchingEngine):
        """Cancelling an order should remove it from the book."""
        order = make_order(side=Side.BUY, price=150.0, quantity=100)
        engine.submit_order(order)
        assert engine.cancel_order(order.order_id) is True
        assert order.status == OrderStatus.CANCELLED

    def test_cancel_nonexistent_order(self, engine: MatchingEngine):
        """Cancelling a non-existent order should return False."""
        assert engine.cancel_order("nonexistent-id") is False

    def test_fifo_priority(self, engine: MatchingEngine):
        """Earlier orders at the same price should fill first."""
        buy1 = make_order(side=Side.BUY, price=150.0, quantity=50, client_id="buyer1")
        buy2 = make_order(side=Side.BUY, price=150.0, quantity=50, client_id="buyer2")
        engine.submit_order(buy1)
        engine.submit_order(buy2)

        sell = make_order(side=Side.SELL, price=150.0, quantity=50, client_id="seller")
        trades = engine.submit_order(sell)
        assert len(trades) == 1
        assert trades[0].buyer_id == "buyer1"

    def test_price_priority(self, engine: MatchingEngine):
        """Higher-priced buy orders should fill first."""
        buy_low = make_order(side=Side.BUY, price=149.0, quantity=100, client_id="buyer_low")
        buy_high = make_order(side=Side.BUY, price=151.0, quantity=100, client_id="buyer_high")
        engine.submit_order(buy_low)
        engine.submit_order(buy_high)

        sell = make_order(side=Side.SELL, price=149.0, quantity=100, client_id="seller")
        trades = engine.submit_order(sell)
        assert len(trades) == 1
        assert trades[0].buyer_id == "buyer_high"
        assert trades[0].price == 151.0


class TestMarketOrders:
    """Test market order handling."""

    def test_market_buy_fills_at_best_ask(self, engine: MatchingEngine):
        """Market buy should fill at the resting sell's price."""
        sell = make_order(side=Side.SELL, price=155.0, quantity=100, client_id="seller")
        engine.submit_order(sell)

        buy = make_order(
            side=Side.BUY,
            price=None,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        trades = engine.submit_order(buy)
        assert len(trades) == 1
        # NOTE: This test will catch the planted bug — market orders
        # should fill at the resting order's price (155.0), not the
        # incoming order's price (None).
        assert trades[0].price == 155.0
