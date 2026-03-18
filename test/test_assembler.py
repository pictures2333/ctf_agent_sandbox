"""Tests for assembler runtime and rendering helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ctf_agent_sandbox import assembler
from ctf_agent_sandbox.models import SandboxConfig
from ctf_agent_sandbox.modules import BuildContext


def test_render_dockerfile_and_startup_and_container_options() -> None:
    context = BuildContext()
    context.pacman_packages.update({"git", "curl"})
    context.copy_files.append(("a", "b"))
    context.env["TZ"] = "UTC"
    context.root_commands.append("echo root")
    context.agent_commands.append("echo agent")
    context.yay_packages.add("yay-pkg")
    context.npm_packages.add("npm-pkg")
    context.gem_packages.add("gem-pkg")
    context.pip_packages.add("pip-pkg")
    context.startup_commands.append("echo startup")
    context.volumes.append("/h:/c")
    config = SandboxConfig()

    dockerfile = assembler.render_dockerfile(context)
    startup = assembler.render_startup_script(context)
    opts = assembler.render_container_options(config, context)

    assert "FROM archlinux:latest" in dockerfile
    assert "RUN pacman -Syu --noconfirm" in dockerfile
    assert "COPY a b" in dockerfile
    assert "ENV TZ=UTC" in dockerfile
    assert "echo startup" in startup
    assert opts["name_prefix"] == config.container_name_prefix
    assert opts["command"] == "/bin/bash /startup.sh"


def test_assemble_adds_workspace_and_startup_mounts_and_dedupes() -> None:
    config = SandboxConfig.model_validate(
        {
            "workspace_host_path": "/host/workspace",
            "workspace_container_path": "/home/agent/challenge",
            "startup_script_host_path": "/host/startup.sh",
            "services": ["dockerd"],
        }
    )
    result = assembler.assemble(config)
    assert "/host/workspace:/home/agent/challenge" in result.container_options["volumes"]
    assert "/host/startup.sh:/startup.sh" in result.container_options["volumes"]


def test_assemble_and_write_outputs_files_and_state(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    startup_host = tmp_path / "runtime" / "startup.sh"
    skill_dir = tmp_path / "skills" / "env-hint"
    config = SandboxConfig.model_validate(
        {
            "services": ["dockerd"],
            "startup_script_host_path": str(startup_host),
            "sandbox_env_skill_path": str(skill_dir),
        }
    )
    result = assembler.assemble_and_write(config, work_dir=work_dir)
    assert (work_dir / "Dockerfile").exists()
    assert (work_dir / "script" / "startup.sh").exists()
    assert startup_host.exists()
    payload = json.loads((work_dir / ".state.json").read_text(encoding="utf-8"))
    assert payload["image_id"] is None
    assert payload["run_params"] == result.container_options


class _FakeImage:
    def __init__(self, image_id: str) -> None:
        self.id = image_id


class _FakeImages:
    def __init__(self, image_id: str) -> None:
        self._image_id = image_id

    def get(self, _tag: str) -> _FakeImage:
        return _FakeImage(self._image_id)


class _FakeContainers:
    def __init__(self, container_id: str) -> None:
        self._container_id = container_id
        self.last_run_kwargs: dict[str, object] | None = None
        self.last_get_id: str | None = None
        self.obj = SimpleNamespace(
            id=container_id,
            stop=lambda: setattr(self, "stopped", True),
            remove=lambda: setattr(self, "removed", True),
        )
        self.stopped = False
        self.removed = False

    def run(self, image_ref: str, **kwargs: object) -> SimpleNamespace:
        self.last_run_kwargs = {"image_ref": image_ref, **kwargs}
        return SimpleNamespace(id=self._container_id)

    def get(self, container_id: str) -> SimpleNamespace:
        self.last_get_id = container_id
        return self.obj


class _FakeAPI:
    def __init__(self, logs: list[dict[str, object]]) -> None:
        self._logs = logs
        self.build_calls: list[dict[str, object]] = []

    def build(self, **kwargs: object):
        self.build_calls.append(kwargs)
        return iter(self._logs)


class _FakeDockerClient:
    def __init__(self, image_id: str, container_id: str, logs: list[dict[str, object]]) -> None:
        self.images = _FakeImages(image_id)
        self.containers = _FakeContainers(container_id)
        self.api = _FakeAPI(logs)


def test_build_image_writes_state_and_returns_image_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = _FakeDockerClient("img-fallback", "ctr-1", [{"aux": {"ID": "img-from-log"}}])
    monkeypatch.setattr(assembler.docker, "from_env", lambda: fake)
    startup_host = tmp_path / "runtime" / "startup.sh"
    skill_dir = tmp_path / "skills" / "env-hint"
    work_dir = tmp_path / "work"
    config = SandboxConfig.model_validate(
        {
            "startup_script_host_path": str(startup_host),
            "sandbox_env_skill_path": str(skill_dir),
        }
    )
    image_id = assembler.build_image(config, tag="custom-tag", verbose=False, work_dir=work_dir)
    assert image_id == "img-from-log"
    payload = json.loads((work_dir / ".state.json").read_text(encoding="utf-8"))
    assert payload["image_id"] == "img-from-log"
    assert startup_host.exists()


def test_run_container_reads_state_and_returns_container_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = _FakeDockerClient("img", "ctr-xyz", [])
    monkeypatch.setattr(assembler.docker, "from_env", lambda: fake)
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    state_file = work_dir / ".state.json"
    state_file.write_text(
        json.dumps(
            {
                "image_id": "img-1",
                "run_params": {
                    "name_prefix": "sandbox",
                    "privileged": True,
                    "command": "/bin/bash /startup.sh",
                    "volumes": [f"{tmp_path}:/home/agent/challenge"],
                },
            }
        ),
        encoding="utf-8",
    )
    container_id = assembler.run_container(work_dir=work_dir)
    assert container_id == "ctr-xyz"
    assert fake.containers.last_run_kwargs is not None
    assert fake.containers.last_run_kwargs["image_ref"] == "img-1"


def test_run_container_raises_when_image_id_missing(tmp_path: Path) -> None:
    state_file = tmp_path / ".state.json"
    state_file.write_text(json.dumps({"image_id": None, "run_params": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        assembler.run_container(work_dir=tmp_path)


def test_stop_container_calls_stop_and_remove(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeDockerClient("img", "ctr-xyz", [])
    monkeypatch.setattr(assembler.docker, "from_env", lambda: fake)
    assembler.stop_container("ctr-xyz")
    assert fake.containers.last_get_id == "ctr-xyz"
    assert fake.containers.stopped is True
    assert fake.containers.removed is True


def test_prepare_assembly_config_sets_generated_skill_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assembler, "_generate_sandbox_env_skill", lambda _config: "/tmp/generated-skill")
    parsed = assembler._prepare_assembly_config({})
    assert parsed.sandbox_env_skill_path == "/tmp/generated-skill"


def test_write_runtime_startup_script_delegates_to_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, str] = {}

    def _fake_write(path: str, content: str) -> None:
        called["path"] = path
        called["content"] = content

    monkeypatch.setattr(assembler, "write_executable_file", _fake_write)
    assembler._write_runtime_startup_script("/tmp/startup.sh", "echo hi")
    assert called == {"path": "/tmp/startup.sh", "content": "echo hi"}


def test_generate_sandbox_env_skill_writes_markdown(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "sandbox-environment-hint"
    config = SandboxConfig.model_validate(
        {
            "timezone": "UTC",
            "services": [{"name": "mcp-terminal", "options": {"host_path": "/mcp"}}],
            "agent-cli-tools": [{"name": "codex", "options": {"prompt_filename": "AGENTS.md"}}],
            "packages": [{"name": "web", "pacman": ["curl"], "pip": ["pwntools"]}],
            "sandbox_env_skill_path": str(skill_dir),
        }
    )
    out = assembler._generate_sandbox_env_skill(config)
    assert out == str(skill_dir)
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "timezone: UTC" in text
    assert "background-service:mcp-terminal" in text
    assert "services: mcp-terminal" in text
    assert "### name: web" in text


def test_generate_sandbox_env_skill_returns_none_when_disabled() -> None:
    config = SandboxConfig(sandbox_env_skill_path=None)
    assert assembler._generate_sandbox_env_skill(config) is None
