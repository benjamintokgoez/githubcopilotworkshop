"""Asynchronous simulated and WebSocket market-data feeds."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import random
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from qxm.core.events import DomainEvent, EventBus, EventType
from qxm.core.models import Tick

logger = logging.getLogger(__name__)


def _utc_datetime(value: str | datetime | None = None) -> datetime:
    """Return a timezone-aware UTC datetime."""
    if value is None:
        return datetime.now(UTC)
    parsed = (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include an explicit timezone offset")
    return parsed.astimezone(UTC)


class GBMSimulator:
    """Generate synthetic prices using geometric Brownian motion."""

    def __init__(
        self,
        initial_price: float,
        mu: float = 0.0001,
        sigma: float = 0.02,
        dt: float = 1.0 / 252.0 / 390.0,
        *,
        rng: random.Random | None = None,
        seed: int | None = None,
    ) -> None:
        if initial_price <= 0 or not math.isfinite(initial_price):
            raise ValueError("initial_price must be finite and positive")
        if not math.isfinite(mu):
            raise ValueError("mu must be finite")
        if sigma < 0 or not math.isfinite(sigma):
            raise ValueError("sigma must be finite and non-negative")
        if dt <= 0 or not math.isfinite(dt):
            raise ValueError("dt must be finite and positive")
        if rng is not None and seed is not None:
            raise ValueError("Specify either rng or seed, not both")

        self._price = initial_price
        self._mu = mu
        self._sigma = sigma
        self._dt = dt
        self._rng = rng if rng is not None else random.Random(seed)

    def next_price(self) -> float:
        """Advance and return the simulated price."""
        z = self._rng.gauss(0.0, 1.0)
        drift = (self._mu - 0.5 * self._sigma**2) * self._dt
        diffusion = self._sigma * math.sqrt(self._dt) * z
        self._price *= math.exp(drift + diffusion)
        return self._price

    @property
    def current_price(self) -> float:
        """Return the latest simulated price."""
        return self._price


class MarketDataFeed:
    """Produce deterministic, simulated ticks as an asynchronous stream."""

    _BASE_PRICES = {
        "AAPL": 185.50,
        "MSFT": 420.30,
        "GOOGL": 175.80,
        "AMZN": 195.20,
        "TSLA": 245.60,
        "NVDA": 890.50,
        "META": 510.40,
        "JPM": 198.70,
        "V": 280.90,
        "BRK.B": 410.25,
    }

    def __init__(
        self,
        event_bus: EventBus,
        symbols: Sequence[str] | None = None,
        tick_interval: float = 0.1,
        *,
        rng: random.Random | None = None,
        seed: int | None = None,
    ) -> None:
        if tick_interval < 0 or not math.isfinite(tick_interval):
            raise ValueError("tick_interval must be finite and non-negative")
        if rng is not None and seed is not None:
            raise ValueError("Specify either rng or seed, not both")

        self._event_bus = event_bus
        self._symbols = list(dict.fromkeys(symbols or ()))
        self._tick_interval = tick_interval
        self._rng = rng if rng is not None else random.Random(seed)
        self._simulators: dict[str, GBMSimulator] = {}
        self._running = False
        self._stop_event = asyncio.Event()
        self._latest_ticks: dict[str, Tick] = {}

    async def _fetch_initial_prices(self) -> dict[str, float]:
        """Fetch reference prices, using deterministic synthetic fallbacks."""
        await asyncio.sleep(0)
        prices: dict[str, float] = {}
        for symbol in self._symbols:
            prices[symbol] = self._BASE_PRICES.get(symbol) or (
                100.0 + self._rng.uniform(-20.0, 50.0)
            )
        return prices

    async def start(self) -> None:
        """Initialize simulators and make the tick stream available."""
        if self._running:
            return

        initial_prices = await self._fetch_initial_prices()
        self._simulators = {
            symbol: GBMSimulator(
                price,
                sigma=self._rng.uniform(0.01, 0.04),
                rng=self._rng,
            )
            for symbol, price in initial_prices.items()
        }
        self._stop_event.clear()
        self._running = True
        logger.info("MarketDataFeed started for %d symbols", len(self._symbols))

    async def stop(self) -> None:
        """Stop generation and wake a stream waiting between ticks."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        logger.info("MarketDataFeed stopped")

    async def generate_ticks(self) -> AsyncIterator[Tick]:
        """Yield ticks while the feed is running and publish each as an event."""
        if self._running and not self._simulators:
            await self._stop_event.wait()
            return

        while self._running:
            for symbol, simulator in self._simulators.items():
                if not self._running:
                    break

                mid = simulator.next_price()
                spread = mid * self._rng.uniform(0.0001, 0.001)
                bid = Decimal(str(round(mid - spread / 2.0, 4)))
                ask = Decimal(str(round(mid + spread / 2.0, 4)))
                last = Decimal(str(round(mid + self._rng.uniform(-spread, spread) / 2.0, 4)))
                volume = self._rng.randint(100, 10_000)
                timestamp = _utc_datetime()
                tick = Tick(
                    symbol=symbol,
                    bid=bid,
                    ask=ask,
                    last=last,
                    volume=volume,
                    timestamp=timestamp,
                )
                self._latest_ticks[symbol] = tick

                await self._event_bus.publish(
                    DomainEvent(
                        event_type=EventType.MARKET_DATA_TICK,
                        source="market_data_feed",
                        payload={
                            "symbol": symbol,
                            "bid": str(bid),
                            "ask": str(ask),
                            "last": str(last),
                            "volume": volume,
                            "timestamp": timestamp.isoformat(),
                        },
                    )
                )
                yield tick

            if self._running and self._tick_interval:
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self._tick_interval,
                    )
                except TimeoutError:
                    pass

    def get_latest_tick(self, symbol: str) -> Tick | None:
        """Return the latest tick for ``symbol``, if one has been generated."""
        return self._latest_ticks.get(symbol)

    def get_all_latest_ticks(self) -> dict[str, Tick]:
        """Return a shallow snapshot of the latest ticks."""
        return dict(self._latest_ticks)

    @property
    def is_running(self) -> bool:
        """Whether the feed is currently generating ticks."""
        return self._running


class WebSocketFeedAdapter:
    """Adapt a reconnecting JSON WebSocket stream into market-data events."""

    def __init__(
        self,
        url: str,
        symbols: Sequence[str],
        event_bus: EventBus,
        reconnect_delay: float = 5.0,
    ) -> None:
        if reconnect_delay < 0 or not math.isfinite(reconnect_delay):
            raise ValueError("reconnect_delay must be finite and non-negative")
        self._url = url
        self._symbols = list(dict.fromkeys(symbols))
        self._symbol_set = set(self._symbols)
        self._event_bus = event_bus
        self._reconnect_delay = reconnect_delay
        self._running = False
        self._disconnect_event = asyncio.Event()
        self._websocket: Any | None = None

    async def connect(self) -> None:
        """Connect, consume valid ticks, and reconnect after transport failures."""
        import websockets
        from websockets.exceptions import WebSocketException

        self._disconnect_event.clear()
        self._running = True
        try:
            while self._running:
                try:
                    async with websockets.connect(self._url) as websocket:
                        self._websocket = websocket
                        await websocket.send(
                            json.dumps({"action": "subscribe", "symbols": self._symbols})
                        )
                        logger.info("Connected to %s", self._url)

                        async for message in websocket:
                            if not self._running:
                                break
                            try:
                                data = json.loads(message)
                            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                                logger.warning("Ignoring malformed feed message: %s", exc)
                                continue
                            if not isinstance(data, dict):
                                logger.warning("Ignoring non-object feed message")
                                continue
                            tick = self._parse_tick(data)
                            if tick is not None:
                                await self._event_bus.publish(
                                    DomainEvent(
                                        event_type=EventType.MARKET_DATA_TICK,
                                        source="websocket_feed",
                                        payload={
                                            "symbol": tick.symbol,
                                            "bid": str(tick.bid),
                                            "ask": str(tick.ask),
                                            "last": str(tick.last),
                                            "volume": tick.volume,
                                            "timestamp": tick.timestamp.isoformat(),
                                        },
                                    )
                                )
                except (OSError, WebSocketException) as exc:
                    if not self._running:
                        break
                    logger.warning(
                        "Feed disconnected: %s; reconnecting in %ss",
                        exc,
                        self._reconnect_delay,
                    )
                else:
                    if self._running:
                        logger.warning(
                            "Feed stream closed; reconnecting in %ss",
                            self._reconnect_delay,
                        )
                finally:
                    self._websocket = None

                if self._running:
                    await self._wait_before_reconnect()
        finally:
            self._running = False
            self._websocket = None

    async def _wait_before_reconnect(self) -> None:
        if self._reconnect_delay == 0:
            await asyncio.sleep(0)
            return
        try:
            await asyncio.wait_for(
                self._disconnect_event.wait(),
                timeout=self._reconnect_delay,
            )
        except TimeoutError:
            pass

    def _parse_tick(self, data: Mapping[str, Any]) -> Tick | None:
        try:
            timestamp = _utc_datetime(data.get("timestamp"))
            symbol_value = data["symbol"]
            if not isinstance(symbol_value, str):
                raise TypeError("symbol must be a string")
            symbol = symbol_value.strip().upper()
            if symbol not in self._symbol_set:
                logger.warning("Ignoring tick for unsubscribed symbol %s", symbol)
                return None
            volume = data.get("volume", 0)
            if isinstance(volume, bool) or not isinstance(volume, int):
                raise TypeError("volume must be an integer")
            return Tick(
                symbol=symbol,
                bid=Decimal(str(data["bid"])),
                ask=Decimal(str(data["ask"])),
                last=Decimal(str(data.get("last", data["ask"]))),
                volume=volume,
                timestamp=timestamp,
            )
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            logger.warning("Failed to parse tick: %s", exc)
            return None

    async def disconnect(self) -> None:
        """Stop reconnecting and close the active socket, if present."""
        self._running = False
        self._disconnect_event.set()
        websocket = self._websocket
        if websocket is not None:
            await websocket.close()
