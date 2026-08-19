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

from qxm.api.service import TradingService
from qxm.auth.keys import KeyManager
from qxm.core.engine import MatchingEngine
from qxm.core.events import EventBus
from qxm.core.models import Instrument
from qxm.data.store import TimeSeriesStore

if TYPE_CHECKING:  # imported for typing only: the API never drives the feed
    from qxm.data.feed import MarketDataFeed

#: Canonical authentication header for the platform.
API_KEY_HEADER = "X-API-Key"
#: Permission required by read-only surfaces.
PERMISSION_READ = "read"
#: Permission required to submit or cancel orders.
PERMISSION_TRADE = "trade"


@dataclass(frozen=True)
class AuthPrincipal:
    """Identity derived from a validated API key — never from request input."""

    client_id: str
    permissions: frozenset[str]
    key_id: str

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


@dataclass
class AppServices:
    """Container for everything a request handler may need."""

    event_bus: EventBus
    engine: MatchingEngine
    trading: TradingService
    key_manager: KeyManager
    instruments: dict[str, Instrument]
    version: str
    store: TimeSeriesStore | None = None
    feed: MarketDataFeed | None = None


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


def get_engine(services: ServicesDep) -> MatchingEngine:
    return services.engine


def get_trading(services: ServicesDep) -> TradingService:
    return services.trading


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
require_trade = require_permission(PERMISSION_TRADE)

#: Identity that additionally proves the ``read`` / ``trade`` permission.
ReadPrincipalDep = Annotated[AuthPrincipal, Depends(require_read)]
TradePrincipalDep = Annotated[AuthPrincipal, Depends(require_trade)]


__all__ = [
    "API_KEY_HEADER",
    "PERMISSION_READ",
    "PERMISSION_TRADE",
    "AuthPrincipal",
    "AppServices",
    "ServicesDep",
    "PrincipalDep",
    "ReadPrincipalDep",
    "TradePrincipalDep",
    "get_services",
    "get_engine",
    "get_trading",
    "get_principal",
    "require_permission",
    "require_read",
    "require_trade",
]
