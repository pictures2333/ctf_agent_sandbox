"""Tests for template rendering utility."""

from __future__ import annotations

from pathlib import Path

import pytest

from ctf_agent_sandbox.utils.template import render_template


def test_render_template_replaces_placeholders(tmp_path: Path) -> None:
    template = tmp_path / "a.tpl"
    template.write_text("X={{KEY}}\n", encoding="utf-8")
    assert render_template(template, {"KEY": "1"}) == "X=1\n"


def test_render_template_raises_for_unresolved_placeholder(tmp_path: Path) -> None:
    template = tmp_path / "a.tpl"
    template.write_text("X={{MISSING}}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        render_template(template, {})
