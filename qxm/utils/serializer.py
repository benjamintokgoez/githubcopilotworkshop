"""Deterministic JSON serialization helpers for QuantCore domain values."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


def _slot_names(value: object) -> tuple[str, ...]:
    names: list[str] = []
    for cls in type(value).__mro__:
        slots = cls.__dict__.get("__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        names.extend(
            name
            for name in slots
            if isinstance(name, str)
            and not name.startswith("_")
            and name not in {"__dict__", "__weakref__"}
        )
    return tuple(dict.fromkeys(names))


def _json_compatible(value: Any, seen: set[int] | None = None) -> Any:
    """Convert supported values without inspecting arbitrary ``__dict__`` data."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON numbers must be finite")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Decimal values must be finite")
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetimes must be timezone-aware")
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return _json_compatible(value.value, seen)

    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        raise ValueError("circular references cannot be serialized")
    seen.add(identity)
    try:
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return _json_compatible(model_dump(mode="json"), seen)

        if is_dataclass(value) and not isinstance(value, type):
            return {
                item.name: _json_compatible(getattr(value, item.name), seen)
                for item in fields(value)
                if not item.name.startswith("_")
            }

        if isinstance(value, Mapping):
            converted: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError("JSON object keys must be strings")
                converted[key] = _json_compatible(item, seen)
            return converted

        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray, memoryview)
        ):
            return [_json_compatible(item, seen) for item in value]

        slots = _slot_names(value)
        if slots:
            return {
                name: _json_compatible(getattr(value, name), seen)
                for name in slots
                if hasattr(value, name)
            }
    finally:
        seen.remove(identity)

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class QuantEncoder(json.JSONEncoder):
    """JSON encoder restricted to explicitly supported QuantCore value types."""

    def default(self, obj: Any) -> Any:
        """Return a JSON-compatible representation of ``obj``."""
        return _json_compatible(obj)


def to_json(obj: Any, pretty: bool = False) -> str:
    """Serialize ``obj`` to deterministic JSON."""
    return json.dumps(
        _json_compatible(obj),
        cls=QuantEncoder,
        allow_nan=False,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def _reject_non_finite_constant(constant: str) -> Any:
    raise ValueError(f"non-finite JSON constant is not permitted: {constant}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key is not permitted: {key!r}")
        result[key] = value
    return result


def from_json(data: str) -> Any:
    """Deserialize strict JSON, rejecting duplicate keys and non-finite values."""
    if not isinstance(data, str):
        raise TypeError("JSON input must be a string")
    try:
        return json.loads(
            data,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_non_finite_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON payload") from exc


def to_binary(obj: Any) -> bytes:
    """Serialize ``obj`` as deterministic UTF-8 encoded JSON bytes."""
    return to_json(obj).encode("utf-8")


def from_binary(data: bytes | bytearray | memoryview) -> Any:
    """Deserialize UTF-8 JSON bytes and reject malformed or non-JSON payloads."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("binary input must be bytes-like")
    try:
        text = bytes(data).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("binary payload is not valid UTF-8 JSON") from exc
    return from_json(text)


def round_decimal(
    value: float | Decimal,
    tick_size: float | Decimal,
) -> Decimal:
    """Round a finite numeric value to the nearest positive tick size."""
    decimal_value = Decimal(str(value))
    decimal_tick = Decimal(str(tick_size))
    if not decimal_value.is_finite():
        raise ValueError("value must be finite")
    if not decimal_tick.is_finite() or decimal_tick <= 0:
        raise ValueError("tick_size must be finite and positive")
    ticks = (decimal_value / decimal_tick).quantize(Decimal("1"))
    return ticks * decimal_tick
