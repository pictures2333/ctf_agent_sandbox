"""Docker build stream parsing helpers."""

from __future__ import annotations

import json
from typing import Any


def consume_build_logs(logs: Any, verbose: bool) -> str | None:
    """Consume Docker build logs, optionally print them, and capture image id."""
    if logs is None or not hasattr(logs, "__iter__"):
        return None

    image_id: str | None = None
    # Read the build stream until completion so Docker build fully finishes.
    for entry in logs:
        normalized = normalize_build_log_entry(entry, echo_raw=verbose)
        if normalized is None:
            continue
        if verbose:
            print_build_log_entry(normalized)
        captured = extract_image_id_from_log_entry(normalized)
        if captured:
            image_id = captured
        error = extract_error_from_log_entry(normalized)
        if error:
            raise RuntimeError(f"docker build failed: {error}")
    return image_id


def print_build_log_entry(entry: Any) -> None:
    """Print one Docker build log entry across dict/bytes/string formats."""
    normalized = normalize_build_log_entry(entry, echo_raw=True)
    if normalized is None:
        return

    # Raw stream chunks from build output.
    stream = normalized.get("stream")
    if isinstance(stream, str) and stream:
        print(stream, end="", flush=True)

    # Structured status/progress fields for pull/build steps.
    status = normalized.get("status")
    progress = normalized.get("progress")
    if isinstance(status, str) and status:
        if isinstance(progress, str) and progress:
            print(f"{status} {progress}", flush=True)
        else:
            print(status, flush=True)

    # Build errors and auxiliary metadata.
    error = normalized.get("error")
    if isinstance(error, str) and error:
        print(error, flush=True)
    aux = normalized.get("aux")
    if isinstance(aux, dict) and aux:
        print(aux, flush=True)


def extract_image_id_from_log_entry(entry: Any) -> str | None:
    """Extract built image id from Docker log entry when available."""
    normalized = normalize_build_log_entry(entry, echo_raw=False)
    if normalized is None:
        return None
    aux = normalized.get("aux")
    if not isinstance(aux, dict):
        return None
    image_id = aux.get("ID")
    return image_id if isinstance(image_id, str) and image_id else None


def extract_error_from_log_entry(entry: Any) -> str | None:
    """Extract build error message from Docker log entry when present."""
    normalized = normalize_build_log_entry(entry, echo_raw=False)
    if normalized is None:
        return None
    error = normalized.get("error")
    return error if isinstance(error, str) and error else None


def normalize_build_log_entry(entry: Any, echo_raw: bool) -> dict[str, Any] | None:
    """Normalize Docker SDK log entry into a dictionary payload."""
    if isinstance(entry, dict):
        return entry
    if isinstance(entry, (bytes, bytearray)):
        text = entry.decode("utf-8", errors="replace").strip()
    elif isinstance(entry, str):
        text = entry.strip()
    else:
        return None
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        if echo_raw:
            print(text, flush=True)
        return None
    return payload if isinstance(payload, dict) else None

