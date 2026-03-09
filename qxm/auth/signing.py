"""Request signing and verification — HMAC-SHA256 signatures for API auth.

Uses canonical request construction to prevent tampering.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Dict, Optional
from urllib.parse import urlencode


def canonical_request(
    method: str,
    path: str,
    params: Optional[Dict[str, str]] = None,
    body: str = "",
    timestamp: Optional[int] = None,
) -> str:
    """Build a canonical string representation of an API request.

    Format::

        METHOD\\nPATH\\nSORTED_PARAMS\\nBODY_HASH\\nTIMESTAMP
    """
    ts = timestamp or int(time.time())
    sorted_params = urlencode(sorted((params or {}).items()))
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    return f"{method.upper()}\n{path}\n{sorted_params}\n{body_hash}\n{ts}"


def sign_request(
    secret_key: str,
    method: str,
    path: str,
    params: Optional[Dict[str, str]] = None,
    body: str = "",
    timestamp: Optional[int] = None,
) -> str:
    """Compute HMAC-SHA256 signature for the given request."""
    canon = canonical_request(method, path, params, body, timestamp)
    return hmac.new(
        secret_key.encode(),
        canon.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(
    secret_key: str,
    signature: str,
    method: str,
    path: str,
    params: Optional[Dict[str, str]] = None,
    body: str = "",
    timestamp: Optional[int] = None,
    max_age_seconds: int = 300,
) -> bool:
    """Verify a request signature.

    Also rejects requests older than ``max_age_seconds`` to prevent
    replay attacks.
    """
    ts = timestamp or int(time.time())
    now = int(time.time())

    if abs(now - ts) > max_age_seconds:
        return False

    expected = sign_request(secret_key, method, path, params, body, ts)
    return hmac.compare_digest(expected, signature)
