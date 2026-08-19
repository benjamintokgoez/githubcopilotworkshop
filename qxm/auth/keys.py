"""API key lifecycle management for the QuantCore platform.

Design rules enforced here:

* Raw API keys are produced with :mod:`secrets` and are returned **once**, at
  creation time.  They are never stored, logged, or exposed through metadata,
  ``repr``, or listings.
* Only a *keyed* digest (HMAC-SHA256 over the raw key, keyed with the manager
  secret) is persisted, so a leaked key store alone cannot be brute-forced.
* Validation is O(1) on the keyed digest and confirms the match with
  :func:`hmac.compare_digest`; callers never iterate the private key store.
* Expiry is evaluated against an injectable clock so tests are deterministic.

The manager secret comes from an explicit constructor argument or from the
``QXM_AUTH_SECRET_KEY`` environment variable.  When neither is present a
process-local cryptographic secret is generated (and never logged), which means
keys issued by one process are not valid in another.
"""

from __future__ import annotations

import hmac
import logging
import os
import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

logger = logging.getLogger(__name__)

# The name of an environment variable, not a secret value.
SECRET_ENV_NAME = "QXM_AUTH_SECRET_KEY"  # noqa: S105
KEY_PREFIX = "qxm_"
#: Number of random bytes behind every generated raw key.
KEY_ENTROPY_BYTES = 32

#: Permissions understood by the platform.  ``read`` guards query surfaces,
#: ``trade`` guards order submission/cancellation, ``admin`` is reserved for
#: key administration performed out of band.
VALID_PERMISSIONS = frozenset({"read", "trade", "admin"})
DEFAULT_PERMISSIONS = frozenset({"read"})

Clock = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _validate_client_id(client_id: str) -> str:
    if not isinstance(client_id, str):
        raise TypeError("client_id must be a string")
    normalised = client_id.strip()
    if not normalised:
        raise ValueError("client_id must be a non-blank string")
    return normalised


def _validate_permissions(permissions: Iterable[str] | None) -> frozenset[str]:
    if permissions is None:
        return DEFAULT_PERMISSIONS
    if isinstance(permissions, (str, bytes)):
        raise TypeError("permissions must be a collection of strings, not a string")
    collected: set[str] = set()
    for permission in permissions:
        if not isinstance(permission, str):
            raise TypeError("each permission must be a string")
        normalised = permission.strip().lower()
        if normalised not in VALID_PERMISSIONS:
            raise ValueError(
                f"unknown permission {permission!r}; expected one of {sorted(VALID_PERMISSIONS)}"
            )
        collected.add(normalised)
    if not collected:
        raise ValueError("permissions must not be empty")
    return frozenset(collected)


def _validate_ttl(ttl_seconds: int | None) -> int | None:
    if ttl_seconds is None:
        return None
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
        raise TypeError("ttl_seconds must be an int or None")
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")
    return ttl_seconds


def _coerce_secret(secret_key: str | bytes | None) -> bytes:
    """Return the manager secret as bytes, generating one when unset."""
    if secret_key is None:
        secret_key = os.environ.get(SECRET_ENV_NAME) or None
    if secret_key is None:
        # Process-local secret: keys stay valid for this process only.  The
        # value is never logged.
        return secrets.token_bytes(KEY_ENTROPY_BYTES)
    if isinstance(secret_key, str):
        secret_key = secret_key.encode("utf-8")
    if not isinstance(secret_key, bytes):
        raise TypeError("secret_key must be str, bytes, or None")
    if not secret_key:
        raise ValueError("secret_key must not be empty")
    return secret_key


@dataclass(frozen=True)
class APIKey:
    """Public metadata for an issued API key.

    This object intentionally carries **no** secret material: neither the raw
    key nor its digest, so it is safe to log, list, or serialise.
    """

    key_id: str
    client_id: str
    permissions: frozenset[str]
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        return (now or _utcnow()) >= self.expires_at

    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_active(self, now: datetime | None = None) -> bool:
        return not self.is_revoked() and not self.is_expired(now)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def __repr__(self) -> str:
        return (
            f"APIKey(key_id={self.key_id!r}, client_id={self.client_id!r}, "
            f"permissions={sorted(self.permissions)!r}, "
            f"expires_at={self.expires_at!r}, revoked={self.is_revoked()})"
        )


class KeyManager:
    """Manage API key lifecycle: issue, register, validate, revoke, rotate."""

    def __init__(
        self,
        secret_key: str | bytes | None = None,
        *,
        clock: Clock | None = None,
        default_ttl_seconds: int | None = None,
    ) -> None:
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self._secret = _coerce_secret(secret_key)
        self._clock: Clock = clock or _utcnow
        self._default_ttl = _validate_ttl(default_ttl_seconds)
        self._records: dict[str, APIKey] = {}
        self._digests: dict[str, str] = {}  # key_id -> keyed digest
        self._by_digest: dict[str, str] = {}  # keyed digest -> key_id

    # -- Internals -------------------------------------------------------

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime):
            raise TypeError("clock must return a datetime")
        if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now.astimezone(UTC)

    def _digest(self, raw_key: str) -> str:
        return hmac.new(self._secret, raw_key.encode("utf-8"), sha256).hexdigest()

    def _store(
        self,
        raw_key: str,
        client_id: str,
        permissions: Iterable[str] | None,
        ttl_seconds: int | None,
    ) -> APIKey:
        client = _validate_client_id(client_id)
        perms = _validate_permissions(permissions)
        ttl = _validate_ttl(ttl_seconds) if ttl_seconds is not None else self._default_ttl

        digest = self._digest(raw_key)
        if digest in self._by_digest:
            raise ValueError("API key is already registered")

        now = self._now()
        key_id = secrets.token_hex(8)
        record = APIKey(
            key_id=key_id,
            client_id=client,
            permissions=perms,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl) if ttl is not None else None,
        )
        self._records[key_id] = record
        self._digests[key_id] = digest
        self._by_digest[digest] = key_id
        logger.info(
            "Issued API key %s for client %s (permissions=%s)",
            key_id,
            client,
            sorted(perms),
        )
        return record

    # -- Issuance --------------------------------------------------------

    def generate_key(
        self,
        client_id: str,
        permissions: Iterable[str] | None = None,
        ttl_seconds: int | None = None,
    ) -> str:
        """Issue a new key and return the raw value — shown exactly once."""
        raw_key = KEY_PREFIX + secrets.token_urlsafe(KEY_ENTROPY_BYTES)
        self._store(raw_key, client_id, permissions, ttl_seconds)
        return raw_key

    def register_key(
        self,
        raw_key: str,
        client_id: str,
        permissions: Iterable[str] | None = None,
        ttl_seconds: int | None = None,
    ) -> APIKey:
        """Register an externally supplied raw key (env/test bootstrap).

        Returns metadata only; the raw key stays with the caller that owns it.
        """
        if not isinstance(raw_key, str):
            raise TypeError("raw_key must be a string")
        if len(raw_key.strip()) < 16:
            raise ValueError("raw_key must be at least 16 characters")
        return self._store(raw_key, client_id, permissions, ttl_seconds)

    # -- Validation ------------------------------------------------------

    def validate_key(self, raw_key: str) -> APIKey | None:
        """Return the key metadata when ``raw_key`` is valid, else ``None``.

        The lookup is performed on the keyed digest — an attacker cannot steer
        it without the manager secret — and the final equality check is
        timing-safe.
        """
        if not isinstance(raw_key, str) or not raw_key:
            return None
        digest = self._digest(raw_key)
        key_id = self._by_digest.get(digest)
        if key_id is None:
            return None
        stored_digest = self._digests[key_id]
        if not hmac.compare_digest(stored_digest, digest):
            return None
        record = self._records[key_id]
        if not record.is_active(self._now()):
            return None
        return record

    def has_permission(self, raw_key: str, permission: str) -> bool:
        record = self.validate_key(raw_key)
        return record is not None and record.has_permission(permission)

    # -- Lifecycle -------------------------------------------------------

    def revoke_key(self, key_id: str) -> bool:
        """Revoke a key by id.  Returns ``False`` when already revoked/unknown."""
        record = self._records.get(key_id)
        if record is None or record.is_revoked():
            return False
        self._records[key_id] = replace(record, revoked_at=self._now())
        logger.info("Revoked API key %s for client %s", key_id, record.client_id)
        return True

    def rotate_key(
        self,
        old_key_id: str,
        ttl_seconds: int | None = None,
    ) -> str | None:
        """Revoke ``old_key_id`` and issue a replacement with the same grants."""
        record = self._records.get(old_key_id)
        if record is None:
            return None
        self.revoke_key(old_key_id)
        return self.generate_key(
            client_id=record.client_id,
            permissions=record.permissions,
            ttl_seconds=ttl_seconds,
        )

    # -- Introspection ---------------------------------------------------

    def get_key(self, key_id: str) -> APIKey | None:
        return self._records.get(key_id)

    def list_keys(self, client_id: str | None = None) -> list[APIKey]:
        """List key metadata — never secrets — optionally filtered by client."""
        records = list(self._records.values())
        if client_id is not None:
            wanted = _validate_client_id(client_id)
            records = [r for r in records if r.client_id == wanted]
        return sorted(records, key=lambda r: (r.created_at, r.key_id))

    @property
    def key_count(self) -> int:
        return len(self._records)

    def __repr__(self) -> str:
        return f"KeyManager(keys={len(self._records)})"


__all__ = [
    "APIKey",
    "KeyManager",
    "SECRET_ENV_NAME",
    "KEY_PREFIX",
    "KEY_ENTROPY_BYTES",
    "VALID_PERMISSIONS",
    "DEFAULT_PERMISSIONS",
]
