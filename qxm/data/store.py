"""Time-series persistence for simulated market data, trades, and instruments.

Built on SQLAlchemy 2.x typed ORM (``DeclarativeBase`` / ``Mapped``) with two
invariants that matter for a financial store:

* **Exact decimals.**  Prices and quantities are never stored as binary floats.
  They round-trip through :class:`DecimalText`, which persists the canonical
  ``str(Decimal)`` form, so ``Decimal("0.1")`` returns as ``Decimal("0.1")``.
* **Aware UTC timestamps.**  Naive datetimes are rejected on the way in, aware
  offsets are normalised to UTC, and rows read back from SQLite (which strips
  offsets) are re-tagged as UTC, so a naive value can never leak to callers.

Every operation runs in its own short-lived session/transaction; the store owns
no long-lived session.  :meth:`TimeSeriesStore.close` disposes the engine.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    TypeDecorator,
    create_engine,
    delete,
    func,
    select,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Dialect, Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

#: Hard ceiling applied to every bounded query, regardless of caller input.
MAX_QUERY_LIMIT = 10_000
#: Hard ceiling for instrument search results and query length.
MAX_SEARCH_LIMIT = 200
MAX_SEARCH_QUERY_LENGTH = 64
#: Column width for order ids, matching the API's client-supplied ``order_id``
#: contract (``qxm.api.schemas.ORDER_ID_MAX_LENGTH``).  Engine-generated ids are
#: 36-character UUIDs, but a client may supply anything up to this length.
ORDER_ID_COLUMN_LENGTH = 64

#: Sentinel marking a required instrument field in :func:`_field`.
_REQUIRED: Any = object()


# ---------------------------------------------------------------------------
# Column types
# ---------------------------------------------------------------------------


def _to_decimal(value: object, name: str) -> Decimal:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{name} must be a finite decimal")
        return value
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a decimal value, not a bool")
    if isinstance(value, float):
        raise TypeError(
            f"{name} must be a Decimal, int, or numeric string — binary floats "
            "are rejected to preserve exactness"
        )
    if isinstance(value, (int, str)):
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{name} is not a valid decimal: {value!r}") from exc
        if not result.is_finite():
            raise ValueError(f"{name} must be a finite decimal")
        return result
    raise TypeError(f"{name} must be a Decimal, int, or numeric string")


def ensure_utc(value: object, name: str = "timestamp") -> datetime:
    """Reject naive datetimes and normalise aware offsets to UTC."""
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{name} must be timezone-aware; naive datetimes are rejected")
    return value.astimezone(UTC)


class DecimalText(TypeDecorator[Decimal]):
    """Store :class:`~decimal.Decimal` as exact text.

    SQLite has no exact numeric type, so persisting the canonical decimal string
    is the only representation that survives a round trip unchanged.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return str(_to_decimal(value, "decimal column"))

    def process_result_value(self, value: Any, dialect: Dialect) -> Decimal | None:
        if value is None:
            return None
        return Decimal(value)


class UTCDateTime(TypeDecorator[datetime]):
    """Aware-UTC datetime column.

    Naive values are rejected on bind; values read back from a dialect that
    drops the offset (SQLite) are re-tagged as UTC.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return ensure_utc(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        stamp: datetime = value
        if stamp.tzinfo is None:
            return stamp.replace(tzinfo=UTC)
        return stamp.astimezone(UTC)


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Declarative base for the persistence layer."""


class TickRecord(Base):
    __tablename__ = "ticks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    bid: Mapped[Decimal] = mapped_column(DecimalText)
    ask: Mapped[Decimal] = mapped_column(DecimalText)
    last: Mapped[Decimal] = mapped_column(DecimalText)
    volume: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class OHLCRecord(Base):
    __tablename__ = "ohlc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    interval: Mapped[str] = mapped_column(String(10), index=True)
    open: Mapped[Decimal] = mapped_column(DecimalText)
    high: Mapped[Decimal] = mapped_column(DecimalText)
    low: Mapped[Decimal] = mapped_column(DecimalText)
    close: Mapped[Decimal] = mapped_column(DecimalText)
    volume: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class TradeRecord(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    buy_order_id: Mapped[str] = mapped_column(String(ORDER_ID_COLUMN_LENGTH))
    sell_order_id: Mapped[str] = mapped_column(String(ORDER_ID_COLUMN_LENGTH))
    price: Mapped[Decimal] = mapped_column(DecimalText)
    quantity: Mapped[Decimal] = mapped_column(DecimalText)
    buyer_client_id: Mapped[str] = mapped_column(String(64), index=True)
    seller_client_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class InstrumentRecord(Base):
    __tablename__ = "instruments"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    instrument_type: Mapped[str] = mapped_column(String(16))
    currency: Mapped[str] = mapped_column(String(3))
    exchange: Mapped[str] = mapped_column(String(32))
    tick_size: Mapped[Decimal] = mapped_column(DecimalText)
    lot_size: Mapped[Decimal] = mapped_column(DecimalText)


# ---------------------------------------------------------------------------
# Detached read models — safe to use after the session closes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TickRow:
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume: int
    timestamp: datetime


@dataclass(frozen=True)
class OHLCRow:
    symbol: str
    interval: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    timestamp: datetime


@dataclass(frozen=True)
class TradeRow:
    trade_id: str
    symbol: str
    buy_order_id: str
    sell_order_id: str
    price: Decimal
    quantity: Decimal
    buyer_client_id: str
    seller_client_id: str
    timestamp: datetime


@dataclass(frozen=True)
class InstrumentRow:
    symbol: str
    name: str
    instrument_type: str
    currency: str
    exchange: str
    tick_size: Decimal
    lot_size: Decimal

    def as_dict(self) -> dict[str, str]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "instrument_type": self.instrument_type,
            "currency": self.currency,
            "exchange": self.exchange,
            "tick_size": str(self.tick_size),
            "lot_size": str(self.lot_size),
        }


def _validate_symbol(symbol: str) -> str:
    if not isinstance(symbol, str):
        raise TypeError("symbol must be a string")
    normalised = symbol.strip().upper()
    if not normalised:
        raise ValueError("symbol must be a non-blank string")
    return normalised


def _validate_limit(limit: int, ceiling: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit must be an int")
    if limit <= 0:
        raise ValueError("limit must be positive")
    return min(limit, ceiling)


def _validate_volume(volume: int) -> int:
    if isinstance(volume, bool) or not isinstance(volume, int):
        raise TypeError("volume must be an int")
    if volume < 0:
        raise ValueError("volume must not be negative")
    return volume


def _escape_like(term: str) -> str:
    """Escape LIKE wildcards so user input matches literally."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _is_memory_url(db_url: str) -> bool:
    return db_url.startswith("sqlite") and (
        ":memory:" in db_url or db_url in ("sqlite://", "sqlite+pysqlite://")
    )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class TimeSeriesStore:
    """Persistence layer for simulated ticks, OHLC bars, trades, instruments."""

    def __init__(
        self,
        db_url: str = "sqlite:///data/sample.db",
        *,
        echo: bool = False,
        create_tables: bool = True,
    ) -> None:
        if not isinstance(db_url, str) or not db_url.strip():
            raise ValueError("db_url must be a non-blank string")
        self._db_url = db_url
        kwargs: dict[str, Any] = {"echo": echo, "future": True}
        if _is_memory_url(db_url):
            # A shared, single connection keeps an in-memory database alive
            # across sessions and threads (TestClient runs handlers in a
            # worker thread).
            kwargs["poolclass"] = StaticPool
            kwargs["connect_args"] = {"check_same_thread": False}
        elif db_url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        self._engine: Engine = create_engine(db_url, **kwargs)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False, future=True)
        self._closed = False
        if create_tables:
            Base.metadata.create_all(self._engine)

    # -- Session plumbing -------------------------------------------------

    @property
    def engine(self) -> Engine:
        return self._engine

    @property
    def db_url(self) -> str:
        return self._db_url

    @property
    def is_closed(self) -> bool:
        return self._closed

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Yield a per-operation session wrapped in a single transaction."""
        if self._closed:
            raise RuntimeError("TimeSeriesStore is closed")
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self) -> None:
        """Dispose the engine.  Subsequent operations raise ``RuntimeError``."""
        if self._closed:
            return
        self._closed = True
        self._engine.dispose()

    def __enter__(self) -> TimeSeriesStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- Ticks -------------------------------------------------------------

    def insert_tick(
        self,
        symbol: str,
        bid: Decimal | int | str,
        ask: Decimal | int | str,
        last: Decimal | int | str,
        volume: int,
        timestamp: datetime,
    ) -> None:
        record = TickRecord(
            symbol=_validate_symbol(symbol),
            bid=_to_decimal(bid, "bid"),
            ask=_to_decimal(ask, "ask"),
            last=_to_decimal(last, "last"),
            volume=_validate_volume(volume),
            timestamp=ensure_utc(timestamp),
        )
        with self.session() as session:
            session.add(record)

    def insert_ticks_batch(self, ticks: Sequence[Mapping[str, Any]]) -> int:
        """Insert many ticks in one transaction and return the row count."""
        records = [
            TickRecord(
                symbol=_validate_symbol(tick["symbol"]),
                bid=_to_decimal(tick["bid"], "bid"),
                ask=_to_decimal(tick["ask"], "ask"),
                last=_to_decimal(tick["last"], "last"),
                volume=_validate_volume(tick["volume"]),
                timestamp=ensure_utc(tick["timestamp"]),
            )
            for tick in ticks
        ]
        if not records:
            return 0
        with self.session() as session:
            session.add_all(records)
        return len(records)

    def get_ticks(
        self,
        symbol: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> list[TickRow]:
        """Return ticks newest-first within the inclusive ``[start, end]`` range."""
        stmt = select(TickRecord).where(TickRecord.symbol == _validate_symbol(symbol))
        if start is not None:
            stmt = stmt.where(TickRecord.timestamp >= ensure_utc(start, "start"))
        if end is not None:
            stmt = stmt.where(TickRecord.timestamp <= ensure_utc(end, "end"))
        stmt = stmt.order_by(TickRecord.timestamp.desc(), TickRecord.id.desc())
        stmt = stmt.limit(_validate_limit(limit, MAX_QUERY_LIMIT))
        with self.session() as session:
            rows = session.execute(stmt).scalars().all()
        return [
            TickRow(
                symbol=row.symbol,
                bid=row.bid,
                ask=row.ask,
                last=row.last,
                volume=row.volume,
                timestamp=row.timestamp,
            )
            for row in rows
        ]

    # -- OHLC --------------------------------------------------------------

    def insert_ohlc(
        self,
        symbol: str,
        interval: str,
        open_: Decimal | int | str,
        high: Decimal | int | str,
        low: Decimal | int | str,
        close: Decimal | int | str,
        volume: int,
        timestamp: datetime,
    ) -> None:
        if not isinstance(interval, str) or not interval.strip():
            raise ValueError("interval must be a non-blank string")
        record = OHLCRecord(
            symbol=_validate_symbol(symbol),
            interval=interval.strip(),
            open=_to_decimal(open_, "open"),
            high=_to_decimal(high, "high"),
            low=_to_decimal(low, "low"),
            close=_to_decimal(close, "close"),
            volume=_validate_volume(volume),
            timestamp=ensure_utc(timestamp),
        )
        with self.session() as session:
            session.add(record)

    def get_ohlc(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 500,
    ) -> list[OHLCRow]:
        stmt = (
            select(OHLCRecord)
            .where(
                OHLCRecord.symbol == _validate_symbol(symbol),
                OHLCRecord.interval == interval,
            )
            .order_by(OHLCRecord.timestamp.desc(), OHLCRecord.id.desc())
            .limit(_validate_limit(limit, MAX_QUERY_LIMIT))
        )
        with self.session() as session:
            rows = session.execute(stmt).scalars().all()
        return [
            OHLCRow(
                symbol=row.symbol,
                interval=row.interval,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
                timestamp=row.timestamp,
            )
            for row in rows
        ]

    # -- Trades ------------------------------------------------------------

    def insert_trade(
        self,
        trade_id: str,
        symbol: str,
        buy_order_id: str,
        sell_order_id: str,
        price: Decimal | int | str,
        quantity: Decimal | int | str,
        buyer_client_id: str,
        seller_client_id: str,
        timestamp: datetime,
    ) -> None:
        """Persist a trade.  A duplicate ``trade_id`` surfaces as an
        :class:`sqlalchemy.exc.IntegrityError` — it is never swallowed."""
        record = _trade_record(
            {
                "trade_id": trade_id,
                "symbol": symbol,
                "buy_order_id": buy_order_id,
                "sell_order_id": sell_order_id,
                "price": price,
                "quantity": quantity,
                "buyer_client_id": buyer_client_id,
                "seller_client_id": seller_client_id,
                "timestamp": timestamp,
            }
        )
        with self.session() as session:
            session.add(record)

    def insert_trades(self, trades: Sequence[Mapping[str, Any]]) -> int:
        """Persist a batch of trades in one transaction; returns the row count.

        All rows are validated before the transaction opens, so a malformed
        entry cannot leave a half-written batch behind.  A duplicate
        ``trade_id`` surfaces as an :class:`sqlalchemy.exc.IntegrityError` and
        rolls the whole batch back.
        """
        records = [_trade_record(trade) for trade in trades]
        if not records:
            return 0
        with self.session() as session:
            session.add_all(records)
        return len(records)

    def get_trades(
        self,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[TradeRow]:
        stmt = select(TradeRecord)
        if symbol is not None:
            stmt = stmt.where(TradeRecord.symbol == _validate_symbol(symbol))
        stmt = stmt.order_by(TradeRecord.timestamp.desc(), TradeRecord.id.desc())
        stmt = stmt.limit(_validate_limit(limit, MAX_QUERY_LIMIT))
        with self.session() as session:
            rows = session.execute(stmt).scalars().all()
        return [
            TradeRow(
                trade_id=row.trade_id,
                symbol=row.symbol,
                buy_order_id=row.buy_order_id,
                sell_order_id=row.sell_order_id,
                price=row.price,
                quantity=row.quantity,
                buyer_client_id=row.buyer_client_id,
                seller_client_id=row.seller_client_id,
                timestamp=row.timestamp,
            )
            for row in rows
        ]

    # -- Instruments -------------------------------------------------------

    def seed_instruments(self, instruments: Sequence[Mapping[str, Any]] | Mapping[str, Any]) -> int:
        """Insert or update instrument reference rows; returns the row count.

        Accepts mappings or any object exposing the instrument attributes
        (e.g. :class:`qxm.core.models.Instrument`).
        """
        items = (
            list(instruments.values()) if isinstance(instruments, Mapping) else list(instruments)
        )
        payloads: list[dict[str, Any]] = []
        for item in items:
            payloads.append(
                {
                    "symbol": _validate_symbol(_field(item, "symbol")),
                    "name": str(_field(item, "name")),
                    "instrument_type": _enum_value(_field(item, "instrument_type")),
                    "currency": str(_field(item, "currency", "USD")),
                    "exchange": str(_field(item, "exchange", "XQXM")),
                    "tick_size": _to_decimal(_field(item, "tick_size"), "tick_size"),
                    "lot_size": _to_decimal(_field(item, "lot_size", 1), "lot_size"),
                }
            )
        if not payloads:
            return 0
        with self.session() as session:
            for payload in payloads:
                stmt = sqlite_insert(InstrumentRecord).values(**payload)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[InstrumentRecord.symbol],
                    set_={
                        key: payload[key]
                        for key in (
                            "name",
                            "instrument_type",
                            "currency",
                            "exchange",
                            "tick_size",
                            "lot_size",
                        )
                    },
                )
                session.execute(stmt)
        return len(payloads)

    def get_instrument(self, symbol: str) -> InstrumentRow | None:
        stmt = select(InstrumentRecord).where(InstrumentRecord.symbol == _validate_symbol(symbol))
        with self.session() as session:
            row = session.execute(stmt).scalar_one_or_none()
        return _instrument_row(row) if row is not None else None

    def search_instruments(self, query: str, limit: int = 20) -> list[InstrumentRow]:
        """Case-insensitive substring search over symbol and name.

        The term is bound as a parameter and its LIKE wildcards are escaped, so
        SQL metacharacters (quotes, ``%``, ``--``, ``;``) are matched literally
        and are inert.
        """
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        term = query.strip()
        if not term:
            raise ValueError("query must be a non-blank string")
        if len(term) > MAX_SEARCH_QUERY_LENGTH:
            raise ValueError(f"query must be at most {MAX_SEARCH_QUERY_LENGTH} characters")
        pattern = f"%{_escape_like(term)}%"
        stmt = (
            select(InstrumentRecord)
            .where(
                InstrumentRecord.symbol.ilike(pattern, escape="\\")
                | InstrumentRecord.name.ilike(pattern, escape="\\")
            )
            .order_by(InstrumentRecord.symbol)
            .limit(_validate_limit(limit, MAX_SEARCH_LIMIT))
        )
        with self.session() as session:
            rows = session.execute(stmt).scalars().all()
        return [_instrument_row(row) for row in rows]

    def list_instruments(self, limit: int = 100) -> list[InstrumentRow]:
        stmt = (
            select(InstrumentRecord)
            .order_by(InstrumentRecord.symbol)
            .limit(_validate_limit(limit, MAX_SEARCH_LIMIT))
        )
        with self.session() as session:
            rows = session.execute(stmt).scalars().all()
        return [_instrument_row(row) for row in rows]

    def clear_instruments(self) -> int:
        """Delete every instrument row and return how many were removed."""
        counter = select(func.count()).select_from(InstrumentRecord)
        with self.session() as session:
            removed = int(session.execute(counter).scalar_one())
            session.execute(delete(InstrumentRecord))
        return removed

    # -- Counts ------------------------------------------------------------

    def count_ticks(self, symbol: str | None = None) -> int:
        return self._count(TickRecord, TickRecord.symbol, symbol)

    def count_trades(self, symbol: str | None = None) -> int:
        return self._count(TradeRecord, TradeRecord.symbol, symbol)

    def count_instruments(self) -> int:
        return self._count(InstrumentRecord, InstrumentRecord.symbol, None)

    def _count(self, model: type[Base], column: Any, symbol: str | None) -> int:
        stmt = select(func.count()).select_from(model)
        if symbol is not None:
            stmt = stmt.where(column == _validate_symbol(symbol))
        with self.session() as session:
            return int(session.execute(stmt).scalar_one())

    def __repr__(self) -> str:
        return f"TimeSeriesStore(url={self._db_url!r}, closed={self._closed})"


def _field(item: Any, name: str, default: Any = _REQUIRED) -> Any:
    """Read ``name`` from a mapping or attribute-bearing object."""
    if isinstance(item, Mapping):
        if name in item:
            return item[name]
    elif hasattr(item, name):
        return getattr(item, name)
    if default is _REQUIRED:
        raise KeyError(f"instrument definition is missing required field {name!r}")
    return default


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _trade_record(trade: Mapping[str, Any]) -> TradeRecord:
    """Validate one trade payload and build its ORM record."""
    trade_id = trade.get("trade_id")
    if not isinstance(trade_id, str) or not trade_id.strip():
        raise ValueError("trade_id must be a non-blank string")
    for name in ("buy_order_id", "sell_order_id", "buyer_client_id", "seller_client_id"):
        value = trade.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-blank string")
    return TradeRecord(
        trade_id=trade_id,
        symbol=_validate_symbol(trade["symbol"]),
        buy_order_id=trade["buy_order_id"],
        sell_order_id=trade["sell_order_id"],
        price=_to_decimal(trade["price"], "price"),
        quantity=_to_decimal(trade["quantity"], "quantity"),
        buyer_client_id=trade["buyer_client_id"],
        seller_client_id=trade["seller_client_id"],
        timestamp=ensure_utc(trade["timestamp"]),
    )


def _instrument_row(record: InstrumentRecord) -> InstrumentRow:
    return InstrumentRow(
        symbol=record.symbol,
        name=record.name,
        instrument_type=record.instrument_type,
        currency=record.currency,
        exchange=record.exchange,
        tick_size=record.tick_size,
        lot_size=record.lot_size,
    )


__all__ = [
    "Base",
    "DecimalText",
    "UTCDateTime",
    "TickRecord",
    "OHLCRecord",
    "TradeRecord",
    "InstrumentRecord",
    "TickRow",
    "OHLCRow",
    "TradeRow",
    "InstrumentRow",
    "TimeSeriesStore",
    "ensure_utc",
    "MAX_QUERY_LIMIT",
    "MAX_SEARCH_LIMIT",
    "MAX_SEARCH_QUERY_LENGTH",
    "ORDER_ID_COLUMN_LENGTH",
]
