"""Functional pipeline steps that mutate a shared build context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .models import SandboxConfig
from .service_registry import (
    apply_registered_background_services,
    collect_background_service_skills,
)

ModuleFunc = Callable[[SandboxConfig, "BuildContext"], None]


@dataclass
class BuildContext:
    """Accumulator object used while composing Docker and runtime outputs."""

    env: dict[str, str] = field(default_factory=dict)
    pacman_packages: set[str] = field(default_factory=set)
    yay_packages: set[str] = field(default_factory=set)
    gem_packages: set[str] = field(default_factory=set)
    npm_packages: set[str] = field(default_factory=set)
    pip_packages: set[str] = field(default_factory=set)

    copy_files: list[tuple[str, str]] = field(default_factory=list)
    root_commands: list[str] = field(default_factory=list)
    agent_commands: list[str] = field(default_factory=list)

    startup_commands: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    privileged: bool = True


def apply_timezone(config: SandboxConfig, context: BuildContext) -> None:
    """Apply timezone environment variable."""
    context.env["TZ"] = config.timezone


def apply_locale(config: SandboxConfig, context: BuildContext) -> None:
    """Generate locale setup commands and locale-related environment values."""
    context.root_commands.append(
        "printf '%s\\n' "
        + " ".join(f"'{line}'" for line in config.locale.install)
        + " > /etc/locale.gen"
    )
    context.root_commands.extend(
        [
            f"echo 'LANG={config.locale.main}' > /etc/locale.conf",
            "locale-gen",
        ]
    )
    context.env["LANG"] = config.locale.main
    context.env["LC_ALL"] = config.locale.main


def apply_background_services(config: SandboxConfig, context: BuildContext) -> None:
    """Install and wire enabled background services via registry dispatch."""
    apply_registered_background_services(config, context)


def apply_tools(config: SandboxConfig, context: BuildContext) -> None:
    """Install selected AI CLI tools and their optional auth/config mounts."""
    for tool in config.ai_cli_tools:
        if tool == "codex":
            context.npm_packages.add("@openai/codex")
            if config.codex_auth_host_path:
                context.volumes.append(
                    f"{config.codex_auth_host_path}:/home/agent/.codex/auth.json"
                )
            if config.codex_config_host_path:
                context.volumes.append(
                    f"{config.codex_config_host_path}:/home/agent/.codex/config.toml"
                )
        elif tool == "opencode":
            context.agent_commands.append("curl -fsSL https://opencode.ai/install | bash")
            if config.opencode_auth_host_path:
                context.volumes.append(
                    f"{config.opencode_auth_host_path}:/home/agent/.local/share/opencode/auth.json"
                )
            if config.opencode_config_host_path:
                context.volumes.append(
                    f"{config.opencode_config_host_path}:/home/agent/.config/opencode/opencode.json"
                )
        elif tool == "gemini":
            context.npm_packages.add("@google/gemini-cli")
            if config.gemini_auth_host_path:
                context.volumes.append(
                    f"{config.gemini_auth_host_path}:/home/agent/.gemini/oauth_creds.json"
                )
            if config.gemini_config_host_path:
                context.volumes.append(
                    f"{config.gemini_config_host_path}:/home/agent/.gemini/settings.json"
                )


def apply_packages(config: SandboxConfig, context: BuildContext) -> None:
    """Merge baseline packages with user-defined package groups."""
    context.pacman_packages.update(
        {
            "base-devel",
            "glibc",
            "wget",
            "curl",
            "zip",
            "unzip",
            "ripgrep",
            "file",
            "sudo",
            "git",
            "openssl",
            "gdb",
            "openbsd-netcat",
            "openssh",
            "vim",
            "ruby",
            "nodejs",
            "npm",
            "python",
            "python-uv",
        }
    )

    for group in config.packages:
        context.pacman_packages.update(group.pacman)
        context.yay_packages.update(group.yay)
        context.gem_packages.update(group.gem)
        context.npm_packages.update(group.npm)
        context.pip_packages.update(group.pip)


def apply_custom_install_commands(config: SandboxConfig, context: BuildContext) -> None:
    """Append user-defined install commands to root/agent execution phases."""
    for item in config.custom_install_commands:
        if item.run_as == "root":
            context.root_commands.append(item.command)
        else:
            context.agent_commands.append(item.command)


def apply_prompt(config: SandboxConfig, context: BuildContext) -> None:
    """Mount prompt file as AGENTS.md inside the workspace when provided."""
    if config.prompt_file:
        context.volumes.append(f"{config.prompt_file}:{config.workspace_container_path}/AGENTS.md")


def apply_skills(config: SandboxConfig, context: BuildContext) -> None:
    """Mount skill directories to CLI-specific skill locations."""
    skill_paths = list(config.skills)
    if config.sandbox_env_skill_path:
        skill_paths.insert(0, config.sandbox_env_skill_path)
    skill_paths.extend(collect_background_service_skills(config))

    tool_set = set(config.ai_cli_tools)
    for skill_path in skill_paths:
        skill_name = skill_path.rstrip("/").split("/")[-1]
        if "codex" in tool_set:
            context.volumes.append(f"{skill_path}:/home/agent/.codex/skills/{skill_name}")
        if "opencode" in tool_set:
            context.volumes.append(f"{skill_path}:/home/agent/.opencode/skills/{skill_name}")
        if "gemini" in tool_set:
            context.volumes.append(f"{skill_path}:/home/agent/.gemini/skills/{skill_name}")


DEFAULT_PIPELINE: list[ModuleFunc] = [
    # Execution order follows the planned assembly priority.
    apply_timezone,
    apply_locale,
    apply_background_services,
    apply_tools,
    apply_packages,
    apply_custom_install_commands,
    apply_prompt,
    apply_skills,
]
