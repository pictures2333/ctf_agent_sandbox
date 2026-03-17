"""Background service registry and helpers."""

from __future__ import annotations

from typing import Any, Callable

from .models import SandboxConfig

BackgroundServiceHandler = Callable[[SandboxConfig, Any], None]
BackgroundServiceSkillProvider = Callable[[SandboxConfig], list[str]]

BACKGROUND_SERVICE_HANDLERS: dict[str, BackgroundServiceHandler] = {}
BACKGROUND_SERVICE_SKILL_PROVIDERS: dict[str, BackgroundServiceSkillProvider] = {}


def register_background_service(
    name: str,
    handler: BackgroundServiceHandler,
    skill_provider: BackgroundServiceSkillProvider | None = None,
) -> None:
    """Register or override a background service handler."""
    # Register service behavior callback.
    BACKGROUND_SERVICE_HANDLERS[name] = handler

    # Register optional skill-path provider callback.
    if skill_provider is None:
        BACKGROUND_SERVICE_SKILL_PROVIDERS.pop(name, None)
    else:
        BACKGROUND_SERVICE_SKILL_PROVIDERS[name] = skill_provider


def apply_registered_background_services(config: SandboxConfig, context: Any) -> None:
    """Apply registered handlers for all enabled services."""
    # Dispatch each configured service to its registered handler.
    for service in config.services:
        handler = BACKGROUND_SERVICE_HANDLERS.get(service.name)
        if handler is None:
            continue
        handler(config, context)


def collect_background_service_skills(config: SandboxConfig) -> list[str]:
    """Collect extra skill paths from enabled background service providers."""
    skill_paths: list[str] = []
    # Collect skill paths exposed by enabled service plugins.
    for service in config.services:
        provider = BACKGROUND_SERVICE_SKILL_PROVIDERS.get(service.name)
        if provider is None:
            continue
        skill_paths.extend(provider(config))
    return skill_paths


def get_service_options(config: SandboxConfig, service_name: str) -> dict[str, str]:
    """Read normalized service-specific options from services array."""
    for service in config.services:
        if service.name == service_name:
            return service.options
    return {}
