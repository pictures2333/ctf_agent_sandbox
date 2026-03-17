"""Core functional assembler and Docker SDK runtime helpers."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import secrets
from typing import Any

import docker
from docker.types import Mount

from .background_services import ensure_builtin_background_services_registered
from .models import SandboxConfig, parse_config
from .modules import BuildContext, DEFAULT_PIPELINE

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
    context.volumes = _dedupe_list(context.volumes)

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
        image_id = _consume_build_logs(logs=logs, verbose=verbose)
        if not image_id:
            image = client.images.get(image_tag)
            image_id = _require_str_attr(image, "id", "docker image")

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
    state = _load_state(state_file)
    image_ref = state["image_id"]
    opts = state["run_params"]
    if not isinstance(image_ref, str) or not image_ref:
        raise ValueError("state file has no built image_id; run build-image first")

    # Start one container with a generated unique name and return only container id.
    client = docker.from_env()
    container_name = _generate_container_name(opts.get("name_prefix", "agent-sandbox"))
    container = client.containers.run(
        image_ref,
        detach=True,
        name=container_name,
        privileged=opts["privileged"],
        command=opts["command"],
        mounts=_to_docker_mounts(opts["volumes"]),
    )
    container_id = _require_str_attr(container, "id", "docker container")
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

    return _render_template(
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
    return _render_template(
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


def _to_docker_mounts(volume_specs: list[str]) -> list[Mount]:
    out: list[Mount] = []
    for spec in volume_specs:
        parts = spec.split(":")
        if len(parts) < 2:
            continue
        # Docker SDK requires absolute host paths for bind mounts.
        host_path = str(Path(parts[0]).expanduser().resolve())
        bind_path = parts[1]
        read_only = len(parts) >= 3 and parts[2] == "ro"
        out.append(Mount(target=bind_path, source=host_path, type="bind", read_only=read_only))
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


def _require_str_attr(obj: object, attr: str, label: str) -> str:
    """Read a dynamic SDK attribute and ensure it is a string."""
    value = getattr(obj, attr, None)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{label} missing valid `{attr}`")
    return value


def _consume_build_logs(logs: Any, verbose: bool) -> str | None:
    """Consume Docker build logs, optionally print them, and capture image id."""
    if logs is None or not hasattr(logs, "__iter__"):
        return None

    image_id: str | None = None
    # Read the build stream until completion so Docker build fully finishes.
    for entry in logs:
        normalized = _normalize_build_log_entry(entry, echo_raw=verbose)
        if normalized is None:
            continue
        if verbose:
            _print_build_log_entry(normalized)
        captured = _extract_image_id_from_log_entry(normalized)
        if captured:
            image_id = captured
        error = _extract_error_from_log_entry(normalized)
        if error:
            raise RuntimeError(f"docker build failed: {error}")
    return image_id


def _print_build_log_entry(entry: Any) -> None:
    """Print one Docker build log entry across dict/bytes/string formats."""
    normalized = _normalize_build_log_entry(entry, echo_raw=True)
    if normalized is None:
        return

    # Raw stream chunks from build output.
    stream = normalized.get("stream")
    if isinstance(stream, str) and stream:
        print(stream, end="", flush=True)

    # Structured status/progress fields for pull/build steps.
    status = normalized.get("status")
    progress = normalized.get("progress")
    if isinstance(status, str) and status:
        if isinstance(progress, str) and progress:
            print(f"{status} {progress}", flush=True)
        else:
            print(status, flush=True)

    # Build errors and auxiliary metadata.
    error = normalized.get("error")
    if isinstance(error, str) and error:
        print(error, flush=True)
    aux = normalized.get("aux")
    if isinstance(aux, dict) and aux:
        print(aux, flush=True)


def _extract_image_id_from_log_entry(entry: Any) -> str | None:
    """Extract built image id from Docker log entry when available."""
    normalized = _normalize_build_log_entry(entry, echo_raw=False)
    if normalized is None:
        return None
    aux = normalized.get("aux")
    if not isinstance(aux, dict):
        return None
    image_id = aux.get("ID")
    return image_id if isinstance(image_id, str) and image_id else None


def _extract_error_from_log_entry(entry: Any) -> str | None:
    """Extract build error message from Docker log entry when present."""
    normalized = _normalize_build_log_entry(entry, echo_raw=False)
    if normalized is None:
        return None
    error = normalized.get("error")
    return error if isinstance(error, str) and error else None


def _normalize_build_log_entry(entry: Any, echo_raw: bool) -> dict[str, Any] | None:
    """Normalize Docker SDK log entry into a dictionary payload."""
    if isinstance(entry, dict):
        return entry
    if isinstance(entry, (bytes, bytearray)):
        text = entry.decode("utf-8", errors="replace").strip()
    elif isinstance(entry, str):
        text = entry.strip()
    else:
        return None
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        if echo_raw:
            print(text, flush=True)
        return None
    return payload if isinstance(payload, dict) else None


def _prepare_assembly_config(config: SandboxConfig | dict[str, Any]) -> SandboxConfig:
    """Normalize config and apply generated sandbox environment skill path."""
    parsed = parse_config(config)
    generated_skill_path = _generate_sandbox_env_skill(parsed)
    if generated_skill_path:
        parsed.sandbox_env_skill_path = generated_skill_path
    return parsed


def _write_runtime_startup_script(host_path: str, content: str) -> None:
    """Write generated runtime startup script to configured host bind path."""
    target = Path(host_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    target.chmod(0o755)


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

    # Build runtime summary blocks for services and agent CLI tools.
    service_names = [service.name for service in config.services]
    services = ", ".join(service_names) if service_names else "(none)"
    tool_names = [tool.name for tool in config.agent_cli_tools]
    tools = ", ".join(tool_names) if tool_names else "(none)"
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
    tool_sections: list[str] = []
    for tool in config.agent_cli_tools:
        tool_sections.append(f"## name: agent-cli-tool:{tool.name}")
        if tool.options:
            for key, value in tool.options.items():
                tool_sections.append(f"- {key}: {value}")
        else:
            tool_sections.append("- options: (none)")
    tool_text = "\n".join(tool_sections) if tool_sections else "## name: agent-cli-tool\n- (none)"

    # Emit final markdown content from skill template.
    content = _render_template(
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


def _render_template(template_path: Path, values: dict[str, str]) -> str:
    """Render a template file by replacing `{{KEY}}` placeholders."""
    # Load template source from repository templates directory.
    template = template_path.read_text(encoding="utf-8")
    # Replace all supported placeholders with rendered block text.
    for key, value in values.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    # Fail fast if any placeholder key was left unresolved.
    unresolved = re.findall(r"\{\{[A-Z0-9_]+\}\}", template)
    if unresolved:
        missing = ", ".join(sorted(set(unresolved)))
        raise ValueError(f"unresolved template placeholders in {template_path.name}: {missing}")
    return template
