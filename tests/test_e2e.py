"""End-to-end pipeline test.

Mocks the HTTP layer, runs ``main()``, and verifies that all three
output files exist and are valid. Marked ``@pytest.mark.e2e``; excluded
from the default suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import main
from src import config

pytestmark = pytest.mark.e2e

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.html"


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Redirect every output path to ``tmp_path`` while keeping inputs real."""
    paths = {
        "data_dir": tmp_path / "data",
        "docs_dir": tmp_path / "docs",
        "projects_json": tmp_path / "data" / "projects.json",
        "docs_data_json": tmp_path / "docs" / "data.json",
        "docs_index_html": tmp_path / "docs" / "index.html",
    }
    monkeypatch.setattr(config, "DATA_DIR", paths["data_dir"])
    monkeypatch.setattr(config, "DOCS_DIR", paths["docs_dir"])
    monkeypatch.setattr(config, "PROJECTS_JSON", paths["projects_json"])
    monkeypatch.setattr(config, "DOCS_DATA_JSON", paths["docs_data_json"])
    monkeypatch.setattr(config, "DOCS_INDEX_HTML", paths["docs_index_html"])
    return paths


def test_full_pipeline_with_mocked_http(isolated: dict[str, Path], mocker) -> None:
    response = mocker.Mock()
    response.status_code = 200
    response.text = FIXTURE.read_text(encoding="utf-8")
    mocker.patch("src.crawler.requests.get", return_value=response)

    exit_code = main.main()

    assert exit_code == 0
    assert isolated["projects_json"].exists()
    assert isolated["docs_data_json"].exists()
    assert isolated["docs_index_html"].exists()


def test_pipeline_writes_valid_projects_json(isolated: dict[str, Path], mocker) -> None:
    response = mocker.Mock()
    response.status_code = 200
    response.text = FIXTURE.read_text(encoding="utf-8")
    mocker.patch("src.crawler.requests.get", return_value=response)

    main.main()

    raw = json.loads(isolated["projects_json"].read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) == 3  # fixture has 3 projects
    for item in raw:
        assert {"id", "title", "url", "description", "published", "source", "first_seen"} <= set(
            item
        )


def test_pipeline_writes_filtered_docs_data_with_wrapper(isolated: dict[str, Path], mocker) -> None:
    response = mocker.Mock()
    response.status_code = 200
    response.text = FIXTURE.read_text(encoding="utf-8")
    mocker.patch("src.crawler.requests.get", return_value=response)

    main.main()

    payload = json.loads(isolated["docs_data_json"].read_text(encoding="utf-8"))
    assert "updated_at" in payload
    assert "projects" in payload
    # Fixture: 3 projects, "Java Entwickler" is on the negative list, the
    # other two should hit positive keywords -> 2 relevant items.
    titles = [p["title"] for p in payload["projects"]]
    assert "Java Entwickler Banking" not in titles
    for project in payload["projects"]:
        assert project["matched_keywords"], (
            f"{project['title']} should have at least one matched keyword"
        )


def test_pipeline_writes_html_with_skeleton(isolated: dict[str, Path], mocker) -> None:
    response = mocker.Mock()
    response.status_code = 200
    response.text = FIXTURE.read_text(encoding="utf-8")
    mocker.patch("src.crawler.requests.get", return_value=response)

    main.main()

    html = isolated["docs_index_html"].read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "Freelancer" in html
    assert 'id="project-list"' in html
    assert "Fraunces" in html


def test_pipeline_embeds_bootstrap_data_matching_docs_data_json(
    isolated: dict[str, Path], mocker
) -> None:
    import re

    response = mocker.Mock()
    response.status_code = 200
    response.text = FIXTURE.read_text(encoding="utf-8")
    mocker.patch("src.crawler.requests.get", return_value=response)

    main.main()

    html = isolated["docs_index_html"].read_text(encoding="utf-8")
    match = re.search(
        r'<script id="bootstrap-data" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None, "bootstrap-data script tag missing"
    # Reverse the "</" escape we apply for script-breakout protection.
    embedded = json.loads(match.group(1).replace("<\\/", "</"))
    on_disk = json.loads(isolated["docs_data_json"].read_text(encoding="utf-8"))
    assert embedded["projects"] == on_disk["projects"]


def test_pipeline_returns_nonzero_when_feed_fetch_fails(isolated: dict[str, Path], mocker) -> None:
    import requests

    mocker.patch(
        "src.crawler.requests.get",
        side_effect=requests.ConnectionError("no network"),
    )

    exit_code = main.main()

    assert exit_code == 1
    # State files should not have been written
    assert not isolated["projects_json"].exists()
    assert not isolated["docs_data_json"].exists()
    assert not isolated["docs_index_html"].exists()
