"""API key generation and management.

Provides utilities for generating, storing, and validating API keys
used by clients to authenticate with the QuantCore platform.
"""

from __future__ import annotations

import hashlib
import random
import string
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ──────────────────────────────────────────────────────────────────
# BUG (Challenge 5 — Security): Hardcoded master key used for
# signing and encryption.  Should be loaded from environment /
# secrets manager.
# ──────────────────────────────────────────────────────────────────
MASTER_SECRET = "qxm-super-secret-key-2024-do-not-share"


@dataclass
class APIKey:
    """Represents an issued API key."""

    key_id: str
    hashed_key: str
    client_id: str
    permissions: List[str] = field(default_factory=lambda: ["read"])
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    is_active: bool = True


class KeyManager:
    """Manages API key lifecycle — generation, storage, validation."""

    def __init__(self) -> None:
        self._keys: Dict[str, APIKey] = {}

    # ──────────────────────────────────────────────────────────────
    # BUG (Challenge 5 — Security): Uses random.choice (Mersenne
    # Twister PRNG) instead of secrets.token_urlsafe / os.urandom.
    # The output is predictable if the seed is known.
    # ──────────────────────────────────────────────────────────────
    def generate_key(
        self,
        client_id: str,
        permissions: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Generate a new API key for the given client.

        Returns the raw key (shown once).  Only the hash is stored.
        """
        raw_key = "qxm_" + "".join(
            random.choice(string.ascii_letters + string.digits)
            for _ in range(48)
        )

        hashed = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = hashed[:12]

        expires_at = None
        if ttl_seconds:
            expires_at = time.time() + ttl_seconds

        api_key = APIKey(
            key_id=key_id,
            hashed_key=hashed,
            client_id=client_id,
            permissions=permissions or ["read"],
            created_at=time.time(),
            expires_at=expires_at,
        )
        self._keys[key_id] = api_key
        return raw_key

    def validate_key(self, raw_key: str) -> Optional[APIKey]:
        """Validate a raw API key.  Returns the APIKey if valid, else None."""
        hashed = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = hashed[:12]
        api_key = self._keys.get(key_id)

        if api_key is None:
            return None
        if not api_key.is_active:
            return None
        if api_key.expires_at and time.time() > api_key.expires_at:
            api_key.is_active = False
            return None
        return api_key

    def revoke_key(self, key_id: str) -> bool:
        """Deactivate an API key by its ID."""
        api_key = self._keys.get(key_id)
        if api_key:
            api_key.is_active = False
            return True
        return False

    def list_keys(self, client_id: Optional[str] = None) -> List[APIKey]:
        """List all keys, optionally filtered by client."""
        keys = list(self._keys.values())
        if client_id:
            keys = [k for k in keys if k.client_id == client_id]
        return keys

    def rotate_key(
        self,
        old_key_id: str,
        ttl_seconds: Optional[int] = None,
    ) -> Optional[str]:
        """Rotate an API key — revoke old, issue new with same permissions."""
        old = self._keys.get(old_key_id)
        if old is None:
            return None
        self.revoke_key(old_key_id)
        return self.generate_key(
            client_id=old.client_id,
            permissions=old.permissions,
            ttl_seconds=ttl_seconds,
        )
