"""Dockerd background service plugin."""

from __future__ import annotations

from ..models import SandboxConfig
from ..modules import BuildContext
from ..service_registry import register_background_service


def _service_dockerd(config: SandboxConfig, context: BuildContext) -> None:
    _ = config
    # Install docker engine package and start daemon in background.
    context.pacman_packages.add("docker")
    context.startup_commands.append("sudo dockerd > /tmp/dockerd.log 2>&1 &")


def register_dockerd_service() -> None:
    # Register dockerd background service plugin.
    register_background_service("dockerd", _service_dockerd)
