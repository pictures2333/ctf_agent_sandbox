"""Tests for assembly pipeline modules."""

from __future__ import annotations

from ctf_agent_sandbox.models import SandboxConfig
from ctf_agent_sandbox.modules import (
    BuildContext,
    DEFAULT_PIPELINE,
    apply_agent_cli_tools,
    apply_background_services,
    apply_custom_install_commands,
    apply_locale,
    apply_packages,
    apply_skills,
    apply_timezone,
)


def test_apply_timezone_sets_env() -> None:
    context = BuildContext()
    config = SandboxConfig(timezone="UTC")
    apply_timezone(config, context)
    assert context.env["TZ"] == "UTC"


def test_apply_locale_sets_commands_and_env() -> None:
    context = BuildContext()
    config = SandboxConfig.model_validate({"locale": {"main": "C.UTF-8", "install": ["C.UTF-8 UTF-8"]}})
    apply_locale(config, context)
    assert any("/etc/locale.gen" in cmd for cmd in context.root_commands)
    assert "locale-gen" in context.root_commands
    assert context.env["LANG"] == "C.UTF-8"
    assert context.env["LC_ALL"] == "C.UTF-8"


def test_apply_background_services_dispatches_registered_plugins() -> None:
    context = BuildContext()
    config = SandboxConfig.model_validate({"services": ["dockerd"]})
    apply_background_services(config, context)
    assert "docker" in context.pacman_packages


def test_apply_agent_cli_tools_dispatches_registered_plugins_and_prompt_mount() -> None:
    from ctf_agent_sandbox import agent_cli_tools

    # Ensure built-in plugins are re-registered even if previous tests cleared registry.
    agent_cli_tools._LOADED = False
    context = BuildContext()
    config = SandboxConfig.model_validate(
        {
            "prompt_file": "/host/AGENTS.md",
            "workspace_container_path": "/home/agent/challenge",
            "agent-cli-tools": [{"name": "codex", "options": {"prompt_filename": "AGENTS.md"}}],
        }
    )
    apply_agent_cli_tools(config, context)
    assert "@openai/codex" in context.npm_packages
    assert "/host/AGENTS.md:/home/agent/challenge/AGENTS.md" in context.volumes


def test_apply_packages_merges_defaults_and_custom_groups() -> None:
    context = BuildContext()
    config = SandboxConfig.model_validate(
        {
            "packages": [
                {
                    "name": "extra",
                    "pacman": ["htop"],
                    "yay": ["yay-a"],
                    "gem": ["rake"],
                    "npm": ["npm-a"],
                    "pip": ["pip-a"],
                }
            ]
        }
    )
    apply_packages(config, context)
    assert "base-devel" in context.pacman_packages
    assert "htop" in context.pacman_packages
    assert "yay-a" in context.yay_packages
    assert "rake" in context.gem_packages
    assert "npm-a" in context.npm_packages
    assert "pip-a" in context.pip_packages


def test_apply_custom_install_commands_routes_by_run_as() -> None:
    context = BuildContext()
    config = SandboxConfig.model_validate(
        {
            "custom_install_commands": [
                {"command": "echo root", "run_as": "root"},
                {"command": "echo agent", "run_as": "agent"},
            ]
        }
    )
    apply_custom_install_commands(config, context)
    assert "echo root" in context.root_commands
    assert "echo agent" in context.agent_commands


def test_apply_skills_mounts_env_explicit_and_service_skills() -> None:
    context = BuildContext()
    config = SandboxConfig.model_validate(
        {
            "sandbox_env_skill_path": "./.sandbox_generated/skills/sandbox-environment-hint",
            "skills": ["./skills/custom"],
            "services": ["mcp-terminal"],
            "agent-cli-tools": ["opencode"],
        }
    )
    apply_skills(config, context)
    assert "./.sandbox_generated/skills/sandbox-environment-hint:/home/agent/.opencode/skills/sandbox-environment-hint" in context.volumes
    assert "./skills/custom:/home/agent/.opencode/skills/custom" in context.volumes
    assert "./skills/mcp-terminal-operator:/home/agent/.opencode/skills/mcp-terminal-operator" in context.volumes


def test_default_pipeline_contains_all_module_steps() -> None:
    names = [f.__name__ for f in DEFAULT_PIPELINE]
    assert names == [
        "apply_timezone",
        "apply_locale",
        "apply_background_services",
        "apply_agent_cli_tools",
        "apply_packages",
        "apply_custom_install_commands",
        "apply_skills",
    ]
