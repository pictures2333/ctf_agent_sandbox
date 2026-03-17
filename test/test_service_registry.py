"""Tests for background service registry helpers."""

from __future__ import annotations

from types import SimpleNamespace

from ctf_agent_sandbox.models import SandboxConfig
from ctf_agent_sandbox.service_registry import (
    BACKGROUND_SERVICE_HANDLERS,
    BACKGROUND_SERVICE_SKILL_PROVIDERS,
    apply_registered_background_services,
    collect_background_service_skills,
    get_service_options,
    register_background_service,
)


def test_register_background_service_with_and_without_skill_provider() -> None:
    BACKGROUND_SERVICE_HANDLERS.clear()
    BACKGROUND_SERVICE_SKILL_PROVIDERS.clear()
    register_background_service("a", lambda _c, _ctx: None, skill_provider=lambda _c: ["x"])
    assert "a" in BACKGROUND_SERVICE_HANDLERS
    assert "a" in BACKGROUND_SERVICE_SKILL_PROVIDERS
    register_background_service("a", lambda _c, _ctx: None, skill_provider=None)
    assert "a" in BACKGROUND_SERVICE_HANDLERS
    assert "a" not in BACKGROUND_SERVICE_SKILL_PROVIDERS


def test_apply_registered_background_services_dispatches_enabled_services() -> None:
    BACKGROUND_SERVICE_HANDLERS.clear()
    called: list[str] = []
    register_background_service("dockerd", lambda _c, _ctx: called.append("dockerd"))
    config = SandboxConfig.model_validate({"services": ["dockerd", "missing"]})
    apply_registered_background_services(config, SimpleNamespace())
    assert called == ["dockerd"]


def test_collect_background_service_skills_aggregates_enabled_services() -> None:
    BACKGROUND_SERVICE_HANDLERS.clear()
    BACKGROUND_SERVICE_SKILL_PROVIDERS.clear()
    register_background_service("a", lambda _c, _ctx: None, skill_provider=lambda _c: ["s1"])
    register_background_service("b", lambda _c, _ctx: None, skill_provider=lambda _c: ["s2"])
    config = SandboxConfig.model_validate({"services": ["a", "b", "none"]})
    assert collect_background_service_skills(config) == ["s1", "s2"]


def test_get_service_options_returns_target_or_empty() -> None:
    config = SandboxConfig.model_validate({"services": [{"name": "x", "options": {"k": "v"}}]})
    assert get_service_options(config, "x") == {"k": "v"}
    assert get_service_options(config, "y") == {}
