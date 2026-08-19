"""qxm.api — FastAPI REST interface for the QuantCore trading simulator.

Dependencies are resolved from application state (see
:mod:`qxm.api.dependencies`), so applications created in the same process never
share engines, keys, or storage.
"""

from qxm.api.dependencies import (
    API_KEY_HEADER,
    PERMISSION_READ,
    PERMISSION_TRADE,
    AppServices,
    AuthPrincipal,
    get_principal,
    get_services,
    require_permission,
    require_read,
    require_trade,
)
from qxm.api.middleware import (
    DEFAULT_PUBLIC_PATHS,
    APIKeyAuthMiddleware,
    RequestLoggingMiddleware,
    configure_middleware,
)
from qxm.api.routes import router
from qxm.api.schemas import DashboardResponse, OrderRequest, OrderSubmissionResponse
from qxm.api.service import TradingService

__all__ = [
    "router",
    "API_KEY_HEADER",
    "PERMISSION_READ",
    "PERMISSION_TRADE",
    "AppServices",
    "AuthPrincipal",
    "TradingService",
    "OrderRequest",
    "OrderSubmissionResponse",
    "DashboardResponse",
    "get_principal",
    "get_services",
    "require_permission",
    "require_read",
    "require_trade",
    "APIKeyAuthMiddleware",
    "RequestLoggingMiddleware",
    "DEFAULT_PUBLIC_PATHS",
    "configure_middleware",
]
