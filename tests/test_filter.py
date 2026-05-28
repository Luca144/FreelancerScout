"""Unit tests for :mod:`src.filter`."""

from __future__ import annotations

import json
from pathlib import Path

from src.filter import (
    Keywords,
    filter_relevant,
    is_relevant,
    load_keywords,
    matched_positives,
)


def make_project(*, title: str = "", description: str = "") -> dict:
    return {
        "id": "x" * 16,
        "title": title,
        "url": "https://example.com/p",
        "description": description,
        "published": "2026-05-27T08:00:00+00:00",
        "matched_keywords": [],
        "source": "freelancermap.de",
    }


# ---------- is_relevant truth table ----------


def test_positive_match_alone_is_relevant() -> None:
    project = make_project(title="Requirements Engineer gesucht")
    assert is_relevant(project, ["requirements engineer"], []) is True


def test_positive_plus_negative_is_not_relevant() -> None:
    project = make_project(
        title="Requirements Engineer", description="auch Java Entwickler welcome"
    )
    assert is_relevant(project, ["requirements engineer"], ["java entwickler"]) is False


def test_only_negative_match_is_not_relevant() -> None:
    project = make_project(title="Java Entwickler")
    assert is_relevant(project, ["requirements engineer"], ["java entwickler"]) is False


def test_no_match_at_all_is_not_relevant() -> None:
    project = make_project(title="Buchhalter im Innendienst")
    assert is_relevant(project, ["requirements engineer"], ["java entwickler"]) is False


def test_match_is_case_insensitive() -> None:
    project = make_project(title="REQUIREMENTS ENGINEER (m/w/d)")
    assert is_relevant(project, ["requirements engineer"], []) is True


def test_multi_word_phrase_matches_as_phrase() -> None:
    project_phrase = make_project(title="Senior Scrum Master")
    project_no_phrase = make_project(title="Scrum-Trainer und Master-Of-None")
    assert is_relevant(project_phrase, ["scrum master"], []) is True
    # "scrum master" with a space should NOT match "Scrum-Trainer ... Master..."
    assert is_relevant(project_no_phrase, ["scrum master"], []) is False


def test_match_searches_in_title_only() -> None:
    project = make_project(title="Requirements Engineer", description="")
    assert is_relevant(project, ["requirements engineer"], []) is True


def test_match_searches_in_description_only() -> None:
    project = make_project(title="Freelance Position", description="Suche Requirements Engineer")
    assert is_relevant(project, ["requirements engineer"], []) is True


# ---------- matched_positives ----------


def test_matched_positives_returns_every_matching_keyword() -> None:
    project = make_project(
        title="Requirements Engineer fuer Stadtwerke",
        description="IREB CPRE Zertifizierung von Vorteil, agil arbeitend",
    )
    result = matched_positives(
        project,
        ["requirements engineer", "stadtwerke", "ireb", "cpre", "agil", "scada"],
    )
    assert set(result) == {
        "requirements engineer",
        "stadtwerke",
        "ireb",
        "cpre",
        "agil",
    }


def test_matched_positives_returns_empty_when_nothing_matches() -> None:
    project = make_project(title="Buchhalter")
    assert matched_positives(project, ["requirements engineer", "ireb"]) == []


def test_matched_positives_preserves_keyword_casing() -> None:
    project = make_project(title="requirements engineer (m/w/d)")
    result = matched_positives(project, ["Requirements Engineer"])
    assert result == ["Requirements Engineer"]


# ---------- edge cases ----------


def test_empty_positive_list_means_no_match() -> None:
    project = make_project(title="anything goes here")
    assert is_relevant(project, [], ["java"]) is False


def test_empty_negative_list_does_not_block_positives() -> None:
    project = make_project(title="Requirements Engineer")
    assert is_relevant(project, ["requirements engineer"], []) is True


def test_missing_title_uses_description_only() -> None:
    project = make_project(title="", description="Requirements Engineer wanted")
    assert is_relevant(project, ["requirements engineer"], []) is True


def test_missing_description_uses_title_only() -> None:
    project = make_project(title="Requirements Engineer", description="")
    assert is_relevant(project, ["requirements engineer"], []) is True


def test_both_fields_empty_means_no_match() -> None:
    project = make_project()
    assert is_relevant(project, ["requirements engineer"], []) is False


def test_haystack_handles_none_fields() -> None:
    project: dict = {
        "id": "y",
        "title": None,
        "description": None,
        "url": "",
        "published": "",
        "matched_keywords": [],
        "source": "",
    }
    assert is_relevant(project, ["anything"], []) is False


# ---------- load_keywords ----------


def test_load_keywords_reads_both_lists(tmp_path: Path) -> None:
    target = tmp_path / "kw.json"
    target.write_text(
        json.dumps({"positive": ["pmo", "scrum"], "negative": ["frontend"]}),
        encoding="utf-8",
    )
    keywords = load_keywords(target)
    assert keywords.positive == ["pmo", "scrum"]
    assert keywords.negative == ["frontend"]


def test_load_keywords_defaults_missing_lists_to_empty(tmp_path: Path) -> None:
    target = tmp_path / "kw.json"
    target.write_text(json.dumps({"positive": ["pmo"]}), encoding="utf-8")
    keywords = load_keywords(target)
    assert keywords.positive == ["pmo"]
    assert keywords.negative == []


# ---------- filter_relevant ----------


def test_filter_relevant_enriches_each_kept_item_with_matched_keywords() -> None:
    kept = make_project(title="Requirements Engineer", description="IREB von Vorteil")
    blocked = make_project(title="Java Entwickler")
    keywords = Keywords(positive=["requirements engineer", "ireb"], negative=["java"])
    out = filter_relevant([kept, blocked], keywords)
    assert len(out) == 1
    assert set(out[0]["matched_keywords"]) == {"requirements engineer", "ireb"}


def test_filter_relevant_does_not_mutate_input() -> None:
    original = make_project(title="Requirements Engineer")
    keywords = Keywords(positive=["requirements engineer"], negative=[])
    filter_relevant([original], keywords)
    assert original["matched_keywords"] == []


def test_filter_relevant_returns_empty_for_empty_input() -> None:
    keywords = Keywords(positive=["pmo"], negative=[])
    assert filter_relevant([], keywords) == []
