"""Public package API for the CTF sandbox assembler."""

from typing import Any

from .assembler import (
    STATE_FILE,
    AssemblyResult,
    assemble,
    assemble_and_write,
    build_image,
    run_container,
    stop_container,
)
from .agent_cli_tools.registry import AgentCliToolSpec, register_agent_cli_tool
from .models import SandboxConfig, parse_config
from .service_registry import register_background_service

# Export stable public API symbols for external callers.
__all__ = [
    "STATE_FILE",
    "AssemblyResult",
    "assemble",
    "assemble_and_write",
    "build_image",
    "run_container",
    "stop_container",
    "AgentCliToolSpec",
    "register_agent_cli_tool",
    "register_background_service",
    "SandboxConfig",
    "parse_config",
]


def assemble_from_object(config_obj: SandboxConfig | dict[str, Any]) -> AssemblyResult:
    """Backward-compatible helper for assembling from a Python object."""
    # Keep legacy helper behavior while reusing the unified assemble function.
    return assemble(config_obj)
