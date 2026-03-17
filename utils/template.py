"""Template rendering helpers."""

from __future__ import annotations

import re
from pathlib import Path


def render_template(template_path: Path, values: dict[str, str]) -> str:
    """Render a template file by replacing `{{KEY}}` placeholders."""
    # Load template source from repository templates directory.
    template = template_path.read_text(encoding="utf-8")
    # Replace all supported placeholders with rendered block text.
    for key, value in values.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    # Fail fast if any placeholder key was left unresolved.
    unresolved = re.findall(r"\{\{[A-Z0-9_]+\}\}", template)
    if unresolved:
        missing = ", ".join(sorted(set(unresolved)))
        raise ValueError(f"unresolved template placeholders in {template_path.name}: {missing}")
    return template

