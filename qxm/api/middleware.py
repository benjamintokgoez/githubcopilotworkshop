"""HTTP middleware: API key authentication, request logging, and CORS.

Authentication reads exactly one header, ``X-API-Key``.  Validation is
delegated to :class:`~qxm.auth.keys.KeyManager`, which performs a timing-safe
comparison against a keyed digest — the middleware never touches private key
storage.  A missing header is ``401``; a key that is unknown, expired, or
revoked is ``403``.

Only the health endpoint, the interactive API docs, and the unauthenticated
dashboard shell are public.  Everything that exposes trading, order, position,
or risk data requires a valid key.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable, Iterable, Sequence

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from qxm.api.dependencies import API_KEY_HEADER, AuthPrincipal
from qxm.auth.keys import KeyManager

logger = logging.getLogger(__name__)

#: Paths served without authentication: liveness, docs, and the dashboard shell.
DEFAULT_PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/",
        "/api/v1/health",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/openapi.json",
    }
)

CallNext = Callable[[Request], Awaitable[Response]]


def _json_error(status_code: int, detail: str) -> Response:
    return Response(
        content=json.dumps({"detail": detail}),
        status_code=status_code,
        media_type="application/json",
    )


def validate_cors_origins(cors_origins: object) -> list[str]:
    """Validate configured CORS origins, returning them as a list.

    ``None`` means "no CORS" (same-origin only).  Anything else must be a
    non-string sequence of non-blank strings: a bare string would otherwise be
    iterated character by character and silently authorise a set of one-letter
    origins.
    """
    if cors_origins is None:
        return []
    if isinstance(cors_origins, (str, bytes)):
        raise ValueError(
            "server.cors_origins must be a list of origin strings, not a single "
            f"string; write [{cors_origins!r}] to allow exactly that origin"
        )
    if not isinstance(cors_origins, Sequence):
        raise ValueError(
            "server.cors_origins must be a list of origin strings, got "
            f"{type(cors_origins).__name__}"
        )
    origins: list[str] = []
    for index, origin in enumerate(cors_origins):
        if not isinstance(origin, str):
            raise ValueError(
                f"server.cors_origins[{index}] must be a string, got {type(origin).__name__}"
            )
        trimmed = origin.strip()
        if not trimmed:
            raise ValueError(f"server.cors_origins[{index}] must not be blank")
        origins.append(trimmed)
    return origins


def validate_cors_credentials(cors_allow_credentials: object) -> bool:
    """Validate the credentials flag.

    Only a real boolean is accepted: coercing values such as the string
    ``"false"`` would enable credentialed cross-origin requests for a
    configuration that plainly says otherwise.
    """
    if not isinstance(cors_allow_credentials, bool):
        raise ValueError(
            "server.cors_allow_credentials must be a boolean (true/false), got "
            f"{type(cors_allow_credentials).__name__}"
        )
    return cors_allow_credentials


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Authenticate requests against the application's :class:`KeyManager`."""

    def __init__(
        self,
        app: ASGIApp,
        key_manager: KeyManager,
        public_paths: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.key_manager = key_manager
        self.public_paths = frozenset(
            DEFAULT_PUBLIC_PATHS if public_paths is None else public_paths
        )

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        if request.method == "OPTIONS" or request.url.path in self.public_paths:
            return await call_next(request)

        raw_key = request.headers.get(API_KEY_HEADER)
        if not raw_key:
            return _json_error(401, f"Missing {API_KEY_HEADER} header")

        api_key = self.key_manager.validate_key(raw_key)
        if api_key is None:
            logger.warning(
                "Rejected request to %s: API key is invalid, expired, or revoked",
                request.url.path,
            )
            return _json_error(403, "Invalid, expired, or revoked API key")

        request.state.principal = AuthPrincipal(
            client_id=api_key.client_id,
            permissions=frozenset(api_key.permissions),
            key_id=api_key.key_id,
        )
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status, and duration.

    Headers, query strings, and bodies are deliberately excluded so API keys and
    payload data can never reach the log.
    """

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        logger.info(
            "%s %s -> %d (%.4fs)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response


def configure_middleware(
    app: FastAPI,
    key_manager: KeyManager,
    *,
    cors_origins: Sequence[str] | None = None,
    cors_allow_credentials: bool = False,
    public_paths: Iterable[str] | None = None,
) -> None:
    """Attach middleware to ``app``.

    CORS is opt-in: with no configured origins the API stays same-origin, which
    is the safe default for a dashboard served from the same host.  A wildcard
    origin is never combined with credentials.  Malformed CORS configuration
    raises :class:`ValueError` here — before the application ever serves a
    request — instead of quietly authorising something unintended.

    Registration order matters.  Starlette wraps the *last* registered
    middleware outermost, so CORS is added last and therefore sees every
    response — including the ``401``/``403`` produced by authentication.  Without
    that, a browser dashboard cannot read the auth failure at all and reports it
    as an opaque network error instead of "invalid key".
    """
    origins = validate_cors_origins(cors_origins)
    allow_credentials = validate_cors_credentials(cors_allow_credentials)

    # Innermost first: authentication, then request logging.
    app.add_middleware(APIKeyAuthMiddleware, key_manager=key_manager, public_paths=public_paths)
    app.add_middleware(RequestLoggingMiddleware)

    # Outermost: CORS, so cross-origin callers can read auth failures too.
    if origins:
        if "*" in origins and allow_credentials:
            logger.warning(
                "Refusing to combine wildcard CORS origin with credentials; credentials disabled"
            )
            allow_credentials = False
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=allow_credentials,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[API_KEY_HEADER, "Content-Type", "Accept"],
        )


__all__ = [
    "DEFAULT_PUBLIC_PATHS",
    "APIKeyAuthMiddleware",
    "RequestLoggingMiddleware",
    "configure_middleware",
    "validate_cors_origins",
    "validate_cors_credentials",
]
