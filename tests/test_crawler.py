"""Unit tests for :mod:`src.crawler`."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from src import config
from src.crawler import (
    FeedFetchError,
    compute_id,
    fetch_feed,
    parse_projects,
)

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "sample_feed.html").read_text(encoding="utf-8")


def test_compute_id_is_stable_for_same_url() -> None:
    url = "https://www.freelancermap.de/projekt/foo-12345"
    assert compute_id(url) == compute_id(url)


def test_compute_id_is_16_hex_chars() -> None:
    result = compute_id("https://example.com/x")
    assert len(result) == 16
    int(result, 16)  # raises if not hex


def test_compute_id_differs_for_different_urls() -> None:
    assert compute_id("https://x.de/a") != compute_id("https://x.de/b")


def test_parse_projects_extracts_all_three_items() -> None:
    projects = parse_projects(FIXTURE_HTML)
    assert len(projects) == 3
    titles = [p["title"] for p in projects]
    assert "Requirements Engineer Energiewirtschaft (m/w/d)" in titles
    assert "Java Entwickler Banking" in titles
    assert "Product Owner / TSO / Redispatch" in titles


def test_parse_projects_strips_html_from_description() -> None:
    projects = parse_projects(FIXTURE_HTML)
    re_project = next(p for p in projects if p["title"].startswith("Requirements Engineer"))
    description = re_project["description"]
    assert "<" not in description
    assert ">" not in description
    assert "Stadtwerke" in description
    assert "IREB" in description


def test_parse_projects_decodes_html_entities() -> None:
    projects = parse_projects(FIXTURE_HTML)
    java_project = next(p for p in projects if "Java" in p["title"])
    # `&amp;` in the fixture must arrive as `&` in the stripped output.
    assert "Java & Spring Boot" in java_project["description"]


def test_parse_projects_builds_projekt_slug_urls() -> None:
    projects = parse_projects(FIXTURE_HTML)
    for project in projects:
        assert project["url"].startswith(config.PROJECT_BASE_URL + "/projekt/")


def test_parse_projects_assigns_stable_id_from_url() -> None:
    projects = parse_projects(FIXTURE_HTML)
    for project in projects:
        assert project["id"] == compute_id(project["url"])


def test_parse_projects_carries_source_and_empty_keywords() -> None:
    projects = parse_projects(FIXTURE_HTML)
    for project in projects:
        assert project["source"] == "freelancermap.de"
        assert project["matched_keywords"] == []


def test_parse_projects_uses_created_as_published() -> None:
    projects = parse_projects(FIXTURE_HTML)
    re_project = next(p for p in projects if p["title"].startswith("Requirements Engineer"))
    assert re_project["published"] == "2026-05-26T10:15:00+02:00"


def test_parse_projects_dedupes_same_url_across_top_and_regular() -> None:
    # Give the top result the same slug as a regular result -> same URL ->
    # same id -> it must be deduplicated.
    html_with_dupe = FIXTURE_HTML.replace(
        '"slug":"product-owner-tso"',
        '"slug":"requirements-engineer-energie"',
    )
    projects = parse_projects(html_with_dupe)
    ids = [p["id"] for p in projects]
    assert len(ids) == len(set(ids))


def test_parse_projects_raises_when_no_json_island() -> None:
    with pytest.raises(FeedFetchError, match="No <script"):
        parse_projects("<html><body>plain page</body></html>")


def test_parse_projects_raises_when_no_results_in_island() -> None:
    html = (
        '<html><body><script type=\'application/json\'>{"something":"else"}</script></body></html>'
    )
    with pytest.raises(FeedFetchError, match="initialResults"):
        parse_projects(html)


def test_parse_projects_skips_items_missing_required_fields() -> None:
    html = (
        '<html><body><script type="application/json">'
        '{"initialResults":[{"id":1,"title":"","slug":"a"},'
        '{"id":2,"title":"Valid","slug":""},'
        '{"id":3,"title":"Keep","slug":"keep"}],'
        '"initialTopResults":[]}'
        "</script></body></html>"
    )
    projects = parse_projects(html)
    assert len(projects) == 1
    assert projects[0]["title"] == "Keep"


def test_fetch_feed_wraps_network_errors(mocker) -> None:
    mocker.patch(
        "src.crawler.requests.get",
        side_effect=requests.ConnectionError("dns boom"),
    )
    with pytest.raises(FeedFetchError, match="HTTP request"):
        fetch_feed("https://example.invalid/")


def test_fetch_feed_raises_on_non_200(mocker) -> None:
    response = mocker.Mock()
    response.status_code = 503
    response.text = "<html>error</html>"
    mocker.patch("src.crawler.requests.get", return_value=response)
    with pytest.raises(FeedFetchError, match="status 503"):
        fetch_feed("https://example.invalid/")


def test_fetch_feed_returns_projects_on_success(mocker) -> None:
    response = mocker.Mock()
    response.status_code = 200
    response.text = FIXTURE_HTML
    mocker.patch("src.crawler.requests.get", return_value=response)
    projects = fetch_feed("https://example.invalid/")
    assert len(projects) == 3
