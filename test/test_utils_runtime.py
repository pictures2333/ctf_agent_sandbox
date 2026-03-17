"""Tests for runtime utility helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ctf_agent_sandbox.utils.runtime import (
    dedupe_list,
    generate_container_name,
    load_state,
    require_str_attr,
    to_docker_mounts,
    write_executable_file,
)


def test_to_docker_mounts_parses_bind_and_ro(tmp_path: Path) -> None:
    host = tmp_path / "a"
    host.mkdir()
    mounts = to_docker_mounts([f"{host}:/container/a:ro", "invalid"])
    assert len(mounts) == 1
    assert mounts[0]["Target"] == "/container/a"
    assert mounts[0]["Type"] == "bind"
    assert mounts[0]["ReadOnly"] is True


def test_load_state_validates_schema(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"image_id": "img", "run_params": {"a": 1}}), encoding="utf-8")
    payload = load_state(state_path)
    assert payload["image_id"] == "img"


def test_load_state_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_state(tmp_path / "missing.json")


def test_load_state_raises_for_invalid_shape(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"image": "x"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_state(state_path)


def test_dedupe_list_preserves_order() -> None:
    assert dedupe_list(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_generate_container_name_format() -> None:
    name = generate_container_name("sandbox")
    assert name.startswith("sandbox-")
    assert len(name.split("-")) == 3


def test_require_str_attr_success_and_failure() -> None:
    obj = SimpleNamespace(id="abc")
    assert require_str_attr(obj, "id", "obj") == "abc"
    with pytest.raises(TypeError):
        require_str_attr(SimpleNamespace(id=None), "id", "obj")


def test_write_executable_file_writes_and_chmods(tmp_path: Path) -> None:
    target = tmp_path / "script.sh"
    write_executable_file(target, "echo hi\n")
    assert target.read_text(encoding="utf-8") == "echo hi\n"
    assert target.stat().st_mode & 0o111
