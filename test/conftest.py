"""Test bootstrap helpers."""

from __future__ import annotations

import sys
import types
from pathlib import Path


# Ensure package import works when tests run from repository root.
PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

# Provide a minimal docker SDK stub when docker is not installed in test env.
try:
    import docker  # type: ignore  # noqa: F401
except ModuleNotFoundError:
    docker_stub = types.ModuleType("docker")
    docker_types_stub = types.ModuleType("docker.types")

    class Mount(dict):
        """Minimal dict-like replacement for docker.types.Mount."""

        def __init__(self, target: str, source: str, type: str, read_only: bool = False) -> None:  # noqa: A002
            super().__init__(Target=target, Source=source, Type=type, ReadOnly=read_only)

    def _from_env():
        raise RuntimeError("docker.from_env stub called without monkeypatch")

    docker_stub.from_env = _from_env  # type: ignore[attr-defined]
    docker_types_stub.Mount = Mount  # type: ignore[attr-defined]
    docker_stub.types = docker_types_stub  # type: ignore[attr-defined]
    sys.modules["docker"] = docker_stub
    sys.modules["docker.types"] = docker_types_stub
