"""Configuration models for sandbox assembly."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocaleConfig(BaseModel):
    """Locale settings that become /etc/locale.* and LANG/LC_ALL values."""

    main: str = "en_US.UTF-8"
    install: list[str] = Field(default_factory=lambda: ["en_US.UTF-8 UTF-8"])


class PackageGroup(BaseModel):
    """A named package bundle grouped by package manager."""

    name: str
    pacman: list[str] = Field(default_factory=list)
    yay: list[str] = Field(default_factory=list)
    gem: list[str] = Field(default_factory=list)
    npm: list[str] = Field(default_factory=list)
    pip: list[str] = Field(default_factory=list)


class ServiceConfig(BaseModel):
    """One background service entry with per-service options."""

    name: str
    options: dict[str, str] = Field(default_factory=dict)


class AgentCliToolConfig(BaseModel):
    """One agent CLI tool entry with per-tool options."""

    name: str
    options: dict[str, str] = Field(default_factory=dict)


class CustomInstallCommand(BaseModel):
    """One custom install command with explicit execution user."""

    command: str
    run_as: Literal["root", "agent"] = "agent"


class SandboxConfig(BaseModel):
    """Single source-of-truth object consumed by the assembler pipeline."""

    # Allow alias-based input keys such as `agent-cli-tools`.
    model_config = ConfigDict(populate_by_name=True)

    # Runtime and tool/service orchestration settings.
    timezone: str = "Asia/Taipei"
    locale: LocaleConfig = Field(default_factory=LocaleConfig)
    services: list[ServiceConfig] = Field(default_factory=list)
    agent_cli_tools: list[AgentCliToolConfig] = Field(default_factory=list, alias="agent-cli-tools")
    packages: list[PackageGroup] = Field(default_factory=list)
    custom_install_commands: list[CustomInstallCommand] = Field(default_factory=list)
    prompt_file: str | None = None
    skills: list[str] = Field(default_factory=list)
    sandbox_env_skill_path: str | None = "./.sandbox_generated/skills/sandbox-environment-hint"

    # Image/runtime path and naming settings.
    image_name: str = "agent-sandbox"
    container_name_prefix: str = "agent-sandbox"
    workspace_host_path: str | None = None
    workspace_container_path: str = "/home/agent/challenge"
    startup_script_host_path: str = "./script/startup.sh"

    @field_validator("skills", mode="before")
    @classmethod
    def _normalize_skills(cls, value: Any) -> list[str]:
        """Accept both a single string and a list for `skills`."""
        # Normalize one-or-many skill entries into a list of strings.
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value]
        raise TypeError("skills must be string or list of strings")

    @field_validator("services", mode="before")
    @classmethod
    def _normalize_services(cls, value: Any) -> list[dict[str, Any]]:
        """Accept both legacy list[str] and list[{name, options}] formats."""
        # Normalize service entries to object form: {name, options}.
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("services must be a list")
        out: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, str):
                out.append({"name": item, "options": {}})
            elif isinstance(item, dict):
                name = item.get("name")
                if not isinstance(name, str):
                    raise TypeError("service item.name must be string")
                options = item.get("options", {})
                if not isinstance(options, dict):
                    raise TypeError("service item.options must be object")
                out.append({"name": name, "options": {str(k): str(v) for k, v in options.items()}})
            else:
                raise TypeError("service item must be string or object")
        return out

    @field_validator("agent_cli_tools", mode="before")
    @classmethod
    def _normalize_agent_cli_tools(cls, value: Any) -> list[dict[str, Any]]:
        """Accept both legacy list[str] and list[{name, options}] formats."""
        # Normalize tool entries to object form: {name, options}.
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("agent-cli-tools must be a list")
        out: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, str):
                out.append({"name": item, "options": {}})
            elif isinstance(item, dict):
                name = item.get("name")
                if not isinstance(name, str):
                    raise TypeError("agent-cli-tools item.name must be string")
                options = item.get("options", {})
                if not isinstance(options, dict):
                    raise TypeError("agent-cli-tools item.options must be object")
                out.append({"name": name, "options": {str(k): str(v) for k, v in options.items()}})
            else:
                raise TypeError("agent-cli-tools item must be string or object")
        return out

    @field_validator("custom_install_commands", mode="before")
    @classmethod
    def _normalize_custom_install_commands(cls, value: Any) -> list[dict[str, str]]:
        """Accept list[str] and list[{command, run_as}] for custom commands."""
        # Normalize custom install commands into explicit {command, run_as} objects.
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("custom_install_commands must be a list")
        out: list[dict[str, str]] = []
        for item in value:
            if isinstance(item, str):
                out.append({"command": item, "run_as": "agent"})
                continue
            if isinstance(item, dict):
                command = item.get("command")
                if not isinstance(command, str) or not command.strip():
                    raise TypeError("custom_install_commands item.command must be non-empty string")
                run_as = item.get("run_as", "agent")
                if run_as not in {"root", "agent"}:
                    raise TypeError("custom_install_commands item.run_as must be 'root' or 'agent'")
                out.append({"command": command, "run_as": run_as})
                continue
            raise TypeError("custom_install_commands item must be string or object")
        return out


def parse_config(config: SandboxConfig | dict[str, Any]) -> SandboxConfig:
    """Normalize raw dict/object input into a validated SandboxConfig."""
    if isinstance(config, SandboxConfig):
        return config
    return SandboxConfig.model_validate(config)
