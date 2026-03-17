"""MCP Terminal background service plugin."""

from __future__ import annotations

from ..models import SandboxConfig
from ..modules import BuildContext
from ..service_registry import get_service_options, register_background_service


def _service_mcp_terminal(config: SandboxConfig, context: BuildContext) -> None:
    # Resolve service options and mount paths.
    options = get_service_options(config, "mcp-terminal")
    host_path = options.get("host_path", "./mcp")
    container_path = options.get("container_path", "/mcp")

    # Install runtime dependency and enqueue startup command.
    context.yay_packages.add("python-mcp")
    context.startup_commands.append(
        f"(cd {container_path}/mcp_terminal "
        "&& uv sync "
        f"&& uv run main.py --host 127.0.0.1 --port 8000 --path {container_path} "
        "--workdir /home/agent/challenge --shell /bin/bash"
        ") > /tmp/mcp-terminal.log 2>&1 &"
    )
    if host_path:
        context.volumes.append(f"{host_path}:{container_path}")


def _mcp_terminal_skill_paths(config: SandboxConfig) -> list[str]:
    # Provide optional skill path only when configured/enabled.
    options = get_service_options(config, "mcp-terminal")
    skill_path = options.get("skill_path", "./skills/mcp-terminal-operator")
    return [skill_path] if skill_path else []


def register_mcp_terminal_service() -> None:
    # Register service behavior and optional skill provider.
    register_background_service(
        "mcp-terminal",
        _service_mcp_terminal,
        skill_provider=_mcp_terminal_skill_paths,
    )
