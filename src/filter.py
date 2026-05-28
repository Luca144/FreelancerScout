"""Keyword-based relevance filter.

A project qualifies when at least one positive keyword appears in its
``title + " " + description`` AND no negative keyword appears. Matching is
case-insensitive substring matching (multi-word entries match as phrases).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import NamedTuple

from src.crawler import RawProject

logger = logging.getLogger(__name__)


class Keywords(NamedTuple):
    """Loaded keyword lists in their original casing."""

    positive: list[str]
    negative: list[str]


def load_keywords(path: Path) -> Keywords:
    """Load positive and negative keyword lists from a JSON config file.

    Missing top-level keys default to empty lists so a partially filled
    config still produces a usable :class:`Keywords` value.
    """
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return Keywords(
        positive=list(data.get("positive", [])),
        negative=list(data.get("negative", [])),
    )


def _haystack(project: RawProject) -> str:
    """Return the lowercased text used for keyword matching."""
    title = project.get("title") or ""
    description = project.get("description") or ""
    return f"{title} {description}".lower()


def matched_positives(project: RawProject, positive: list[str]) -> list[str]:
    """Return every positive keyword whose lowercased form appears in the project.

    Casing of the returned strings matches the input list — keywords are
    surfaced to the UI exactly as configured.
    """
    haystack = _haystack(project)
    return [kw for kw in positive if kw.lower() in haystack]


def is_relevant(project: RawProject, positive: list[str], negative: list[str]) -> bool:
    """Return True iff the project has any positive match and no negative match."""
    haystack = _haystack(project)
    if not any(kw.lower() in haystack for kw in positive):
        return False
    return not any(kw.lower() in haystack for kw in negative)


def filter_relevant(projects: list[RawProject], keywords: Keywords) -> list[RawProject]:
    """Return the subset of ``projects`` that pass the filter, each enriched
    with its ``matched_keywords`` list.

    The input items are not mutated; shallow copies are returned.
    """
    relevant: list[RawProject] = []
    for project in projects:
        if not is_relevant(project, keywords.positive, keywords.negative):
            continue
        enriched: RawProject = dict(project)  # type: ignore[assignment]
        enriched["matched_keywords"] = matched_positives(project, keywords.positive)
        relevant.append(enriched)
    logger.debug("filter_relevant: %d/%d items pass", len(relevant), len(projects))
    return relevant
