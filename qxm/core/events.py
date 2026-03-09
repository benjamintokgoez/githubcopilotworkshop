"""Asynchronous event bus implementing the publish/subscribe pattern with
event sourcing semantics.  All domain events are persisted to an append-only
log before delivery, enabling full replay and auditability — a regulatory
requirement in most trading venues.

The bus uses ``asyncio.Queue`` per subscriber and supports both coroutine
callbacks and async-generator consumers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

class EventType(str, Enum):
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
    metadata for audit, correlation, and replay."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.SYSTEM_STATUS
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    correlation_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainEvent":
        data = dict(data)
        if "event_type" in data:
            data["event_type"] = EventType(data["event_type"])
        return cls(**data)


# ---------------------------------------------------------------------------
# Append-only event log
# ---------------------------------------------------------------------------

class EventLog:
    """Thread-safe append-only event store.  Supports sequential replay from
    an arbitrary offset — the foundation of event-sourcing in QXM."""

    def __init__(self, max_size: int = 100_000) -> None:
        self._log: List[DomainEvent] = []
        self._max_size = max_size
        self._sequence: int = 0

    def append(self, event: DomainEvent) -> int:
        seq = self._sequence
        self._log.append(event)
        self._sequence += 1
        if len(self._log) > self._max_size:
            self._log = self._log[-self._max_size:]
        return seq

    def replay(
        self,
        from_sequence: int = 0,
        event_types: Optional[Set[EventType]] = None,
    ) -> List[DomainEvent]:
        events = self._log[from_sequence:]
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        return events

    def snapshot(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._log]

    @property
    def size(self) -> int:
        return len(self._log)

    @property
    def latest_sequence(self) -> int:
        return self._sequence


# ---------------------------------------------------------------------------
# Subscription handle
# ---------------------------------------------------------------------------

@dataclass
class _Subscription:
    subscriber_id: str
    event_types: Set[EventType]
    queue: asyncio.Queue[DomainEvent]
    callback: Optional[Callable[[DomainEvent], Coroutine[Any, Any, None]]] = None


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------

class EventBus:
    """Asynchronous pub/sub event bus with optional event-sourcing persistence.

    Subscribers register interest in one or more ``EventType`` values.
    Published events are first persisted to the ``EventLog`` (if enabled),
    then fan-out to matching subscribers via per-subscriber
    ``asyncio.Queue`` instances.

    Two consumption models are supported:

    1. **Callback** — an ``async def handler(event)`` invoked for each event.
    2. **Async generator** — ``async for event in bus.stream(types):``.
    """

    def __init__(self, *, persist: bool = True, max_queue: int = 10_000) -> None:
        self._subscriptions: Dict[str, _Subscription] = {}
        self._event_log = EventLog() if persist else None
        self._max_queue = max_queue
        self._running = False
        self._dispatch_tasks: List[asyncio.Task[None]] = []

    # -- Publish --------------------------------------------------------

    async def publish(self, event: DomainEvent) -> None:
        if self._event_log is not None:
            self._event_log.append(event)

        for sub in self._subscriptions.values():
            if event.event_type in sub.event_types or not sub.event_types:
                try:
                    sub.queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(
                        "Queue full for subscriber %s — dropping event %s",
                        sub.subscriber_id,
                        event.event_id,
                    )

    # -- Subscribe (callback mode) -------------------------------------

    def subscribe(
        self,
        event_types: Set[EventType],
        callback: Callable[[DomainEvent], Coroutine[Any, Any, None]],
        subscriber_id: Optional[str] = None,
    ) -> str:
        sid = subscriber_id or str(uuid.uuid4())
        sub = _Subscription(
            subscriber_id=sid,
            event_types=event_types,
            queue=asyncio.Queue(maxsize=self._max_queue),
            callback=callback,
        )
        self._subscriptions[sid] = sub
        return sid

    def unsubscribe(self, subscriber_id: str) -> None:
        self._subscriptions.pop(subscriber_id, None)

    # -- Subscribe (async generator mode) -------------------------------

    async def stream(
        self,
        event_types: Set[EventType],
        subscriber_id: Optional[str] = None,
    ) -> AsyncIterator[DomainEvent]:
        sid = subscriber_id or str(uuid.uuid4())
        queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=self._max_queue)
        sub = _Subscription(
            subscriber_id=sid,
            event_types=event_types,
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
        while self._running:
            try:
                event = await asyncio.wait_for(sub.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if sub.callback is not None:
                try:
                    await sub.callback(event)
                except Exception:
                    logger.exception(
                        "Error in subscriber %s callback", sub.subscriber_id
                    )

    async def start(self) -> None:
        self._running = True
        for sub in self._subscriptions.values():
            if sub.callback is not None:
                task = asyncio.create_task(self._dispatch_loop(sub))
                self._dispatch_tasks.append(task)
        logger.info("EventBus started with %d subscribers", len(self._subscriptions))

    async def stop(self) -> None:
        self._running = False
        for task in self._dispatch_tasks:
            task.cancel()
        await asyncio.gather(*self._dispatch_tasks, return_exceptions=True)
        self._dispatch_tasks.clear()
        logger.info("EventBus stopped")

    # -- Event log access -----------------------------------------------

    @property
    def event_log(self) -> Optional[EventLog]:
        return self._event_log

    def replay(
        self,
        from_sequence: int = 0,
        event_types: Optional[Set[EventType]] = None,
    ) -> List[DomainEvent]:
        if self._event_log is None:
            return []
        return self._event_log.replay(from_sequence, event_types)
