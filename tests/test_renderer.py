"""Unit tests for :mod:`src.renderer`."""

from __future__ import annotations

from pathlib import Path

import pytest

from src import config
from src.renderer import render


@pytest.fixture
def base_context() -> dict[str, str]:
    return {
        "site_title": "Freelancer Scout",
        "source_url": "https://www.freelancermap.de/projekte",
        "source_label": "freelancermap.de",
        "repo_url": "https://github.com/example/freelancer-scout",
        "bootstrap_json": '{"updated_at":"2026-05-27T00:00:00+00:00","projects":[]}',
    }


def test_render_writes_file(tmp_path: Path, base_context: dict[str, str]) -> None:
    output = tmp_path / "index.html"
    render(config.TEMPLATE_INDEX, output, base_context)
    assert output.exists()
    assert output.stat().st_size > 0


def test_render_includes_site_title(tmp_path: Path, base_context: dict[str, str]) -> None:
    output = tmp_path / "index.html"
    render(config.TEMPLATE_INDEX, output, base_context)
    html = output.read_text(encoding="utf-8")
    # Title appears in <title> and in the visible <h1>
    assert "<title>Freelancer Scout</title>" in html
    assert "Freelancer" in html


def test_render_includes_three_required_fonts(tmp_path: Path, base_context: dict[str, str]) -> None:
    output = tmp_path / "index.html"
    render(config.TEMPLATE_INDEX, output, base_context)
    html = output.read_text(encoding="utf-8")
    assert "Fraunces" in html
    assert "Manrope" in html
    assert "JetBrains+Mono" in html
    assert "fonts.googleapis.com" in html


def test_render_includes_template_skeleton(tmp_path: Path, base_context: dict[str, str]) -> None:
    """The dynamic mount points must be present so app.js can hydrate."""
    output = tmp_path / "index.html"
    render(config.TEMPLATE_INDEX, output, base_context)
    html = output.read_text(encoding="utf-8")
    assert 'id="project-list"' in html
    assert 'id="filter-chips"' in html
    assert 'id="project-count"' in html
    assert 'id="last-updated"' in html
    assert 'id="card-template"' in html
    assert 'id="empty-state-template"' in html


def test_render_substitutes_context_values(tmp_path: Path, base_context: dict[str, str]) -> None:
    output = tmp_path / "index.html"
    custom = {**base_context, "site_title": "Custom Title", "repo_url": "https://example.org/repo"}
    render(config.TEMPLATE_INDEX, output, custom)
    html = output.read_text(encoding="utf-8")
    assert "Custom Title" in html
    assert "https://example.org/repo" in html


def test_render_creates_parent_directory(tmp_path: Path, base_context: dict[str, str]) -> None:
    output = tmp_path / "nested" / "out" / "index.html"
    render(config.TEMPLATE_INDEX, output, base_context)
    assert output.exists()


def test_render_loads_app_js_script(tmp_path: Path, base_context: dict[str, str]) -> None:
    output = tmp_path / "index.html"
    render(config.TEMPLATE_INDEX, output, base_context)
    html = output.read_text(encoding="utf-8")
    assert 'src="app.js"' in html
    assert 'href="style.css"' in html


def test_render_embeds_bootstrap_data(tmp_path: Path, base_context: dict[str, str]) -> None:
    output = tmp_path / "index.html"
    render(config.TEMPLATE_INDEX, output, base_context)
    html = output.read_text(encoding="utf-8")
    assert 'id="bootstrap-data"' in html
    assert '"updated_at"' in html
    assert '"projects"' in html
