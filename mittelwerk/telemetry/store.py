"""Time-series persistence for synthetic telemetry, interval bars, assignments, and equipment.

Built on SQLAlchemy 2.x typed ORM (``DeclarativeBase`` / ``Mapped``) with two
invariants that matter for this operational store:

* **Exact decimals.** Readings, rates, and hours are never stored as binary
  floats. They round-trip through :class:`DecimalText`, which persists the
  canonical ``str(Decimal)`` form, so ``Decimal("0.1")`` returns as
  ``Decimal("0.1")``.
* **Aware UTC timestamps.** Naive datetimes are rejected on the way in, aware
  offsets are normalised to UTC, and rows read back from SQLite (which strips
  offsets) are re-tagged as UTC, so a naive value can never leak to callers.

Every operation runs in its own short-lived session/transaction; the store owns
no long-lived session. :meth:`TelemetryStore.close` disposes the engine.
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
#: Hard ceiling for equipment search results and query length.
MAX_SEARCH_LIMIT = 200
MAX_SEARCH_QUERY_LENGTH = 64
#: Column width for work-order ids, matching the API's client-supplied
#: ``work_order_id`` contract (``mittelwerk.api.schemas.WORK_ORDER_ID_MAX_LENGTH``).
#: Engine-generated ids are 36-character UUIDs, but a client may supply
#: anything up to this length.
WORK_ORDER_ID_COLUMN_LENGTH = 64

#: Sentinel marking a required equipment field in :func:`_field`.
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
    """Store :class:`~decimal.Decimal` as exact text."""

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
    """Aware-UTC datetime column."""

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


class ReadingRecord(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(32), index=True)
    min_reading: Mapped[Decimal] = mapped_column(DecimalText)
    max_reading: Mapped[Decimal] = mapped_column(DecimalText)
    last_reading: Mapped[Decimal] = mapped_column(DecimalText)
    sample_count: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class IntervalRecord(Base):
    __tablename__ = "intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(32), index=True)
    interval: Mapped[str] = mapped_column(String(10), index=True)
    open_reading: Mapped[Decimal] = mapped_column(DecimalText)
    high_reading: Mapped[Decimal] = mapped_column(DecimalText)
    low_reading: Mapped[Decimal] = mapped_column(DecimalText)
    close_reading: Mapped[Decimal] = mapped_column(DecimalText)
    sample_count: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class AssignmentRecord(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    asset_id: Mapped[str] = mapped_column(String(32), index=True)
    requester_work_order_id: Mapped[str] = mapped_column(String(WORK_ORDER_ID_COLUMN_LENGTH))
    provider_work_order_id: Mapped[str] = mapped_column(String(WORK_ORDER_ID_COLUMN_LENGTH))
    hourly_rate: Mapped[Decimal] = mapped_column(DecimalText)
    hours: Mapped[Decimal] = mapped_column(DecimalText)
    requester_organization_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_organization_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class EquipmentRecord(Base):
    __tablename__ = "equipment"

    asset_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    equipment_type: Mapped[str] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3))
    site_code: Mapped[str] = mapped_column(String(32))
    hourly_service_rate: Mapped[Decimal] = mapped_column(DecimalText)
    rate_increment: Mapped[Decimal] = mapped_column(DecimalText)
    hour_lot_size: Mapped[Decimal] = mapped_column(DecimalText)


# ---------------------------------------------------------------------------
# Detached read models — safe to use after the session closes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadingRow:
    asset_id: str
    min_reading: Decimal
    max_reading: Decimal
    last_reading: Decimal
    sample_count: int
    timestamp: datetime


@dataclass(frozen=True)
class IntervalRow:
    asset_id: str
    interval: str
    open_reading: Decimal
    high_reading: Decimal
    low_reading: Decimal
    close_reading: Decimal
    sample_count: int
    timestamp: datetime


@dataclass(frozen=True)
class AssignmentRow:
    assignment_id: str
    asset_id: str
    requester_work_order_id: str
    provider_work_order_id: str
    hourly_rate: Decimal
    hours: Decimal
    requester_organization_id: str
    provider_organization_id: str
    timestamp: datetime


@dataclass(frozen=True)
class EquipmentRow:
    asset_id: str
    name: str
    equipment_type: str
    currency: str
    site_code: str
    hourly_service_rate: Decimal
    rate_increment: Decimal
    hour_lot_size: Decimal

    def as_dict(self) -> dict[str, str]:
        return {
            "asset_id": self.asset_id,
            "name": self.name,
            "equipment_type": self.equipment_type,
            "currency": self.currency,
            "site_code": self.site_code,
            "hourly_service_rate": str(self.hourly_service_rate),
            "rate_increment": str(self.rate_increment),
            "hour_lot_size": str(self.hour_lot_size),
        }


def _validate_asset_id(asset_id: str) -> str:
    if not isinstance(asset_id, str):
        raise TypeError("asset_id must be a string")
    normalised = asset_id.strip().upper()
    if not normalised:
        raise ValueError("asset_id must be a non-blank string")
    return normalised


def _validate_limit(limit: int, ceiling: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit must be an int")
    if limit <= 0:
        raise ValueError("limit must be positive")
    return min(limit, ceiling)


def _validate_sample_count(sample_count: int) -> int:
    if isinstance(sample_count, bool) or not isinstance(sample_count, int):
        raise TypeError("sample_count must be an int")
    if sample_count < 0:
        raise ValueError("sample_count must not be negative")
    return sample_count


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


class TelemetryStore:
    """Persistence layer for simulated readings, interval bars, assignments, and equipment."""

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
            raise RuntimeError("TelemetryStore is closed")
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
        """Dispose the engine. Subsequent operations raise ``RuntimeError``."""
        if self._closed:
            return
        self._closed = True
        self._engine.dispose()

    def __enter__(self) -> TelemetryStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- Readings ----------------------------------------------------------

    def insert_reading(
        self,
        asset_id: str,
        min_reading: Decimal | int | str,
        max_reading: Decimal | int | str,
        last_reading: Decimal | int | str,
        sample_count: int,
        timestamp: datetime,
    ) -> None:
        record = ReadingRecord(
            asset_id=_validate_asset_id(asset_id),
            min_reading=_to_decimal(min_reading, "min_reading"),
            max_reading=_to_decimal(max_reading, "max_reading"),
            last_reading=_to_decimal(last_reading, "last_reading"),
            sample_count=_validate_sample_count(sample_count),
            timestamp=ensure_utc(timestamp),
        )
        with self.session() as session:
            session.add(record)

    def insert_readings(self, readings: Sequence[Mapping[str, Any]]) -> int:
        """Insert many readings in one transaction and return the row count."""
        records = [
            ReadingRecord(
                asset_id=_validate_asset_id(reading["asset_id"]),
                min_reading=_to_decimal(reading["min_reading"], "min_reading"),
                max_reading=_to_decimal(reading["max_reading"], "max_reading"),
                last_reading=_to_decimal(reading["last_reading"], "last_reading"),
                sample_count=_validate_sample_count(reading["sample_count"]),
                timestamp=ensure_utc(reading["timestamp"]),
            )
            for reading in readings
        ]
        if not records:
            return 0
        with self.session() as session:
            session.add_all(records)
        return len(records)

    def get_readings(
        self,
        asset_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> list[ReadingRow]:
        """Return readings newest-first within the inclusive ``[start, end]`` range."""
        stmt = select(ReadingRecord).where(ReadingRecord.asset_id == _validate_asset_id(asset_id))
        if start is not None:
            stmt = stmt.where(ReadingRecord.timestamp >= ensure_utc(start, "start"))
        if end is not None:
            stmt = stmt.where(ReadingRecord.timestamp <= ensure_utc(end, "end"))
        stmt = stmt.order_by(ReadingRecord.timestamp.desc(), ReadingRecord.id.desc())
        stmt = stmt.limit(_validate_limit(limit, MAX_QUERY_LIMIT))
        with self.session() as session:
            rows = session.execute(stmt).scalars().all()
        return [
            ReadingRow(
                asset_id=row.asset_id,
                min_reading=row.min_reading,
                max_reading=row.max_reading,
                last_reading=row.last_reading,
                sample_count=row.sample_count,
                timestamp=row.timestamp,
            )
            for row in rows
        ]

    def latest_reading(self, asset_id: str) -> ReadingRow | None:
        rows = self.get_readings(asset_id, limit=1)
        return rows[0] if rows else None

    # -- Intervals ---------------------------------------------------------

    def insert_interval(
        self,
        asset_id: str,
        interval: str,
        open_reading: Decimal | int | str,
        high_reading: Decimal | int | str,
        low_reading: Decimal | int | str,
        close_reading: Decimal | int | str,
        sample_count: int,
        timestamp: datetime,
    ) -> None:
        if not isinstance(interval, str) or not interval.strip():
            raise ValueError("interval must be a non-blank string")
        record = IntervalRecord(
            asset_id=_validate_asset_id(asset_id),
            interval=interval.strip(),
            open_reading=_to_decimal(open_reading, "open_reading"),
            high_reading=_to_decimal(high_reading, "high_reading"),
            low_reading=_to_decimal(low_reading, "low_reading"),
            close_reading=_to_decimal(close_reading, "close_reading"),
            sample_count=_validate_sample_count(sample_count),
            timestamp=ensure_utc(timestamp),
        )
        with self.session() as session:
            session.add(record)

    def insert_intervals(self, intervals: Sequence[Mapping[str, Any]]) -> int:
        """Insert many interval bars in one transaction and return the row count."""
        records: list[IntervalRecord] = []
        for interval_row in intervals:
            interval = interval_row["interval"]
            if not isinstance(interval, str) or not interval.strip():
                raise ValueError("interval must be a non-blank string")
            records.append(
                IntervalRecord(
                    asset_id=_validate_asset_id(interval_row["asset_id"]),
                    interval=interval.strip(),
                    open_reading=_to_decimal(interval_row["open_reading"], "open_reading"),
                    high_reading=_to_decimal(interval_row["high_reading"], "high_reading"),
                    low_reading=_to_decimal(interval_row["low_reading"], "low_reading"),
                    close_reading=_to_decimal(interval_row["close_reading"], "close_reading"),
                    sample_count=_validate_sample_count(interval_row["sample_count"]),
                    timestamp=ensure_utc(interval_row["timestamp"]),
                )
            )
        if not records:
            return 0
        with self.session() as session:
            session.add_all(records)
        return len(records)

    def get_intervals(
        self,
        asset_id: str,
        interval: str = "1m",
        limit: int = 500,
    ) -> list[IntervalRow]:
        stmt = (
            select(IntervalRecord)
            .where(
                IntervalRecord.asset_id == _validate_asset_id(asset_id),
                IntervalRecord.interval == interval,
            )
            .order_by(IntervalRecord.timestamp.desc(), IntervalRecord.id.desc())
            .limit(_validate_limit(limit, MAX_QUERY_LIMIT))
        )
        with self.session() as session:
            rows = session.execute(stmt).scalars().all()
        return [
            IntervalRow(
                asset_id=row.asset_id,
                interval=row.interval,
                open_reading=row.open_reading,
                high_reading=row.high_reading,
                low_reading=row.low_reading,
                close_reading=row.close_reading,
                sample_count=row.sample_count,
                timestamp=row.timestamp,
            )
            for row in rows
        ]

    # -- Assignments -------------------------------------------------------

    def insert_assignment(
        self,
        assignment_id: str,
        asset_id: str,
        requester_work_order_id: str,
        provider_work_order_id: str,
        hourly_rate: Decimal | int | str,
        hours: Decimal | int | str,
        requester_organization_id: str,
        provider_organization_id: str,
        timestamp: datetime,
    ) -> None:
        record = _assignment_record(
            {
                "assignment_id": assignment_id,
                "asset_id": asset_id,
                "requester_work_order_id": requester_work_order_id,
                "provider_work_order_id": provider_work_order_id,
                "hourly_rate": hourly_rate,
                "hours": hours,
                "requester_organization_id": requester_organization_id,
                "provider_organization_id": provider_organization_id,
                "timestamp": timestamp,
            }
        )
        with self.session() as session:
            session.add(record)

    def insert_assignments(self, assignments: Sequence[Mapping[str, Any]]) -> int:
        """Persist a batch of assignments in one transaction; returns the row count."""
        records = [_assignment_record(assignment) for assignment in assignments]
        if not records:
            return 0
        with self.session() as session:
            session.add_all(records)
        return len(records)

    def get_assignments(
        self,
        asset_id: str | None = None,
        limit: int = 100,
    ) -> list[AssignmentRow]:
        stmt = select(AssignmentRecord)
        if asset_id is not None:
            stmt = stmt.where(AssignmentRecord.asset_id == _validate_asset_id(asset_id))
        stmt = stmt.order_by(AssignmentRecord.timestamp.desc(), AssignmentRecord.id.desc())
        stmt = stmt.limit(_validate_limit(limit, MAX_QUERY_LIMIT))
        with self.session() as session:
            rows = session.execute(stmt).scalars().all()
        return [
            AssignmentRow(
                assignment_id=row.assignment_id,
                asset_id=row.asset_id,
                requester_work_order_id=row.requester_work_order_id,
                provider_work_order_id=row.provider_work_order_id,
                hourly_rate=row.hourly_rate,
                hours=row.hours,
                requester_organization_id=row.requester_organization_id,
                provider_organization_id=row.provider_organization_id,
                timestamp=row.timestamp,
            )
            for row in rows
        ]

    # -- Equipment ---------------------------------------------------------

    def upsert_equipment(self, equipment: Mapping[str, Any] | Any) -> None:
        self.upsert_equipments([equipment])

    def upsert_equipments(self, equipment: Sequence[Mapping[str, Any]] | Mapping[str, Any]) -> int:
        """Insert or update equipment reference rows; returns the row count."""
        items = list(equipment.values()) if isinstance(equipment, Mapping) else list(equipment)
        payloads: list[dict[str, Any]] = []
        for item in items:
            payloads.append(
                {
                    "asset_id": _validate_asset_id(_field(item, "asset_id")),
                    "name": str(_field(item, "name")),
                    "equipment_type": _enum_value(_field(item, "equipment_type")),
                    "currency": str(_field(item, "currency", "EUR")),
                    "site_code": str(_field(item, "site_code", "MW-HQ")),
                    "hourly_service_rate": _to_decimal(
                        _field(item, "hourly_service_rate"),
                        "hourly_service_rate",
                    ),
                    "rate_increment": _to_decimal(
                        _field(item, "rate_increment", Decimal("0.50")),
                        "rate_increment",
                    ),
                    "hour_lot_size": _to_decimal(
                        _field(item, "hour_lot_size", Decimal("0.25")),
                        "hour_lot_size",
                    ),
                }
            )
        if not payloads:
            return 0
        with self.session() as session:
            for payload in payloads:
                stmt = sqlite_insert(EquipmentRecord).values(**payload)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[EquipmentRecord.asset_id],
                    set_={
                        key: payload[key]
                        for key in (
                            "name",
                            "equipment_type",
                            "currency",
                            "site_code",
                            "hourly_service_rate",
                            "rate_increment",
                            "hour_lot_size",
                        )
                    },
                )
                session.execute(stmt)
        return len(payloads)

    def get_equipment(self, asset_id: str) -> EquipmentRow | None:
        stmt = select(EquipmentRecord).where(
            EquipmentRecord.asset_id == _validate_asset_id(asset_id)
        )
        with self.session() as session:
            row = session.execute(stmt).scalar_one_or_none()
        return _equipment_row(row) if row is not None else None

    def search_equipment(self, query: str, limit: int = 20) -> list[EquipmentRow]:
        """Case-insensitive substring search over asset_id and name."""
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        term = query.strip()
        if not term:
            raise ValueError("query must be a non-blank string")
        if len(term) > MAX_SEARCH_QUERY_LENGTH:
            raise ValueError(f"query must be at most {MAX_SEARCH_QUERY_LENGTH} characters")
        pattern = f"%{_escape_like(term)}%"
        stmt = (
            select(EquipmentRecord)
            .where(
                EquipmentRecord.asset_id.ilike(pattern, escape="\\")
                | EquipmentRecord.name.ilike(pattern, escape="\\")
            )
            .order_by(EquipmentRecord.asset_id)
            .limit(_validate_limit(limit, MAX_SEARCH_LIMIT))
        )
        with self.session() as session:
            rows = session.execute(stmt).scalars().all()
        return [_equipment_row(row) for row in rows]

    def list_equipment(self, limit: int = 100) -> list[EquipmentRow]:
        stmt = (
            select(EquipmentRecord)
            .order_by(EquipmentRecord.asset_id)
            .limit(_validate_limit(limit, MAX_SEARCH_LIMIT))
        )
        with self.session() as session:
            rows = session.execute(stmt).scalars().all()
        return [_equipment_row(row) for row in rows]

    def clear_equipment(self) -> int:
        """Delete every equipment row and return how many were removed."""
        counter = select(func.count()).select_from(EquipmentRecord)
        with self.session() as session:
            removed = int(session.execute(counter).scalar_one())
            session.execute(delete(EquipmentRecord))
        return removed

    # -- Counts ------------------------------------------------------------

    def count_readings(self, asset_id: str | None = None) -> int:
        return self._count(ReadingRecord, ReadingRecord.asset_id, asset_id)

    def count_assignments(self, asset_id: str | None = None) -> int:
        return self._count(AssignmentRecord, AssignmentRecord.asset_id, asset_id)

    def count_equipment(self) -> int:
        return self._count(EquipmentRecord, EquipmentRecord.asset_id, None)

    def _count(self, model: type[Base], column: Any, asset_id: str | None) -> int:
        stmt = select(func.count()).select_from(model)
        if asset_id is not None:
            stmt = stmt.where(column == _validate_asset_id(asset_id))
        with self.session() as session:
            return int(session.execute(stmt).scalar_one())

    def __repr__(self) -> str:
        return f"TelemetryStore(url={self._db_url!r}, closed={self._closed})"


def _field(item: Any, name: str, default: Any = _REQUIRED) -> Any:
    """Read ``name`` from a mapping or attribute-bearing object."""
    if isinstance(item, Mapping):
        if name in item:
            return item[name]
    elif hasattr(item, name):
        return getattr(item, name)
    if default is _REQUIRED:
        raise KeyError(f"equipment definition is missing required field {name!r}")
    return default


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _assignment_record(assignment: Mapping[str, Any]) -> AssignmentRecord:
    """Validate one assignment payload and build its ORM record."""
    assignment_id = assignment.get("assignment_id")
    if not isinstance(assignment_id, str) or not assignment_id.strip():
        raise ValueError("assignment_id must be a non-blank string")
    for name in (
        "requester_work_order_id",
        "provider_work_order_id",
        "requester_organization_id",
        "provider_organization_id",
    ):
        value = assignment.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-blank string")
    return AssignmentRecord(
        assignment_id=assignment_id,
        asset_id=_validate_asset_id(assignment["asset_id"]),
        requester_work_order_id=assignment["requester_work_order_id"],
        provider_work_order_id=assignment["provider_work_order_id"],
        hourly_rate=_to_decimal(assignment["hourly_rate"], "hourly_rate"),
        hours=_to_decimal(assignment["hours"], "hours"),
        requester_organization_id=assignment["requester_organization_id"],
        provider_organization_id=assignment["provider_organization_id"],
        timestamp=ensure_utc(assignment["timestamp"]),
    )


def _equipment_row(record: EquipmentRecord) -> EquipmentRow:
    return EquipmentRow(
        asset_id=record.asset_id,
        name=record.name,
        equipment_type=record.equipment_type,
        currency=record.currency,
        site_code=record.site_code,
        hourly_service_rate=record.hourly_service_rate,
        rate_increment=record.rate_increment,
        hour_lot_size=record.hour_lot_size,
    )


__all__ = [
    "Base",
    "DecimalText",
    "UTCDateTime",
    "ReadingRecord",
    "IntervalRecord",
    "AssignmentRecord",
    "EquipmentRecord",
    "ReadingRow",
    "IntervalRow",
    "AssignmentRow",
    "EquipmentRow",
    "TelemetryStore",
    "ensure_utc",
    "MAX_QUERY_LIMIT",
    "MAX_SEARCH_LIMIT",
    "MAX_SEARCH_QUERY_LENGTH",
    "WORK_ORDER_ID_COLUMN_LENGTH",
]
