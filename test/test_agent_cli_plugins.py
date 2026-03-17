"""Tests for built-in agent CLI tool plugins."""

from __future__ import annotations

from ctf_agent_sandbox.agent_cli_tools import ensure_builtin_agent_cli_tools_registered
from ctf_agent_sandbox.agent_cli_tools import codex, gemini, opencode
from ctf_agent_sandbox.agent_cli_tools.registry import AGENT_CLI_TOOLS
from ctf_agent_sandbox.models import SandboxConfig
from ctf_agent_sandbox.modules import BuildContext


def test_tool_codex_applies_packages_and_optional_mounts() -> None:
    context = BuildContext()
    codex._tool_codex(
        SandboxConfig(),
        {"auth_host_path": "/a/auth.json", "config_host_path": "/a/config.toml"},
        context,
    )
    assert "@openai/codex" in context.npm_packages
    assert "/a/auth.json:/home/agent/.codex/auth.json" in context.volumes
    assert "/a/config.toml:/home/agent/.codex/config.toml" in context.volumes


def test_tool_gemini_applies_packages_and_optional_mounts() -> None:
    context = BuildContext()
    gemini._tool_gemini(
        SandboxConfig(),
        {"auth_host_path": "/a/oauth.json", "config_host_path": "/a/settings.json"},
        context,
    )
    assert "@google/gemini-cli" in context.npm_packages
    assert "/a/oauth.json:/home/agent/.gemini/oauth_creds.json" in context.volumes
    assert "/a/settings.json:/home/agent/.gemini/settings.json" in context.volumes


def test_tool_opencode_applies_install_command_and_mounts() -> None:
    context = BuildContext()
    opencode._tool_opencode(
        SandboxConfig(),
        {"auth_host_path": "/a/auth.json", "config_host_path": "/a/opencode.json"},
        context,
    )
    assert any("opencode.ai/install" in cmd for cmd in context.agent_commands)
    assert "/a/auth.json:/home/agent/.local/share/opencode/auth.json" in context.volumes
    assert "/a/opencode.json:/home/agent/.config/opencode/opencode.json" in context.volumes


def test_register_helpers_register_specs() -> None:
    AGENT_CLI_TOOLS.clear()
    codex.register_codex_tool()
    gemini.register_gemini_tool()
    opencode.register_opencode_tool()
    assert set(AGENT_CLI_TOOLS) == {"codex", "gemini", "opencode"}


def test_ensure_builtin_agent_cli_tools_registered_is_idempotent() -> None:
    from ctf_agent_sandbox import agent_cli_tools

    AGENT_CLI_TOOLS.clear()
    agent_cli_tools._LOADED = False
    ensure_builtin_agent_cli_tools_registered()
    first = set(AGENT_CLI_TOOLS)
    ensure_builtin_agent_cli_tools_registered()
    assert set(AGENT_CLI_TOOLS) == first
