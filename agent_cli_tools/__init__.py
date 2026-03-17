"""Built-in agent CLI tool plugin bootstrap."""

from __future__ import annotations

from .codex import register_codex_tool
from .gemini import register_gemini_tool
from .opencode import register_opencode_tool

_LOADED = False


def ensure_builtin_agent_cli_tools_registered() -> None:
    """Register built-in agent CLI tool plugins once."""
    global _LOADED
    # Guard against duplicate registration side effects.
    if _LOADED:
        return
    # Register built-in tool plugins.
    register_codex_tool()
    register_gemini_tool()
    register_opencode_tool()
    _LOADED = True
