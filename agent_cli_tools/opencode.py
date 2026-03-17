"""OpenCode CLI tool plugin."""

from __future__ import annotations

from typing import Any

from ..models import SandboxConfig
from .registry import AgentCliToolSpec, register_agent_cli_tool


def _tool_opencode(config: SandboxConfig, options: dict[str, str], context: Any) -> None:
    _ = config
    # Install OpenCode CLI via upstream install script.
    context.agent_commands.append("curl -fsSL https://opencode.ai/install | bash")

    # Mount auth/config only when explicitly configured by the caller.
    auth_host_path = options.get("auth_host_path")
    config_host_path = options.get("config_host_path")
    if auth_host_path:
        context.volumes.append(f"{auth_host_path}:/home/agent/.local/share/opencode/auth.json")
    if config_host_path:
        context.volumes.append(f"{config_host_path}:/home/agent/.config/opencode/opencode.json")


def register_opencode_tool() -> None:
    # Register OpenCode plugin mount conventions and handler.
    register_agent_cli_tool(
        AgentCliToolSpec(
            name="opencode",
            handler=_tool_opencode,
            skills_mount_dir="/home/agent/.config/opencode/skills",
        )
    )
