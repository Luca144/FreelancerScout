"""Unit tests for :mod:`src.storage`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.crawler import RawProject
from src.storage import load_projects, merge_projects, save_projects


def make_project(
    *,
    id_: str = "abc123",
    title: str = "Demo",
    description: str = "demo body",
    url: str = "https://example.com/projekt/demo",
    published: str = "2026-05-27T08:00:00+00:00",
    first_seen: str | None = None,
) -> dict:
    project: dict = {
        "id": id_,
        "title": title,
        "url": url,
        "description": description,
        "published": published,
        "matched_keywords": [],
        "source": "freelancermap.de",
    }
    if first_seen is not None:
        project["first_seen"] = first_seen
    return project


def test_load_returns_empty_list_when_file_missing(tmp_path: Path) -> None:
    target = tmp_path / "does-not-exist.json"
    assert load_projects(target) == []


def test_save_load_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "projects.json"
    projects: list[RawProject] = [make_project(id_="aaa"), make_project(id_="bbb", title="Other")]
    save_projects(projects, target)
    loaded = load_projects(target)
    assert loaded == projects


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deeper" / "projects.json"
    save_projects([], target)
    assert target.exists()


def test_load_rejects_non_list(tmp_path: Path) -> None:
    target = tmp_path / "bad.json"
    target.write_text('{"not": "a list"}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON list"):
        load_projects(target)


def test_merge_stamps_first_seen_on_new_items() -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
    fresh = [make_project(id_="new1"), make_project(id_="new2", title="Two")]
    merged, stats = merge_projects([], fresh, now=now)
    assert stats.added == 2
    assert stats.known == 0
    assert stats.removed == 0
    for item in merged:
        assert item["first_seen"] == now.isoformat()


def test_merge_preserves_first_seen_on_known_items() -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
    earlier = (now - timedelta(days=3)).isoformat()
    existing = [make_project(id_="known", first_seen=earlier)]
    refreshed = [make_project(id_="known", title="Refreshed Title")]
    merged, stats = merge_projects(existing, refreshed, now=now)
    assert stats.added == 0
    assert stats.known == 1
    assert merged[0]["first_seen"] == earlier
    assert merged[0]["title"] == "Refreshed Title"


def test_merge_keeps_existing_items_not_in_feed_until_they_age_out() -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
    young = (now - timedelta(days=3)).isoformat()
    existing = [make_project(id_="orphan", first_seen=young)]
    merged, stats = merge_projects(existing, [], now=now)
    assert stats.added == 0
    assert stats.known == 0
    assert stats.removed == 0
    assert len(merged) == 1
    assert merged[0]["id"] == "orphan"


def test_merge_drops_items_older_than_14_days() -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
    stale = (now - timedelta(days=15)).isoformat()
    existing = [make_project(id_="stale", first_seen=stale)]
    merged, stats = merge_projects(existing, [], now=now)
    assert stats.removed == 1
    assert merged == []


def test_merge_keeps_items_exactly_within_14_day_cutoff() -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
    boundary = (now - timedelta(days=13, hours=23)).isoformat()
    existing = [make_project(id_="boundary", first_seen=boundary)]
    merged, stats = merge_projects(existing, [], now=now)
    assert stats.removed == 0
    assert len(merged) == 1


def test_merge_restamps_legacy_items_missing_first_seen() -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
    legacy = make_project(id_="legacy")
    legacy.pop("first_seen", None)
    merged, stats = merge_projects([legacy], [], now=now)
    assert stats.added == 0
    assert stats.removed == 0
    assert merged[0]["first_seen"] == now.isoformat()


def test_merge_combines_existing_and_new_with_correct_stats() -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
    young = (now - timedelta(days=2)).isoformat()
    stale = (now - timedelta(days=20)).isoformat()
    existing = [
        make_project(id_="keep", first_seen=young),
        make_project(id_="ageout", first_seen=stale),
    ]
    fresh = [
        make_project(id_="keep"),
        make_project(id_="brand-new", title="Brand new"),
    ]
    merged, stats = merge_projects(existing, fresh, now=now)
    assert stats.added == 1
    assert stats.known == 1
    assert stats.removed == 1
    ids = {p["id"] for p in merged}
    assert ids == {"keep", "brand-new"}


def test_merge_sorts_results_by_first_seen_desc() -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
    older = (now - timedelta(days=5)).isoformat()
    newer = (now - timedelta(days=1)).isoformat()
    existing = [
        make_project(id_="old", first_seen=older),
        make_project(id_="recent", first_seen=newer),
    ]
    merged, _ = merge_projects(existing, [], now=now)
    assert [p["id"] for p in merged] == ["recent", "old"]
