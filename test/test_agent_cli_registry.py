"""Tests for agent CLI tool registry helpers."""

from __future__ import annotations

from types import SimpleNamespace

from ctf_agent_sandbox.agent_cli_tools.registry import (
    AGENT_CLI_TOOLS,
    AgentCliToolSpec,
    apply_registered_agent_cli_tools,
    collect_agent_cli_prompt_volumes,
    collect_agent_cli_skill_volumes,
    get_agent_cli_tool_options,
    register_agent_cli_tool,
)
from ctf_agent_sandbox.models import SandboxConfig


def test_register_agent_cli_tool_overrides_entry() -> None:
    AGENT_CLI_TOOLS.clear()
    spec = AgentCliToolSpec(name="codex", handler=lambda _c, _o, _ctx: None, skills_mount_dir="/skills")
    register_agent_cli_tool(spec)
    assert AGENT_CLI_TOOLS["codex"] is spec


def test_apply_registered_agent_cli_tools_dispatches() -> None:
    AGENT_CLI_TOOLS.clear()
    called: list[str] = []
    register_agent_cli_tool(
        AgentCliToolSpec(
            name="codex",
            handler=lambda _c, _o, _ctx: called.append("codex"),
            skills_mount_dir="/skills",
        )
    )
    config = SandboxConfig.model_validate({"agent-cli-tools": ["codex", "missing"]})
    apply_registered_agent_cli_tools(config, SimpleNamespace())
    assert called == ["codex"]


def test_collect_agent_cli_prompt_volumes() -> None:
    AGENT_CLI_TOOLS.clear()
    register_agent_cli_tool(AgentCliToolSpec(name="codex", handler=lambda _c, _o, _ctx: None, skills_mount_dir="/x"))
    config = SandboxConfig.model_validate(
        {
            "prompt_file": "/host/AGENTS.md",
            "workspace_container_path": "/home/agent/challenge",
            "agent-cli-tools": [{"name": "codex", "options": {"prompt_filename": "AGENTS.md"}}],
        }
    )
    assert collect_agent_cli_prompt_volumes(config) == ["/host/AGENTS.md:/home/agent/challenge/AGENTS.md"]


def test_collect_agent_cli_prompt_volumes_without_prompt_file_returns_empty() -> None:
    config = SandboxConfig.model_validate({"agent-cli-tools": ["codex"]})
    assert collect_agent_cli_prompt_volumes(config) == []


def test_collect_agent_cli_skill_volumes() -> None:
    AGENT_CLI_TOOLS.clear()
    register_agent_cli_tool(
        AgentCliToolSpec(name="opencode", handler=lambda _c, _o, _ctx: None, skills_mount_dir="/home/agent/.opencode/skills")
    )
    config = SandboxConfig.model_validate({"agent-cli-tools": ["opencode"]})
    out = collect_agent_cli_skill_volumes(config, ["./skills/a", "./skills/b"])
    assert out == [
        "./skills/a:/home/agent/.opencode/skills/a",
        "./skills/b:/home/agent/.opencode/skills/b",
    ]


def test_get_agent_cli_tool_options_returns_target_or_empty() -> None:
    config = SandboxConfig.model_validate({"agent-cli-tools": [{"name": "codex", "options": {"k": "v"}}]})
    assert get_agent_cli_tool_options(config, "codex") == {"k": "v"}
    assert get_agent_cli_tool_options(config, "x") == {}
