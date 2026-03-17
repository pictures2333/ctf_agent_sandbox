"""Tests for built-in background service plugins."""

from __future__ import annotations

from ctf_agent_sandbox.background_services import ensure_builtin_background_services_registered
from ctf_agent_sandbox.background_services import dockerd, mcp_terminal
from ctf_agent_sandbox.models import SandboxConfig
from ctf_agent_sandbox.modules import BuildContext
from ctf_agent_sandbox.service_registry import (
    BACKGROUND_SERVICE_HANDLERS,
    BACKGROUND_SERVICE_SKILL_PROVIDERS,
)


def test_service_dockerd_adds_package_and_startup_command() -> None:
    context = BuildContext()
    dockerd._service_dockerd(SandboxConfig(), context)
    assert "docker" in context.pacman_packages
    assert any("dockerd" in cmd for cmd in context.startup_commands)


def test_service_mcp_terminal_adds_deps_startup_and_mount() -> None:
    context = BuildContext()
    config = SandboxConfig.model_validate(
        {"services": [{"name": "mcp-terminal", "options": {"host_path": "/host/mcp", "container_path": "/mcp"}}]}
    )
    mcp_terminal._service_mcp_terminal(config, context)
    assert "python-requests" in context.pacman_packages
    assert "python-mcp" in context.yay_packages
    assert any("uv run main.py" in cmd for cmd in context.startup_commands)
    assert "/host/mcp:/mcp" in context.volumes


def test_mcp_terminal_skill_paths_default_and_override() -> None:
    config_default = SandboxConfig.model_validate({"services": ["mcp-terminal"]})
    assert mcp_terminal._mcp_terminal_skill_paths(config_default) == ["./skills/mcp-terminal-operator"]

    config_none = SandboxConfig.model_validate(
        {"services": [{"name": "mcp-terminal", "options": {"skill_path": ""}}]}
    )
    assert mcp_terminal._mcp_terminal_skill_paths(config_none) == []


def test_register_service_helpers_register_handlers() -> None:
    BACKGROUND_SERVICE_HANDLERS.clear()
    BACKGROUND_SERVICE_SKILL_PROVIDERS.clear()
    dockerd.register_dockerd_service()
    mcp_terminal.register_mcp_terminal_service()
    assert "dockerd" in BACKGROUND_SERVICE_HANDLERS
    assert "mcp-terminal" in BACKGROUND_SERVICE_HANDLERS
    assert "mcp-terminal" in BACKGROUND_SERVICE_SKILL_PROVIDERS


def test_ensure_builtin_background_services_registered_is_idempotent() -> None:
    from ctf_agent_sandbox import background_services

    BACKGROUND_SERVICE_HANDLERS.clear()
    BACKGROUND_SERVICE_SKILL_PROVIDERS.clear()
    background_services._LOADED = False
    ensure_builtin_background_services_registered()
    first = set(BACKGROUND_SERVICE_HANDLERS)
    ensure_builtin_background_services_registered()
    assert set(BACKGROUND_SERVICE_HANDLERS) == first
