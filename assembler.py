"""Core functional assembler and Docker SDK runtime helpers."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import docker

from .background_services import ensure_builtin_background_services_registered
from .models import SandboxConfig, parse_config
from .modules import BuildContext, DEFAULT_PIPELINE
from .utils.docker_build import consume_build_logs
from .utils.runtime import (
    dedupe_list,
    generate_container_name,
    load_state,
    require_str_attr,
    to_docker_mounts,
    write_executable_file,
)
from .utils.template import render_template

STATE_FILE = Path(__file__).resolve().parent / ".sandbox_state.json"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
DOCKERFILE_TEMPLATE_FILE = TEMPLATE_DIR / "Dockerfile.tpl"
STARTUP_SCRIPT_TEMPLATE_FILE = TEMPLATE_DIR / "startup.sh.tpl"
ENV_SKILL_TEMPLATE_FILE = TEMPLATE_DIR / "env-skill.md.tpl"


@dataclass
class AssemblyResult:
    """Final artifacts generated from a single config object."""

    dockerfile: str
    startup_script: str
    container_options: dict[str, Any]


def assemble(
    config: SandboxConfig | dict[str, Any],
) -> AssemblyResult:
    """Build in-memory artifacts from a config object."""
    # Bootstrap built-in plugin registries before executing the assembly pipeline.
    ensure_builtin_background_services_registered()
    # Normalize raw dict/object input into a validated config model.
    parsed = parse_config(config)
    context = BuildContext()

    # Execute all pipeline modules in order to populate build context.
    for module_func in DEFAULT_PIPELINE:
        module_func(parsed, context)

    # Add workspace/startup mounts and deduplicate all volume specs.
    if parsed.workspace_host_path:
        context.volumes.append(f"{parsed.workspace_host_path}:{parsed.workspace_container_path}")
    context.volumes.append(f"{parsed.startup_script_host_path}:/startup.sh")
    context.volumes = dedupe_list(context.volumes)

    # Render final text artifacts and runtime options.
    return AssemblyResult(
        dockerfile=render_dockerfile(context),
        startup_script=render_startup_script(context),
        container_options=render_container_options(parsed, context),
    )


def assemble_and_write(
    config: SandboxConfig | dict[str, Any],
    output_dir: str | Path = ".",
    state_file: str | Path = STATE_FILE,
) -> AssemblyResult:
    """Assemble full artifacts and write files/state without building image."""
    # Parse config and ensure generated environment skill is ready.
    parsed = _prepare_assembly_config(config)
    result = assemble(config=parsed)

    # Write generated Docker build artifacts to target output directory.
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "Dockerfile").write_text(result.dockerfile, encoding="utf-8")
    startup_path = out_dir / "script" / "startup.sh"
    startup_path.parent.mkdir(parents=True, exist_ok=True)
    startup_path.write_text(result.startup_script, encoding="utf-8")
    startup_path.chmod(0o755)
    # Also write runtime startup script to the configured bind-mount host path.
    _write_runtime_startup_script(parsed.startup_script_host_path, result.startup_script)

    # Write state template for downstream runtime flow (image not built yet).
    payload = {
        "image_id": None,
        "run_params": result.container_options,
    }
    Path(state_file).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return result


def build_image(
    config: SandboxConfig | dict[str, Any],
    tag: str | None = None,
    verbose: bool = False,
) -> str:
    """Build image via Docker SDK and persist image/config state."""
    # Parse config and ensure generated environment skill is ready.
    parsed = _prepare_assembly_config(config)
    result = assemble(parsed)

    # Materialize temporary Docker build context and invoke Docker SDK image build.
    with tempfile.TemporaryDirectory(prefix="ctf-sandbox-build-") as tmp_dir:
        build_root = Path(tmp_dir)
        (build_root / "Dockerfile").write_text(result.dockerfile, encoding="utf-8")
        startup_path = build_root / "script" / "startup.sh"
        startup_path.parent.mkdir(parents=True, exist_ok=True)
        startup_path.write_text(result.startup_script, encoding="utf-8")

        # Build image through low-level API to support realtime log streaming.
        client = docker.from_env()
        image_tag = tag or parsed.image_name
        logs = client.api.build(
            path=str(build_root),
            tag=image_tag,
            rm=True,
            decode=True,
        )
        image_id = consume_build_logs(logs=logs, verbose=verbose)
        if not image_id:
            image = client.images.get(image_tag)
            image_id = require_str_attr(image, "id", "docker image")

    # Write runtime startup script to the configured bind-mount host path.
    _write_runtime_startup_script(parsed.startup_script_host_path, result.startup_script)

    # Persist runtime state used by `run_container`.
    payload = {
        "image_id": image_id,
        "run_params": result.container_options,
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return image_id


def run_container(
    state_file: str | Path = STATE_FILE,
) -> str:
    """Run a container from stored state and return container id."""
    # Resolve image id and run options from persisted state.
    state = load_state(state_file)
    image_ref = state["image_id"]
    opts = state["run_params"]
    if not isinstance(image_ref, str) or not image_ref:
        raise ValueError("state file has no built image_id; run build-image first")

    # Start one container with a generated unique name and return only container id.
    client = docker.from_env()
    container_name = generate_container_name(opts.get("name_prefix", "agent-sandbox"))
    container = client.containers.run(
        image_ref,
        detach=True,
        name=container_name,
        privileged=opts["privileged"],
        command=opts["command"],
        mounts=to_docker_mounts(opts["volumes"]),
    )
    container_id = require_str_attr(container, "id", "docker container")
    return container_id


def stop_container(container_id: str) -> None:
    """Stop and remove a container by id."""
    client = docker.from_env()
    container = client.containers.get(container_id)
    container.stop()
    container.remove()


def render_dockerfile(context: BuildContext) -> str:
    """Render Dockerfile text from accumulated context state."""
    pacman = " \\\n    ".join(sorted(context.pacman_packages))
    # Build dynamic template blocks from current context.
    pacman_block = ""
    if pacman:
        pacman_block = "\n".join(
            [
                "RUN pacman -Syu --noconfirm \\",
                f"    {pacman}",
            ]
        )
    copy_block = "\n".join(f"COPY {src} {dst}" for src, dst in context.copy_files)
    env_block = "\n".join(f"ENV {key}={value}" for key, value in context.env.items())
    root_commands_block = ""
    if context.root_commands:
        root_commands_block = "RUN " + " && \\\n    ".join(context.root_commands)
    agent_commands_block = ""
    if context.agent_commands:
        agent_commands_block = "RUN " + " && \\\n    ".join(context.agent_commands)
    yay_block = ""
    if context.yay_packages:
        yay_block = "\n".join(
            [
                "RUN cd ~ && git clone https://aur.archlinux.org/yay.git && cd yay && makepkg -si --noconfirm",
                "RUN yay -Syy --noconfirm --mflags \"--nocheck\" " + " ".join(sorted(context.yay_packages)),
            ]
        )
    npm_block = ""
    if context.npm_packages:
        npm_block = "RUN sudo npm install -g " + " ".join(sorted(context.npm_packages))
    gem_block = ""
    if context.gem_packages:
        gem_block = "\n".join(
            [
                "USER root",
                "RUN gem install " + " ".join(sorted(context.gem_packages)) + " --no-user-install",
                "USER agent",
            ]
        )
    pip_block = ""
    if context.pip_packages:
        pip_block = "RUN uv pip install --system " + " ".join(sorted(context.pip_packages))

    return render_template(
        DOCKERFILE_TEMPLATE_FILE,
        {
            "PACMAN_BLOCK": pacman_block,
            "COPY_BLOCK": copy_block,
            "ENV_BLOCK": env_block,
            "ROOT_COMMANDS_BLOCK": root_commands_block,
            "AGENT_COMMANDS_BLOCK": agent_commands_block,
            "YAY_BLOCK": yay_block,
            "NPM_BLOCK": npm_block,
            "GEM_BLOCK": gem_block,
            "PIP_BLOCK": pip_block,
        },
    )


def render_startup_script(context: BuildContext) -> str:
    """Render startup script that launches selected background services."""
    commands = context.startup_commands or ["true"]
    return render_template(
        STARTUP_SCRIPT_TEMPLATE_FILE,
        {
            "STARTUP_COMMANDS": "\n".join(commands),
        },
    )


def render_container_options(
    config: SandboxConfig,
    context: BuildContext,
) -> dict[str, Any]:
    """Render Docker SDK `containers.run(...)` options except image id."""
    return {
        "name_prefix": config.container_name_prefix,
        "privileged": context.privileged,
        "volumes": context.volumes,
        "command": "/bin/bash /startup.sh",
    }


def _prepare_assembly_config(config: SandboxConfig | dict[str, Any]) -> SandboxConfig:
    """Normalize config and apply generated sandbox environment skill path."""
    parsed = parse_config(config)
    generated_skill_path = _generate_sandbox_env_skill(parsed)
    if generated_skill_path:
        parsed.sandbox_env_skill_path = generated_skill_path
    return parsed


def _write_runtime_startup_script(host_path: str, content: str) -> None:
    """Write generated runtime startup script to configured host bind path."""
    write_executable_file(host_path, content)


def _generate_sandbox_env_skill(config: SandboxConfig) -> str | None:
    """Generate sandbox environment hint skill and return its host path."""
    if not config.sandbox_env_skill_path:
        return None

    # Prepare output directory and target skill file.
    skill_dir = Path(config.sandbox_env_skill_path).resolve()
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"

    # Build package summary grouped by configured package group names.
    package_sections: list[str] = []
    for group in config.packages:
        lines: list[str] = [f"### name: {group.name}"]
        if group.pacman:
            lines.append(f"- pacman: {', '.join(group.pacman)}")
        if group.yay:
            lines.append(f"- yay: {', '.join(group.yay)}")
        if group.npm:
            lines.append(f"- npm: {', '.join(group.npm)}")
        if group.pip:
            lines.append(f"- pip: {', '.join(group.pip)}")
        if group.gem:
            lines.append(f"- gem: {', '.join(group.gem)}")
        package_sections.append("\n".join(lines))

    # Build runtime summary blocks for services and agent CLI tools.
    service_names = [service.name for service in config.services]
    services = ", ".join(service_names) if service_names else "(none)"
    tool_names = [tool.name for tool in config.agent_cli_tools]
    tools = ", ".join(tool_names) if tool_names else "(none)"
    package_text = "\n\n".join(package_sections) if package_sections else "### name: Base\n- (no extra packages)"
    service_sections: list[str] = []
    for service in config.services:
        service_sections.append(f"### name: background-service:{service.name}")
        options = service.options
        if options:
            for key, value in options.items():
                service_sections.append(f"- {key}: {value}")
        else:
            service_sections.append("- options: (none)")
    service_text = "\n".join(service_sections) if service_sections else "### name: background-service\n- (none)"
    tool_sections: list[str] = []
    for tool in config.agent_cli_tools:
        tool_sections.append(f"### name: agent-cli-tool:{tool.name}")
        if tool.options:
            for key, value in tool.options.items():
                tool_sections.append(f"- {key}: {value}")
        else:
            tool_sections.append("- options: (none)")
    tool_text = "\n".join(tool_sections) if tool_sections else "### name: agent-cli-tool\n- (none)"

    # Emit final markdown content from skill template.
    content = render_template(
        ENV_SKILL_TEMPLATE_FILE,
        {
            "TIMEZONE": config.timezone,
            "LOCALE": config.locale.main,
            "SERVICES": services,
            "AGENT_CLI_TOOLS": tools,
            "WORKSPACE": config.workspace_container_path,
            "TOOL_SECTION": tool_text,
            "SERVICE_SECTION": service_text,
            "PACKAGE_SECTION": package_text,
        },
    )
    skill_file.write_text(content, encoding="utf-8")
    return str(skill_dir)
