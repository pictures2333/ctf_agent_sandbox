"""Gemini CLI tool plugin."""

from __future__ import annotations

from typing import Any

from ..models import SandboxConfig
from .registry import AgentCliToolSpec, register_agent_cli_tool


def _tool_gemini(config: SandboxConfig, options: dict[str, str], context: Any) -> None:
    _ = config
    # Install Gemini CLI package.
    context.npm_packages.add("@google/gemini-cli")

    # Mount auth/config only when explicitly configured by the caller.
    auth_host_path = options.get("auth_host_path")
    config_host_path = options.get("config_host_path")
    if auth_host_path:
        context.volumes.append(f"{auth_host_path}:/home/agent/.gemini/oauth_creds.json")
    if config_host_path:
        context.volumes.append(f"{config_host_path}:/home/agent/.gemini/settings.json")


def register_gemini_tool() -> None:
    # Register Gemini plugin mount conventions and handler.
    register_agent_cli_tool(
        AgentCliToolSpec(
            name="gemini",
            handler=_tool_gemini,
            skills_mount_dir="/home/agent/.gemini/skills",
        )
    )
