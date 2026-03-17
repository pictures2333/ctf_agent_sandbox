"""Built-in background service plugin bootstrap."""

from __future__ import annotations

from .dockerd import register_dockerd_service
from .mcp_terminal import register_mcp_terminal_service

_LOADED = False


def ensure_builtin_background_services_registered() -> None:
    """Register built-in background service plugins once."""
    global _LOADED
    # Guard against duplicate registration side effects.
    if _LOADED:
        return
    # Register built-in background service plugins.
    register_dockerd_service()
    register_mcp_terminal_service()
    _LOADED = True
