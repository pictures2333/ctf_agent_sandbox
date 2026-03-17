"""Tests for docker build log parsing helpers."""

from __future__ import annotations

import json

import pytest

from ctf_agent_sandbox.utils import docker_build as db


def test_normalize_build_log_entry_dict_and_bytes() -> None:
    assert db.normalize_build_log_entry({"stream": "ok"}, echo_raw=False) == {"stream": "ok"}
    payload = json.dumps({"status": "pull"})
    assert db.normalize_build_log_entry(payload.encode(), echo_raw=False) == {"status": "pull"}


def test_normalize_build_log_entry_invalid_text_returns_none(capsys: pytest.CaptureFixture[str]) -> None:
    assert db.normalize_build_log_entry("not-json", echo_raw=False) is None
    assert db.normalize_build_log_entry("not-json", echo_raw=True) is None
    assert "not-json" in capsys.readouterr().out


def test_extract_helpers() -> None:
    assert db.extract_image_id_from_log_entry({"aux": {"ID": "img123"}}) == "img123"
    assert db.extract_image_id_from_log_entry({"aux": {}}) is None
    assert db.extract_error_from_log_entry({"error": "boom"}) == "boom"
    assert db.extract_error_from_log_entry({"error": ""}) is None


def test_print_build_log_entry_outputs_known_fields(capsys: pytest.CaptureFixture[str]) -> None:
    db.print_build_log_entry({"stream": "S\n", "status": "PULL", "progress": "10%", "error": "E", "aux": {"ID": "x"}})
    out = capsys.readouterr().out
    assert "S" in out
    assert "PULL 10%" in out
    assert "E" in out
    assert "ID" in out


def test_consume_build_logs_returns_latest_image_id() -> None:
    logs = iter([{"aux": {"ID": "img1"}}, {"aux": {"ID": "img2"}}])
    assert db.consume_build_logs(logs, verbose=False) == "img2"


def test_consume_build_logs_raises_on_error() -> None:
    logs = iter([{"error": "failed"}])
    with pytest.raises(RuntimeError):
        db.consume_build_logs(logs, verbose=False)


def test_consume_build_logs_handles_non_iterable() -> None:
    assert db.consume_build_logs(None, verbose=False) is None
