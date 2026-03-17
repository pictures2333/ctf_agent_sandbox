"""Tests for public package API helpers."""

from __future__ import annotations

from ctf_agent_sandbox import __all__, assemble_from_object


def test_assemble_from_object_delegates_to_assemble(monkeypatch):
    import ctf_agent_sandbox

    class _Dummy:
        pass

    expected = _Dummy()
    monkeypatch.setattr(ctf_agent_sandbox, "assemble", lambda _cfg: expected)
    assert assemble_from_object({}) is expected


def test_public_api_symbols_exported() -> None:
    expected = {
        "STATE_FILE",
        "AssemblyResult",
        "assemble",
        "assemble_and_write",
        "build_image",
        "run_container",
        "stop_container",
        "AgentCliToolSpec",
        "register_agent_cli_tool",
        "register_background_service",
        "SandboxConfig",
        "parse_config",
    }
    assert set(__all__) == expected
