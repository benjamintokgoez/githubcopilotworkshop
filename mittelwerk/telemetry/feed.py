"""Asynchronous synthetic and WebSocket telemetry feeds."""

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

from mittelwerk.core.events import DispatchEventType, DomainEvent, EventBus
from mittelwerk.core.models import TelemetryReading

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


class ReadingSimulator:
    """Generate positive synthetic sensor readings with multiplicative noise."""

    def __init__(
        self,
        initial_value: float,
        mu: float = 0.0001,
        sigma: float = 0.02,
        dt: float = 1.0 / (365.0 * 24.0 * 60.0),
        *,
        rng: random.Random | None = None,
        seed: int | None = None,
    ) -> None:
        if initial_value <= 0 or not math.isfinite(initial_value):
            raise ValueError("initial_value must be finite and positive")
        if not math.isfinite(mu):
            raise ValueError("mu must be finite")
        if sigma < 0 or not math.isfinite(sigma):
            raise ValueError("sigma must be finite and non-negative")
        if dt <= 0 or not math.isfinite(dt):
            raise ValueError("dt must be finite and positive")
        if rng is not None and seed is not None:
            raise ValueError("Specify either rng or seed, not both")

        self._value = initial_value
        self._mu = mu
        self._sigma = sigma
        self._dt = dt
        self._rng = rng if rng is not None else random.Random(seed)

    def next_value(self) -> float:
        """Advance and return the simulated reading."""
        z = self._rng.gauss(0.0, 1.0)
        drift = (self._mu - 0.5 * self._sigma**2) * self._dt
        diffusion = self._sigma * math.sqrt(self._dt) * z
        self._value *= math.exp(drift + diffusion)
        return self._value

    @property
    def current_value(self) -> float:
        """Return the latest simulated reading."""
        return self._value


class TelemetryFeed:
    """Produce deterministic, simulated telemetry readings as an asynchronous stream."""

    # Synthetic baseline readings for fictional industrial assets.
    _BASE_READINGS = {
        "CNC-01": 96.5,
        "PRESS-04": 182.0,
        "CONV-12": 68.0,
        "ROBOT-07": 121.5,
        "COMP-03": 154.0,
        "GEN-02": 207.5,
        "HVAC-09": 58.0,
        "FORK-05": 73.5,
        "CNC-02": 104.0,
        "PRESS-01": 176.5,
    }

    def __init__(
        self,
        event_bus: EventBus,
        asset_ids: Sequence[str] | None = None,
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
        self._asset_ids = [asset_id.strip().upper() for asset_id in dict.fromkeys(asset_ids or ())]
        self._tick_interval = tick_interval
        self._rng = rng if rng is not None else random.Random(seed)
        self._simulators: dict[str, ReadingSimulator] = {}
        self._running = False
        self._stop_event = asyncio.Event()
        self._latest_readings: dict[str, TelemetryReading] = {}

    async def _fetch_initial_readings(self) -> dict[str, float]:
        """Fetch reference readings, using deterministic synthetic fallbacks."""
        await asyncio.sleep(0)
        readings: dict[str, float] = {}
        for asset_id in self._asset_ids:
            readings[asset_id] = self._BASE_READINGS.get(asset_id) or (
                100.0 + self._rng.uniform(-20.0, 50.0)
            )
        return readings

    async def start(self) -> None:
        """Initialize simulators and make the reading stream available."""
        if self._running:
            return

        initial_readings = await self._fetch_initial_readings()
        self._simulators = {
            asset_id: ReadingSimulator(
                value,
                sigma=self._rng.uniform(0.01, 0.04),
                rng=self._rng,
            )
            for asset_id, value in initial_readings.items()
        }
        self._stop_event.clear()
        self._running = True
        logger.info("TelemetryFeed started for %d assets", len(self._asset_ids))

    async def stop(self) -> None:
        """Stop generation and wake a stream waiting between readings."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        logger.info("TelemetryFeed stopped")

    async def generate_readings(self) -> AsyncIterator[TelemetryReading]:
        """Yield readings while the feed is running and publish each as an event."""
        if self._running and not self._simulators:
            await self._stop_event.wait()
            return

        while self._running:
            for asset_id, simulator in self._simulators.items():
                if not self._running:
                    break

                mid = simulator.next_value()
                spread = mid * self._rng.uniform(0.0001, 0.001)
                min_reading = Decimal(str(round(mid - spread / 2.0, 4)))
                max_reading = Decimal(str(round(mid + spread / 2.0, 4)))
                last_reading = Decimal(
                    str(round(mid + self._rng.uniform(-spread, spread) / 2.0, 4))
                )
                sample_count = self._rng.randint(100, 10_000)
                timestamp = _utc_datetime()
                reading = TelemetryReading(
                    asset_id=asset_id,
                    min_reading=min_reading,
                    max_reading=max_reading,
                    last_reading=last_reading,
                    sample_count=sample_count,
                    timestamp=timestamp,
                )
                self._latest_readings[asset_id] = reading

                await self._event_bus.publish(
                    DomainEvent(
                        event_type=DispatchEventType.TELEMETRY_READING,
                        source="telemetry_feed",
                        payload={
                            "asset_id": asset_id,
                            "min_reading": str(min_reading),
                            "max_reading": str(max_reading),
                            "last_reading": str(last_reading),
                            "sample_count": sample_count,
                            "timestamp": timestamp.isoformat(),
                        },
                    )
                )
                yield reading

            if self._running and self._tick_interval:
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self._tick_interval,
                    )
                except TimeoutError:
                    pass

    def get_latest_reading(self, asset_id: str) -> TelemetryReading | None:
        """Return the latest reading for ``asset_id``, if one has been generated."""
        return self._latest_readings.get(asset_id.strip().upper())

    def get_all_latest_readings(self) -> dict[str, TelemetryReading]:
        """Return a shallow snapshot of the latest readings."""
        return dict(self._latest_readings)

    @property
    def is_running(self) -> bool:
        """Whether the feed is currently generating readings."""
        return self._running


class WebSocketFeedAdapter:
    """Adapt a reconnecting JSON WebSocket stream into telemetry events."""

    def __init__(
        self,
        url: str,
        asset_ids: Sequence[str],
        event_bus: EventBus,
        reconnect_delay: float = 5.0,
    ) -> None:
        if reconnect_delay < 0 or not math.isfinite(reconnect_delay):
            raise ValueError("reconnect_delay must be finite and non-negative")
        self._url = url
        self._asset_ids = [asset_id.strip().upper() for asset_id in dict.fromkeys(asset_ids)]
        self._asset_set = set(self._asset_ids)
        self._event_bus = event_bus
        self._reconnect_delay = reconnect_delay
        self._running = False
        self._disconnect_event = asyncio.Event()
        self._websocket: Any | None = None

    async def connect(self) -> None:
        """Connect, consume valid readings, and reconnect after transport failures."""
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
                            json.dumps({"action": "subscribe", "asset_ids": self._asset_ids})
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
                            reading = self._parse_reading(data)
                            if reading is not None:
                                await self._event_bus.publish(
                                    DomainEvent(
                                        event_type=DispatchEventType.TELEMETRY_READING,
                                        source="websocket_feed",
                                        payload={
                                            "asset_id": reading.asset_id,
                                            "min_reading": str(reading.min_reading),
                                            "max_reading": str(reading.max_reading),
                                            "last_reading": str(reading.last_reading),
                                            "sample_count": reading.sample_count,
                                            "timestamp": reading.timestamp.isoformat(),
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

    def _parse_reading(self, data: Mapping[str, Any]) -> TelemetryReading | None:
        try:
            timestamp = _utc_datetime(data.get("timestamp"))
            asset_id_value = data["asset_id"]
            if not isinstance(asset_id_value, str):
                raise TypeError("asset_id must be a string")
            asset_id = asset_id_value.strip().upper()
            if asset_id not in self._asset_set:
                logger.warning("Ignoring reading for unsubscribed asset_id %s", asset_id)
                return None
            sample_count = data.get("sample_count", 0)
            if isinstance(sample_count, bool) or not isinstance(sample_count, int):
                raise TypeError("sample_count must be an integer")
            return TelemetryReading(
                asset_id=asset_id,
                min_reading=Decimal(str(data["min_reading"])),
                max_reading=Decimal(str(data["max_reading"])),
                last_reading=Decimal(str(data.get("last_reading", data["max_reading"]))),
                sample_count=sample_count,
                timestamp=timestamp,
            )
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            logger.warning("Failed to parse reading: %s", exc)
            return None

    async def disconnect(self) -> None:
        """Stop reconnecting and close the active socket, if present."""
        self._running = False
        self._disconnect_event.set()
        websocket = self._websocket
        if websocket is not None:
            await websocket.close()


__all__ = ["ReadingSimulator", "TelemetryFeed", "WebSocketFeedAdapter"]
