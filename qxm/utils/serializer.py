"""Object serialisation utilities — JSON and binary formats.

Provides serialisation for domain objects that aren't natively
JSON-serialisable (Decimal, datetime, enums, etc.).
"""

from __future__ import annotations

import json
import pickle
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class QuantEncoder(json.JSONEncoder):
    """Custom JSON encoder for QuantCore domain types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        if hasattr(obj, "dict"):
            return obj.dict()
        if hasattr(obj, "__dict__"):
            return {
                k: v for k, v in obj.__dict__.items()
                if not k.startswith("_")
            }
        return super().default(obj)


def to_json(obj: Any, pretty: bool = False) -> str:
    """Serialise an object to a JSON string."""
    return json.dumps(
        obj,
        cls=QuantEncoder,
        indent=2 if pretty else None,
        sort_keys=True,
    )


def from_json(data: str) -> Any:
    """Deserialise a JSON string."""
    return json.loads(data)


# ──────────────────────────────────────────────────────────────────
# BUG (Challenge 5 — Security): pickle.loads on untrusted data
# allows arbitrary code execution.  Should use a safe format
# (JSON, msgpack, protobuf) or at minimum restrict allowed classes.
# ──────────────────────────────────────────────────────────────────

def to_binary(obj: Any) -> bytes:
    """Serialise an object to a binary (pickle) byte string.

    Useful for high-performance caching of pre-computed risk
    analytics and portfolio snapshots.
    """
    return pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)


def from_binary(data: bytes) -> Any:
    """Deserialise a binary (pickle) byte string.

    .. warning::
        This loads arbitrary Python objects.  Only use with trusted
        data sources.
    """
    return pickle.loads(data)  # noqa: S301


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def round_decimal(value: float, tick_size: float) -> Decimal:
    """Round a float to the nearest tick size."""
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")
    ticks = round(value / tick_size)
    return Decimal(str(ticks * tick_size))
