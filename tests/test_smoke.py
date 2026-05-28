"""Smoke tests that hit the live freelancermap project page.

Run with ``pytest -m smoke``; excluded from the default suite.
"""

from __future__ import annotations

import pytest

from src.crawler import fetch_feed

pytestmark = pytest.mark.smoke


def test_fetch_feed_returns_projects_from_live_page() -> None:
    projects = fetch_feed()
    assert len(projects) >= 1, "Live feed returned no projects"
    sample = projects[0]
    assert sample["title"], "First project has empty title"
    assert sample["url"].startswith("https://www.freelancermap.de/projekt/")
    assert sample["id"] and len(sample["id"]) == 16
    assert sample["source"] == "freelancermap.de"
