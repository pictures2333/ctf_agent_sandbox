"""Configuration models for sandbox assembly."""

from __future__ import annotations

from typing import Any

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


class SandboxConfig(BaseModel):
    """Single source-of-truth object consumed by the assembler pipeline."""

    model_config = ConfigDict(populate_by_name=True)

    timezone: str = "Asia/Taipei"
    locale: LocaleConfig = Field(default_factory=LocaleConfig)
    services: list[ServiceConfig] = Field(default_factory=list)
    ai_cli_tools: list[str] = Field(default_factory=list, alias="ai-cli-tools")
    packages: list[PackageGroup] = Field(default_factory=list)
    prompt_file: str | None = None
    skills: list[str] = Field(default_factory=list)
    sandbox_env_skill_path: str | None = "./.sandbox_generated/skills/sandbox-environment-hint"

    image_name: str = "agent-sandbox"
    container_name_prefix: str = "agent-sandbox"
    workspace_host_path: str | None = None
    workspace_container_path: str = "/home/agent/challenge"
    startup_script_host_path: str = "./script/startup.sh"

    codex_auth_host_path: str | None = "~/.codex/auth.json"
    codex_config_host_path: str | None = "~/.codex/config.toml"
    gemini_auth_host_path: str | None = "~/.gemini/oauth_creds.json"
    gemini_config_host_path: str | None = "~/.gemini/settings.json"
    opencode_auth_host_path: str | None = "~/.local/share/opencode/auth.json"
    opencode_config_host_path: str | None = "~/.config/opencode/opencode.json"

    @field_validator("skills", mode="before")
    @classmethod
    def _normalize_skills(cls, value: Any) -> list[str]:
        """Accept both a single string and a list for `skills`."""
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


def parse_config(config: SandboxConfig | dict[str, Any]) -> SandboxConfig:
    """Normalize raw dict/object input into a validated SandboxConfig."""
    if isinstance(config, SandboxConfig):
        return config
    return SandboxConfig.model_validate(config)
