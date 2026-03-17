"""Codex CLI tool plugin."""

from __future__ import annotations

from typing import Any

from ..models import SandboxConfig
from .registry import AgentCliToolSpec, register_agent_cli_tool


def _tool_codex(config: SandboxConfig, options: dict[str, str], context: Any) -> None:
    _ = config
    # Install Codex CLI package.
    context.npm_packages.add("@openai/codex")

    # Mount auth/config only when explicitly configured by the caller.
    auth_host_path = options.get("auth_host_path")
    config_host_path = options.get("config_host_path")
    if auth_host_path:
        context.volumes.append(f"{auth_host_path}:/home/agent/.codex/auth.json")
    if config_host_path:
        context.volumes.append(f"{config_host_path}:/home/agent/.codex/config.toml")


def register_codex_tool() -> None:
    # Register Codex plugin mount conventions and handler.
    register_agent_cli_tool(
        AgentCliToolSpec(
            name="codex",
            handler=_tool_codex,
            skills_mount_dir="/home/agent/.codex/skills",
        )
    )
