"""Request-scoped dependencies backed by application state.

Nothing here is a module-level singleton: every dependency resolves through
``request.app.state``, so several applications can coexist in one process (and
in one test session) without sharing an engine, key manager, or store.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, Request, status

from mittelwerk.api.service import DispatchService
from mittelwerk.auth.keys import KeyManager
from mittelwerk.core.engine import DispatchEngine
from mittelwerk.core.events import EventBus
from mittelwerk.core.models import Equipment
from mittelwerk.telemetry.store import TelemetryStore

if TYPE_CHECKING:  # imported for typing only: the API never drives the feed
    from mittelwerk.telemetry.feed import TelemetryFeed

#: Canonical authentication header for the platform.
API_KEY_HEADER = "X-API-Key"
#: Permission required by read-only surfaces.
PERMISSION_READ = "read"
#: Permission required to submit or cancel work orders.
PERMISSION_DISPATCH = "dispatch"


@dataclass(frozen=True)
class AuthPrincipal:
    """Identity derived from a validated API key — never from request input."""

    organization_id: str
    permissions: frozenset[str]
    key_id: str

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


@dataclass
class AppServices:
    """Container for everything a request handler may need."""

    event_bus: EventBus
    engine: DispatchEngine
    dispatch: DispatchService
    key_manager: KeyManager
    equipment: dict[str, Equipment]
    version: str
    store: TelemetryStore | None = None
    feed: TelemetryFeed | None = None


def get_services(request: Request) -> AppServices:
    services = getattr(request.app.state, "services", None)
    if not isinstance(services, AppServices):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application services are not initialised",
        )
    return services


#: Injected application services for a single request.
ServicesDep = Annotated[AppServices, Depends(get_services)]


def get_engine(services: ServicesDep) -> DispatchEngine:
    return services.engine


def get_dispatch(services: ServicesDep) -> DispatchService:
    return services.dispatch


def get_principal(request: Request) -> AuthPrincipal:
    """Return the principal attached by the authentication middleware."""
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, AuthPrincipal):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing {API_KEY_HEADER} header",
        )
    return principal


#: Authenticated identity, without any permission requirement.
PrincipalDep = Annotated["AuthPrincipal", Depends(get_principal)]


def require_permission(permission: str) -> Callable[..., AuthPrincipal]:
    """Build a dependency enforcing a single permission (least privilege)."""

    def _dependency(principal: PrincipalDep) -> AuthPrincipal:
        if not principal.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key lacks the '{permission}' permission",
            )
        return principal

    return _dependency


require_read = require_permission(PERMISSION_READ)
require_dispatch = require_permission(PERMISSION_DISPATCH)

#: Identity that additionally proves the ``read`` / ``dispatch`` permission.
ReadPrincipalDep = Annotated[AuthPrincipal, Depends(require_read)]
DispatchPrincipalDep = Annotated[AuthPrincipal, Depends(require_dispatch)]


__all__ = [
    "API_KEY_HEADER",
    "PERMISSION_READ",
    "PERMISSION_DISPATCH",
    "AuthPrincipal",
    "AppServices",
    "ServicesDep",
    "PrincipalDep",
    "ReadPrincipalDep",
    "DispatchPrincipalDep",
    "get_services",
    "get_engine",
    "get_dispatch",
    "get_principal",
    "require_permission",
    "require_read",
    "require_dispatch",
]
