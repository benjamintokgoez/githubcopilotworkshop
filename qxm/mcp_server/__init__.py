"""MCP v2 integration for QuantCore's local simulation runtime."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from qxm.mcp_server.server import RiskCalculator as RiskCalculator
    from qxm.mcp_server.server import (
        create_default_mcp_server as create_default_mcp_server,
    )
    from qxm.mcp_server.server import create_mcp_server as create_mcp_server
    from qxm.mcp_server.server import run_server as run_server

__all__ = [
    "RiskCalculator",
    "create_default_mcp_server",
    "create_mcp_server",
    "run_server",
]

_EXPORTS = frozenset(__all__)


def __getattr__(name: str) -> Any:
    """Load the server module only when an exported integration is requested."""
    if name in _EXPORTS:
        value = getattr(import_module("qxm.mcp_server.server"), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return the stable public package namespace."""
    return sorted(set(globals()) | _EXPORTS)
