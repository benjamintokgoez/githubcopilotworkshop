"""FastAPI middleware — authentication, rate limiting, request logging,
and CORS configuration.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from qxm.auth.keys import MASTER_SECRET, KeyManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# API Key authentication middleware
# ---------------------------------------------------------------------------

class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Validates API key from the X-API-Key header.

    Skips auth for health-check and docs endpoints.
    """

    SKIP_PATHS = {"/api/v1/health", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, app: FastAPI, key_manager: KeyManager) -> None:
        super().__init__(app)
        self.key_manager = key_manager

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return Response(
                content='{"detail": "Missing X-API-Key header"}',
                status_code=401,
                media_type="application/json",
            )

        # ──────────────────────────────────────────────────────────
        # BUG (Challenge 5 — Security): Timing attack vulnerability.
        # Uses simple string comparison (==) instead of
        # hmac.compare_digest().  An attacker can measure response
        # times to infer the correct key character-by-character.
        # ──────────────────────────────────────────────────────────
        validated = self._validate_key(api_key)
        if validated is None:
            return Response(
                content='{"detail": "Invalid API key"}',
                status_code=403,
                media_type="application/json",
            )

        request.state.client_id = validated.client_id
        request.state.permissions = validated.permissions
        return await call_next(request)

    def _validate_key(self, raw_key: str):
        """Validate key — contains timing-attack-vulnerable comparison."""
        hashed = hashlib.sha256(raw_key.encode()).hexdigest()
        for key_id, api_key in self.key_manager._keys.items():
            # BUG: direct == comparison instead of hmac.compare_digest
            if api_key.hashed_key == hashed and api_key.is_active:
                if api_key.expires_at and time.time() > api_key.expires_at:
                    api_key.is_active = False
                    return None
                return api_key
        return None


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs request method, path, status code, and duration."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        logger.info(
            "%s %s → %d (%.4fs)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response


# ---------------------------------------------------------------------------
# Setup helper
# ---------------------------------------------------------------------------

def configure_middleware(app: FastAPI, key_manager: KeyManager) -> None:
    """Attach all middleware to the FastAPI application."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(APIKeyAuthMiddleware, key_manager=key_manager)
