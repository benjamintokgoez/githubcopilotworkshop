"""Asynchronous market data feed module.

Provides both a simulated feed (for testing/workshop use) and a
WebSocket-based feed adapter.  The ``MarketDataFeed`` class is the
primary interface — it produces an async stream of ``Tick`` objects
that downstream consumers (strategies, risk engine) subscribe to.

The simulated feed generates realistic price movements using
geometric Brownian motion (GBM).

**BUG (Challenge 2):** ``_fetch_initial_prices`` is an async method
but is called without ``await`` in ``start()``, causing it to return
a coroutine object instead of the actual price data.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import random
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Set

from qxm.core.events import DomainEvent, EventBus, EventType
from qxm.core.models import Tick

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simulated price generator (Geometric Brownian Motion)
# ---------------------------------------------------------------------------

class GBMSimulator:
    """Generates synthetic price paths using geometric Brownian motion.

    .. math::

        S_{t+dt} = S_t \\exp\\left((\\mu - \\frac{\\sigma^2}{2}) dt + \\sigma \\sqrt{dt} Z\\right)

    where :math:`Z \\sim \\mathcal{N}(0,1)`.
    """

    def __init__(
        self,
        initial_price: float,
        mu: float = 0.0001,
        sigma: float = 0.02,
        dt: float = 1.0 / 252.0 / 390.0,  # ~1 minute in trading-year terms
    ) -> None:
        self._price = initial_price
        self._mu = mu
        self._sigma = sigma
        self._dt = dt

    def next_price(self) -> float:
        z = random.gauss(0, 1)
        drift = (self._mu - 0.5 * self._sigma ** 2) * self._dt
        diffusion = self._sigma * math.sqrt(self._dt) * z
        self._price *= math.exp(drift + diffusion)
        return self._price

    @property
    def current_price(self) -> float:
        return self._price


# ---------------------------------------------------------------------------
# Market Data Feed
# ---------------------------------------------------------------------------

class MarketDataFeed:
    """Asynchronous market data feed that produces ``Tick`` objects.

    In simulation mode, generates ticks via ``GBMSimulator``.
    The feed publishes each tick as a ``DomainEvent`` on the event bus,
    and also yields ticks via an async generator for direct consumption.
    """

    def __init__(
        self,
        event_bus: EventBus,
        symbols: Optional[List[str]] = None,
        tick_interval: float = 0.1,
    ) -> None:
        self._event_bus = event_bus
        self._symbols = symbols or []
        self._tick_interval = tick_interval
        self._simulators: Dict[str, GBMSimulator] = {}
        self._running = False
        self._latest_ticks: Dict[str, Tick] = {}
        self._subscribers: List[asyncio.Queue[Tick]] = []

    async def _fetch_initial_prices(self) -> Dict[str, float]:
        """Fetch initial reference prices for all symbols.

        In a production system this would call an exchange REST API.
        Here we simulate a network call with a small delay.
        """
        await asyncio.sleep(0.05)  # Simulate latency
        prices = {}
        base_prices = {
            "AAPL": 185.50, "MSFT": 420.30, "GOOGL": 175.80,
            "AMZN": 195.20, "TSLA": 245.60, "NVDA": 890.50,
            "META": 510.40, "JPM": 198.70, "V": 280.90,
            "BRK.B": 410.25,
        }
        for sym in self._symbols:
            prices[sym] = base_prices.get(sym, 100.0 + random.uniform(-20, 50))
        return prices

    async def start(self) -> None:
        """Initialize simulators and begin generating ticks."""
        # BUG (Challenge 2): missing await — returns coroutine, not dict
        initial_prices = self._fetch_initial_prices()

        for sym, price in initial_prices.items():
            vol = random.uniform(0.01, 0.04)
            self._simulators[sym] = GBMSimulator(price, sigma=vol)

        self._running = True
        logger.info("MarketDataFeed started for %d symbols", len(self._symbols))

    async def stop(self) -> None:
        self._running = False
        logger.info("MarketDataFeed stopped")

    async def generate_ticks(self) -> AsyncIterator[Tick]:
        """Async generator that yields simulated ticks continuously."""
        while self._running:
            for sym, sim in self._simulators.items():
                mid = sim.next_price()
                spread = mid * random.uniform(0.0001, 0.001)
                bid = Decimal(str(round(mid - spread / 2, 4)))
                ask = Decimal(str(round(mid + spread / 2, 4)))
                last = Decimal(str(round(mid + random.uniform(-spread, spread) / 2, 4)))
                volume = random.randint(100, 10000)

                tick = Tick(
                    symbol=sym,
                    bid=bid,
                    ask=ask,
                    last=last,
                    volume=volume,
                    timestamp=datetime.utcnow(),
                )
                self._latest_ticks[sym] = tick

                # Publish to event bus
                await self._event_bus.publish(DomainEvent(
                    event_type=EventType.MARKET_DATA_TICK,
                    source="market_data_feed",
                    payload={
                        "symbol": sym,
                        "bid": str(bid),
                        "ask": str(ask),
                        "last": str(last),
                        "volume": volume,
                    },
                ))

                yield tick

            await asyncio.sleep(self._tick_interval)

    def get_latest_tick(self, symbol: str) -> Optional[Tick]:
        return self._latest_ticks.get(symbol)

    def get_all_latest_ticks(self) -> Dict[str, Tick]:
        return dict(self._latest_ticks)

    @property
    def is_running(self) -> bool:
        return self._running


# ---------------------------------------------------------------------------
# WebSocket feed adapter (production skeleton)
# ---------------------------------------------------------------------------

class WebSocketFeedAdapter:
    """Adapter for connecting to a real WebSocket-based market data source.

    This is a structural skeleton — in the workshop it is not wired up,
    but demonstrates the intended production architecture using
    ``websockets`` and ``asyncio``.
    """

    def __init__(
        self,
        url: str,
        symbols: List[str],
        event_bus: EventBus,
        reconnect_delay: float = 5.0,
    ) -> None:
        self._url = url
        self._symbols = symbols
        self._event_bus = event_bus
        self._reconnect_delay = reconnect_delay
        self._running = False

    async def connect(self) -> None:
        """Connect to the WebSocket feed with automatic reconnection."""
        import websockets

        self._running = True
        while self._running:
            try:
                async with websockets.connect(self._url) as ws:
                    subscribe_msg = json.dumps({
                        "action": "subscribe",
                        "symbols": self._symbols,
                    })
                    await ws.send(subscribe_msg)
                    logger.info("Connected to %s", self._url)

                    async for message in ws:
                        data = json.loads(message)
                        tick = self._parse_tick(data)
                        if tick:
                            await self._event_bus.publish(DomainEvent(
                                event_type=EventType.MARKET_DATA_TICK,
                                source="websocket_feed",
                                payload=data,
                            ))
            except Exception as exc:
                logger.error("Feed disconnected: %s — reconnecting in %ss", exc, self._reconnect_delay)
                await asyncio.sleep(self._reconnect_delay)

    def _parse_tick(self, data: Dict[str, Any]) -> Optional[Tick]:
        try:
            return Tick(
                symbol=data["symbol"],
                bid=Decimal(str(data["bid"])),
                ask=Decimal(str(data["ask"])),
                last=Decimal(str(data.get("last", data["ask"]))),
                volume=int(data.get("volume", 0)),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
            )
        except (KeyError, ValueError) as e:
            logger.warning("Failed to parse tick: %s", e)
            return None

    async def disconnect(self) -> None:
        self._running = False
