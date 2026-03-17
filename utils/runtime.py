"""Runtime helper utilities for container assembly/run flows."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docker.types import Mount


def to_docker_mounts(volume_specs: list[str]) -> list[Mount]:
    """Convert `host:container[:ro]` specs into Docker SDK Mount objects."""
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


def load_state(state_file: str | Path) -> dict[str, Any]:
    """Load and validate persisted sandbox state payload."""
    path = Path(state_file)
    if not path.exists():
        raise FileNotFoundError(f"state file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "image_id" not in payload or "run_params" not in payload:
        raise ValueError(f"invalid state file: {path}")
    return payload


def dedupe_list(items: list[str]) -> list[str]:
    """Return a de-duplicated list while preserving input order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def generate_container_name(prefix: str) -> str:
    """Generate unique container name from prefix + timestamp + random suffix."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = secrets.token_hex(4)
    return f"{prefix}-{ts}-{suffix}"


def require_str_attr(obj: object, attr: str, label: str) -> str:
    """Read a dynamic SDK attribute and ensure it is a non-empty string."""
    value = getattr(obj, attr, None)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{label} missing valid `{attr}`")
    return value


def write_executable_file(path: str | Path, content: str) -> None:
    """Write text file and set executable mode."""
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    target.chmod(0o755)

