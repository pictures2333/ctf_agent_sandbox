"""Tests for CLI helpers and command dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from ctf_agent_sandbox import cli


def test_load_config_reads_yaml_object(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("timezone: UTC\n", encoding="utf-8")
    config = cli._load_config(str(path))
    assert config.timezone == "UTC"


def test_load_config_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli._load_config(str(tmp_path / "missing.yaml"))


def test_load_config_non_object_yaml_raises(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("- a\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        cli._load_config(str(path))


def test_build_parser_has_expected_subcommands() -> None:
    parser = cli._build_parser()
    subparsers_action = next(a for a in parser._actions if getattr(a, "dest", None) == "command")
    assert set(subparsers_action.choices) == {"assemble", "build-image", "run-container", "stop-container"}


def test_main_dispatch_assemble(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}", encoding="utf-8")
    called: dict[str, object] = {}

    def _fake_assemble(config, output_dir, state_file):
        called["output_dir"] = output_dir
        called["state_file"] = state_file
        called["config"] = config

    monkeypatch.setattr(cli, "assemble_and_write", _fake_assemble)
    code = cli.main(["assemble", "--config", str(config_path), "--output-dir", "out", "--state-file", "s.json"])
    assert code == 0
    assert called["output_dir"] == "out"
    assert called["state_file"] == "s.json"


def test_main_dispatch_build_image(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli, "build_image", lambda config, tag, verbose: "img-1")
    code = cli.main(["build-image", "--config", str(config_path), "--tag", "x", "--verbose"])
    assert code == 0
    assert "img-1" in capsys.readouterr().out


def test_main_dispatch_run_container(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "run_container", lambda state_file: "ctr-1")
    code = cli.main(["run-container", "--state-file", "s.json"])
    assert code == 0
    assert "ctr-1" in capsys.readouterr().out


def test_main_dispatch_stop_container(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, str] = {}

    def _fake_stop(container_id: str) -> None:
        called["id"] = container_id

    monkeypatch.setattr(cli, "stop_container", _fake_stop)
    code = cli.main(["stop-container", "--container-id", "abc"])
    assert code == 0
    assert called["id"] == "abc"
