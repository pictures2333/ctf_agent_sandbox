"""Core functional assembler and Docker SDK runtime helpers."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import secrets
from typing import Any

import docker

from .background_services import ensure_builtin_background_services_registered
from .models import SandboxConfig, parse_config
from .modules import BuildContext, DEFAULT_PIPELINE, ModuleFunc

STATE_FILE = Path(__file__).resolve().parent / ".sandbox_state.json"


@dataclass
class AssemblyResult:
    """Final artifacts generated from a single config object."""

    dockerfile: str
    startup_script: str
    container_options: dict[str, Any]


def assemble(
    config: SandboxConfig | dict[str, Any],
    pipeline: list[ModuleFunc] | None = None,
) -> AssemblyResult:
    """Build in-memory artifacts from a config object and optional pipeline."""
    ensure_builtin_background_services_registered()
    parsed = parse_config(config)
    context = BuildContext()
    active_pipeline = pipeline or DEFAULT_PIPELINE

    for module_func in active_pipeline:
        module_func(parsed, context)

    if parsed.workspace_host_path:
        context.volumes.append(f"{parsed.workspace_host_path}:{parsed.workspace_container_path}")
    context.volumes.append(f"{parsed.startup_script_host_path}:/startup.sh")
    context.volumes = _dedupe_list(context.volumes)

    return AssemblyResult(
        dockerfile=render_dockerfile(context),
        startup_script=render_startup_script(context),
        container_options=render_container_options(parsed, context),
    )


def assemble_and_write(
    config: SandboxConfig | dict[str, Any],
    output_dir: str | Path = ".",
    pipeline: list[ModuleFunc] | None = None,
) -> AssemblyResult:
    """Assemble artifacts and write them to disk under `output_dir`."""
    result = assemble(config=config, pipeline=pipeline)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "Dockerfile").write_text(result.dockerfile, encoding="utf-8")
    startup_path = out_dir / "script" / "startup.sh"
    startup_path.parent.mkdir(parents=True, exist_ok=True)
    startup_path.write_text(result.startup_script, encoding="utf-8")
    startup_path.chmod(0o755)
    return result


def build_image(
    config: SandboxConfig | dict[str, Any],
    state_file: str | Path = STATE_FILE,
    pipeline: list[ModuleFunc] | None = None,
    tag: str | None = None,
) -> str:
    """Build image via Docker SDK and persist image/config state."""
    parsed = parse_config(config)
    generated_skill_path = _generate_sandbox_env_skill(parsed)
    if generated_skill_path:
        parsed.sandbox_env_skill_path = generated_skill_path
    result = assemble(parsed, pipeline=pipeline)

    with tempfile.TemporaryDirectory(prefix="ctf-sandbox-build-") as tmp_dir:
        build_root = Path(tmp_dir)
        (build_root / "Dockerfile").write_text(result.dockerfile, encoding="utf-8")
        startup_path = build_root / "script" / "startup.sh"
        startup_path.parent.mkdir(parents=True, exist_ok=True)
        startup_path.write_text(result.startup_script, encoding="utf-8")

        client = docker.from_env()
        image, _ = client.images.build(
            path=str(build_root),
            tag=tag or parsed.image_name,
            rm=True,
        )

    payload = {
        "image_id": image.id,
        "run_params": result.container_options,
    }
    Path(state_file).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return image.id


def run_container(
    config: SandboxConfig | dict[str, Any] | None = None,
    state_file: str | Path = STATE_FILE,
    pipeline: list[ModuleFunc] | None = None,
) -> str:
    """Run a container from stored state/config and return container id."""
    state = _load_state(state_file)
    image_ref = state["image_id"]

    if config is not None:
        parsed = parse_config(config)
        result = assemble(parsed, pipeline=pipeline)
        opts = result.container_options
    else:
        opts = state["run_params"]

    client = docker.from_env()
    container_name = _generate_container_name(opts.get("name_prefix", "agent-sandbox"))
    container = client.containers.run(
        image_ref,
        detach=True,
        name=container_name,
        privileged=opts["privileged"],
        command=opts["command"],
        volumes=_to_docker_volume_map(opts["volumes"]),
    )
    return container.id


def stop_container(container_id: str) -> None:
    """Stop and remove a container by id."""
    client = docker.from_env()
    container = client.containers.get(container_id)
    container.stop()
    container.remove()


def render_dockerfile(context: BuildContext) -> str:
    """Render Dockerfile text from accumulated context state."""
    pacman = " \\\n    ".join(sorted(context.pacman_packages))
    out: list[str] = ["FROM archlinux:latest", ""]

    if pacman:
        out.extend(
            [
                "RUN pacman -Syu --noconfirm \\",
                f"    {pacman}",
                "",
            ]
        )

    out.extend(
        [
            "RUN useradd -m agent && usermod -aG wheel,docker agent",
            "RUN printf '%s\\n' 'Defaults env_reset' 'root ALL=(ALL:ALL) ALL' '%wheel ALL=(ALL:ALL) NOPASSWD:ALL' > /etc/sudoers && chmod 440 /etc/sudoers",
            "",
        ]
    )

    for src, dst in context.copy_files:
        out.append(f"COPY {src} {dst}")

    for key, value in context.env.items():
        out.append(f"ENV {key}={value}")

    if context.root_commands:
        out.append("RUN " + " && \\\n    ".join(context.root_commands))

    out.extend(["", "USER agent"])

    if context.agent_commands:
        out.append("RUN " + " && \\\n    ".join(context.agent_commands))

    if context.yay_packages:
        out.extend(
            [
                "RUN cd ~ && git clone https://aur.archlinux.org/yay.git && cd yay && makepkg -si --noconfirm",
                "RUN yay -Syy --noconfirm --mflags \"--nocheck\" " + " ".join(sorted(context.yay_packages)),
            ]
        )

    if context.npm_packages:
        out.append("RUN sudo npm install -g " + " ".join(sorted(context.npm_packages)))

    if context.gem_packages:
        out.append("USER root")
        out.append("RUN gem install " + " ".join(sorted(context.gem_packages)) + " --no-user-install")
        out.append("USER agent")

    if context.pip_packages:
        out.append("RUN uv pip install --system " + " ".join(sorted(context.pip_packages)))

    out.extend(["WORKDIR /home/agent/challenge", ""])
    return "\n".join(out)


def render_startup_script(context: BuildContext) -> str:
    """Render startup script that launches selected background services."""
    commands = context.startup_commands or ["true"]
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n\n"
        f"{'\n'.join(commands)}\n"
        "tail -f /dev/null\n"
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


def _to_docker_volume_map(volume_specs: list[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for spec in volume_specs:
        parts = spec.split(":")
        if len(parts) < 2:
            continue
        host_path = str(Path(parts[0]).expanduser())
        bind_path = parts[1]
        mode = "ro" if len(parts) >= 3 and parts[2] == "ro" else "rw"
        out[host_path] = {"bind": bind_path, "mode": mode}
    return out


def _load_state(state_file: str | Path) -> dict[str, Any]:
    path = Path(state_file)
    if not path.exists():
        raise FileNotFoundError(f"state file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "image_id" not in payload or "run_params" not in payload:
        raise ValueError(f"invalid state file: {path}")
    return payload


def _dedupe_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _generate_container_name(prefix: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = secrets.token_hex(4)
    return f"{prefix}-{ts}-{suffix}"


def _generate_sandbox_env_skill(config: SandboxConfig) -> str | None:
    """Generate sandbox environment hint skill and return its host path."""
    if not config.sandbox_env_skill_path:
        return None

    skill_dir = Path(config.sandbox_env_skill_path).resolve()
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"

    package_sections: list[str] = []
    for group in config.packages:
        lines: list[str] = [f"## name: {group.name}"]
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

    service_names = [service.name for service in config.services]
    services = ", ".join(service_names) if service_names else "(none)"
    tools = ", ".join(config.ai_cli_tools) if config.ai_cli_tools else "(none)"
    package_text = "\n\n".join(package_sections) if package_sections else "## name: Base\n- (no extra packages)"
    service_sections: list[str] = []
    for service in config.services:
        service_sections.append(f"## name: background-service:{service.name}")
        options = service.options
        if options:
            for key, value in options.items():
                service_sections.append(f"- {key}: {value}")
        else:
            service_sections.append("- options: (none)")
    service_text = "\n".join(service_sections) if service_sections else "## name: background-service\n- (none)"

    content = "\n".join(
        [
            "---",
            "name: sandbox-environment-hint",
            "description: Auto-generated sandbox environment summary. Use this to understand installed tools and service topology before operating.",
            "---",
            "",
            "# Sandbox Environment Hint",
            "",
            "## Runtime Summary",
            f"- timezone: {config.timezone}",
            f"- locale: {config.locale.main}",
            f"- services: {services}",
            f"- ai_cli_tools: {tools}",
            f"- workspace: {config.workspace_container_path}",
            "",
            "## Built-in Notes",
            "- This skill is generated automatically during `build_image`.",
            "- Service-specific skills are mounted only when their service plugin is enabled.",
            "",
            "## Background Services",
            service_text,
            "",
            package_text,
            "",
        ]
    )
    skill_file.write_text(content, encoding="utf-8")
    return str(skill_dir)
