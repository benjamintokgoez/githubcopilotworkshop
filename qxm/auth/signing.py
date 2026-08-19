"""Request signing and verification — HMAC-SHA256 over a canonical request.

The canonical string is deterministic (sorted, percent-encoded parameters plus
a body hash) so signer and verifier always agree.  ``timestamp`` is handled
explicitly: ``None`` means "use the current clock" while ``0`` is a legitimate
epoch second and is signed as such.  Verification is timing-safe and rejects
both stale and future-dated requests.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Mapping
from urllib.parse import urlencode

#: Default replay window, in seconds, applied by :func:`verify_signature`.
DEFAULT_MAX_AGE_SECONDS = 300


def _coerce_secret(secret_key: str | bytes) -> bytes:
    if isinstance(secret_key, str):
        secret_key = secret_key.encode("utf-8")
    if not isinstance(secret_key, bytes):
        raise TypeError("secret_key must be str or bytes")
    if not secret_key:
        raise ValueError("secret_key must not be empty")
    return secret_key


def _coerce_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def _coerce_timestamp(timestamp: int | None) -> int:
    """Resolve the signing timestamp.  ``0`` is a valid value, not "missing"."""
    if timestamp is None:
        return int(time.time())
    if isinstance(timestamp, bool) or not isinstance(timestamp, int):
        raise TypeError("timestamp must be an int (epoch seconds) or None")
    if timestamp < 0:
        raise ValueError("timestamp must not be negative")
    return timestamp


def _canonical_params(params: Mapping[str, str] | None) -> str:
    if params is None:
        return ""
    if not isinstance(params, Mapping):
        raise TypeError("params must be a mapping of string keys to string values")
    items: list[tuple[str, str]] = []
    for key, value in params.items():
        if not isinstance(key, str):
            raise TypeError("param names must be strings")
        if not isinstance(value, str):
            raise TypeError(f"param {key!r} must have a string value")
        items.append((key, value))
    return urlencode(sorted(items))


def canonical_request(
    method: str,
    path: str,
    params: Mapping[str, str] | None = None,
    body: str = "",
    timestamp: int | None = None,
) -> str:
    """Build the canonical string representation of an API request.

    Format::

        METHOD\\nPATH\\nSORTED_PARAMS\\nBODY_SHA256\\nTIMESTAMP
    """
    method_text = _coerce_text(method, "method").strip()
    if not method_text:
        raise ValueError("method must not be blank")
    path_text = _coerce_text(path, "path")
    if not path_text.startswith("/"):
        raise ValueError("path must be an absolute request path starting with '/'")
    body_text = _coerce_text(body, "body")
    ts = _coerce_timestamp(timestamp)
    sorted_params = _canonical_params(params)
    body_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
    return f"{method_text.upper()}\n{path_text}\n{sorted_params}\n{body_hash}\n{ts}"


def sign_request(
    secret_key: str | bytes,
    method: str,
    path: str,
    params: Mapping[str, str] | None = None,
    body: str = "",
    timestamp: int | None = None,
) -> str:
    """Compute the HMAC-SHA256 signature for the given request."""
    canon = canonical_request(method, path, params, body, timestamp)
    return hmac.new(
        _coerce_secret(secret_key),
        canon.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(
    secret_key: str | bytes,
    signature: str,
    method: str,
    path: str,
    params: Mapping[str, str] | None = None,
    body: str = "",
    timestamp: int | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> bool:
    """Verify a request signature within a bounded replay window.

    Returns ``False`` for a malformed signature, a stale request, or a request
    dated further into the future than ``max_age_seconds``.  Misconfiguration
    (empty secret, non-positive ``max_age_seconds``, non-integer timestamp) is
    a programming error and raises.
    """
    if isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, int):
        raise TypeError("max_age_seconds must be an int")
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if not isinstance(signature, str) or not signature:
        return False

    ts = _coerce_timestamp(timestamp)
    now = int(time.time())
    if abs(now - ts) > max_age_seconds:
        return False

    expected = sign_request(secret_key, method, path, params, body, ts)
    return hmac.compare_digest(expected, signature)


__all__ = [
    "DEFAULT_MAX_AGE_SECONDS",
    "canonical_request",
    "sign_request",
    "verify_signature",
]
