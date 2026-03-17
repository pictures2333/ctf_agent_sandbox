"""Tests for configuration models and normalization helpers."""

from __future__ import annotations

import pytest

from ctf_agent_sandbox.models import SandboxConfig, parse_config


def test_parse_config_with_model_instance_returns_same_object() -> None:
    config = SandboxConfig()
    assert parse_config(config) is config


def test_parse_config_with_dict_normalizes_alias_and_lists() -> None:
    config = parse_config(
        {
            "skills": "skills/a",
            "services": ["dockerd", {"name": "mcp-terminal", "options": {"k": 1}}],
            "agent-cli-tools": ["codex", {"name": "gemini", "options": {"prompt_filename": "GEMINI.md"}}],
            "custom_install_commands": ["echo hi", {"command": "echo root", "run_as": "root"}],
        }
    )
    assert config.skills == ["skills/a"]
    assert [s.name for s in config.services] == ["dockerd", "mcp-terminal"]
    assert config.services[1].options == {"k": "1"}
    assert [t.name for t in config.agent_cli_tools] == ["codex", "gemini"]
    assert config.custom_install_commands[0].run_as == "agent"
    assert config.custom_install_commands[1].run_as == "root"


def test_invalid_skills_type_raises() -> None:
    with pytest.raises(Exception):
        SandboxConfig.model_validate({"skills": 123})


def test_invalid_services_type_raises() -> None:
    with pytest.raises(Exception):
        SandboxConfig.model_validate({"services": "dockerd"})


def test_invalid_agent_cli_tools_type_raises() -> None:
    with pytest.raises(Exception):
        SandboxConfig.model_validate({"agent-cli-tools": "codex"})


def test_invalid_custom_install_commands_run_as_raises() -> None:
    with pytest.raises(Exception):
        SandboxConfig.model_validate({"custom_install_commands": [{"command": "x", "run_as": "bad"}]})
