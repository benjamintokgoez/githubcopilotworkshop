"""Asynchronous event bus implementing the publish/subscribe pattern with
event-sourcing semantics.  Every domain event is appended to a bounded,
monotonically-sequenced log before delivery, enabling audit and bounded
replay.  The bus supports both coroutine callbacks and async-generator
consumers, and callbacks registered after the bus has started are wired up
immediately.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import (
    Any,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(dt: datetime) -> datetime:
    """Reject naive datetimes and normalise aware offsets to UTC."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError("datetime must be timezone-aware; naive datetimes are rejected")
    return dt.astimezone(UTC)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class EventType(StrEnum):
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"
    TRADE_EXECUTED = "TRADE_EXECUTED"
    POSITION_UPDATED = "POSITION_UPDATED"
    MARKET_DATA_TICK = "MARKET_DATA_TICK"
    RISK_BREACH = "RISK_BREACH"
    STRATEGY_SIGNAL = "STRATEGY_SIGNAL"
    SYSTEM_STATUS = "SYSTEM_STATUS"


# ---------------------------------------------------------------------------
# Event envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DomainEvent:
    """Immutable event envelope wrapping arbitrary payloads with mandatory
    metadata for audit, correlation, and replay.  ``timestamp`` is a
    timezone-aware UTC datetime."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.SYSTEM_STATUS
    timestamp: datetime = field(default_factory=_utcnow)
    source: str = ""
    correlation_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Enforce the aware-UTC invariant even for externally supplied values;
        # the dataclass is frozen, so normalise via object.__setattr__.
        object.__setattr__(self, "timestamp", _ensure_utc(self.timestamp))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainEvent:
        data = dict(data)
        if "event_type" in data:
            data["event_type"] = EventType(data["event_type"])
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


# ---------------------------------------------------------------------------
# Append-only event log
# ---------------------------------------------------------------------------


class EventLog:
    """Bounded append-only event store with monotonically increasing global
    sequence numbers.  When the log exceeds ``max_size`` the oldest events are
    evicted, but sequence numbers keep increasing so ``replay(from_sequence)``
    always returns events whose global sequence is ``>= from_sequence`` (any
    already-evicted range is simply unavailable)."""

    def __init__(self, max_size: int = 100_000) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self._log: list[DomainEvent] = []
        self._max_size = max_size
        self._base_sequence: int = 0  # global sequence of _log[0]
        self._next_sequence: int = 0  # global sequence to assign next append

    def append(self, event: DomainEvent) -> int:
        seq = self._next_sequence
        self._log.append(event)
        self._next_sequence += 1
        if len(self._log) > self._max_size:
            overflow = len(self._log) - self._max_size
            del self._log[:overflow]
            self._base_sequence += overflow
        return seq

    def replay(
        self,
        from_sequence: int = 0,
        event_types: set[EventType] | None = None,
    ) -> list[DomainEvent]:
        start = max(from_sequence, self._base_sequence) - self._base_sequence
        if start < 0:
            start = 0
        events = self._log[start:]
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        return events

    def snapshot(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._log]

    @property
    def size(self) -> int:
        return len(self._log)

    @property
    def base_sequence(self) -> int:
        return self._base_sequence

    @property
    def latest_sequence(self) -> int:
        return self._next_sequence


# ---------------------------------------------------------------------------
# Subscription handle
# ---------------------------------------------------------------------------


@dataclass
class _Subscription:
    subscriber_id: str
    event_types: set[EventType]
    queue: asyncio.Queue[DomainEvent]
    callback: Callable[[DomainEvent], Coroutine[Any, Any, None]] | None = None


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------


class EventBus:
    """Asynchronous pub/sub event bus with optional event-sourcing persistence.

    Subscribers register interest in one or more ``EventType`` values (an empty
    set means "all events").  Published events are first persisted to the
    ``EventLog`` (if enabled), then fanned out to matching subscribers via
    per-subscriber ``asyncio.Queue`` instances.

    Two consumption models are supported:

    1. **Callback** — an ``async def handler(event)`` invoked for each event.
       Callbacks are driven by a dispatch task; registering a callback after
       :meth:`start` immediately spawns its dispatch task.
    2. **Async generator** — ``async for event in bus.stream(types):``.
    """

    def __init__(self, *, persist: bool = True, max_queue: int = 10_000) -> None:
        if not isinstance(max_queue, int) or isinstance(max_queue, bool):
            raise TypeError("max_queue must be an int")
        if max_queue <= 0:
            raise ValueError("max_queue must be a positive integer")
        self._subscriptions: dict[str, _Subscription] = {}
        self._event_log = EventLog() if persist else None
        self._max_queue = max_queue
        self._running = False
        self._dispatch_tasks: dict[str, asyncio.Task[None]] = {}

    def _reserve_subscriber_id(self, subscriber_id: str | None) -> str:
        """Return a unique subscriber id, rejecting explicit collisions so a
        new subscription can never orphan an existing one's dispatch task."""
        if subscriber_id is None:
            return str(uuid.uuid4())
        if subscriber_id in self._subscriptions:
            raise ValueError(f"subscriber_id {subscriber_id!r} is already registered")
        return subscriber_id

    # -- Publish --------------------------------------------------------

    async def publish(self, event: DomainEvent) -> None:
        if self._event_log is not None:
            self._event_log.append(event)

        for sub in list(self._subscriptions.values()):
            if sub.event_types and event.event_type not in sub.event_types:
                continue
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                # Not silent: a full queue is a back-pressure signal we surface.
                logger.warning(
                    "Queue full for subscriber %s — dropping event %s (%s)",
                    sub.subscriber_id,
                    event.event_id,
                    event.event_type.value,
                )

    # -- Subscribe (callback mode) -------------------------------------

    def subscribe(
        self,
        event_types: set[EventType],
        callback: Callable[[DomainEvent], Coroutine[Any, Any, None]],
        subscriber_id: str | None = None,
    ) -> str:
        sid = self._reserve_subscriber_id(subscriber_id)
        sub = _Subscription(
            subscriber_id=sid,
            event_types=set(event_types),
            queue=asyncio.Queue(maxsize=self._max_queue),
            callback=callback,
        )
        self._subscriptions[sid] = sub
        if self._running:
            self._dispatch_tasks[sid] = asyncio.create_task(self._dispatch_loop(sub))
        return sid

    def unsubscribe(self, subscriber_id: str) -> None:
        self._subscriptions.pop(subscriber_id, None)
        task = self._dispatch_tasks.pop(subscriber_id, None)
        if task is not None:
            task.cancel()

    # -- Subscribe (async generator mode) -------------------------------

    async def stream(
        self,
        event_types: set[EventType],
        subscriber_id: str | None = None,
    ) -> AsyncIterator[DomainEvent]:
        sid = self._reserve_subscriber_id(subscriber_id)
        queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=self._max_queue)
        sub = _Subscription(
            subscriber_id=sid,
            event_types=set(event_types),
            queue=queue,
        )
        self._subscriptions[sid] = sub
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            self._subscriptions.pop(sid, None)

    # -- Dispatch loop (drives callback subscribers) --------------------

    async def _dispatch_loop(self, sub: _Subscription) -> None:
        # Drain remaining queued events on shutdown so no event is lost.
        while self._running or not sub.queue.empty():
            try:
                event = await asyncio.wait_for(sub.queue.get(), timeout=0.1)
            except TimeoutError:
                continue
            if sub.callback is not None:
                try:
                    await sub.callback(event)
                except Exception:
                    # Logged with traceback — never silently swallowed — and the
                    # loop keeps serving so one bad handler cannot stall others.
                    logger.exception(
                        "Error in subscriber %s callback for event %s",
                        sub.subscriber_id,
                        event.event_id,
                    )

    async def start(self) -> None:
        self._running = True
        for sid, sub in self._subscriptions.items():
            if sub.callback is not None and sid not in self._dispatch_tasks:
                self._dispatch_tasks[sid] = asyncio.create_task(self._dispatch_loop(sub))
        logger.info("EventBus started with %d subscribers", len(self._subscriptions))

    async def stop(self) -> None:
        self._running = False
        tasks = list(self._dispatch_tasks.values())
        # Loops exit once running is False and their queues are drained.
        await asyncio.gather(*tasks, return_exceptions=True)
        self._dispatch_tasks.clear()
        logger.info("EventBus stopped")

    # -- Event log access -----------------------------------------------

    @property
    def event_log(self) -> EventLog | None:
        return self._event_log

    @property
    def is_running(self) -> bool:
        return self._running

    def replay(
        self,
        from_sequence: int = 0,
        event_types: set[EventType] | None = None,
    ) -> list[DomainEvent]:
        if self._event_log is None:
            return []
        return self._event_log.replay(from_sequence, event_types)


__all__ = [
    "EventType",
    "DomainEvent",
    "EventLog",
    "EventBus",
]
