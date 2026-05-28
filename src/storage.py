"""Persist project state to and from ``data/projects.json``.

The on-disk format is a flat JSON array of project dicts. ``merge_projects``
is the only place that stamps ``first_seen`` or expires old items.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

from src import config
from src.crawler import RawProject

logger = logging.getLogger(__name__)


class MergeStats(NamedTuple):
    """Counts emitted by :func:`merge_projects` for observability."""

    added: int
    known: int
    removed: int


def load_projects(path: Path = config.PROJECTS_JSON) -> list[RawProject]:
    """Load the project state. Returns an empty list if the file is missing."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{path} does not contain a JSON list")
    return data


def save_projects(projects: list[RawProject], path: Path = config.PROJECTS_JSON) -> None:
    """Atomically write ``projects`` as pretty-printed JSON to ``path``."""
    _atomic_write_json(projects, path)


def save_docs_data(
    projects: list[RawProject],
    updated_at: datetime,
    path: Path = config.DOCS_DATA_JSON,
) -> None:
    """Write the public docs payload (``{updated_at, projects}``).

    Wrapping the project list lets the frontend display "last updated …"
    without depending on HTTP ``Last-Modified`` headers (which are absent
    when the page is opened via ``file://`` for local testing).
    """
    payload: dict[str, Any] = {
        "updated_at": updated_at.isoformat(),
        "projects": projects,
    }
    _atomic_write_json(payload, path)


def _atomic_write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    tmp.replace(path)


def merge_projects(
    existing: list[RawProject],
    new: list[RawProject],
    now: datetime | None = None,
) -> tuple[list[RawProject], MergeStats]:
    """Merge ``new`` items into ``existing`` and apply the 14-day cutoff.

    Rules:
        * Items already known keep their original ``first_seen`` value;
          mutable fields (title, description, published) get refreshed
          from ``new``.
        * Items not yet known get ``first_seen`` stamped with ``now``.
        * Existing items not in ``new`` are kept until they age out.
        * Items whose ``first_seen`` is older than 14 days are dropped.

    Returns:
        A tuple of (merged list, MergeStats) where MergeStats counts
        added / known / removed items relative to the previous state.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=config.MAX_AGE_DAYS)
    now_iso = now.isoformat()

    existing_by_id: dict[str, RawProject] = {p["id"]: dict(p) for p in existing}
    new_by_id: dict[str, RawProject] = {p["id"]: p for p in new}

    added = 0
    known = 0
    for item_id, fresh in new_by_id.items():
        if item_id in existing_by_id:
            stored = existing_by_id[item_id]
            stored["title"] = fresh["title"]
            stored["description"] = fresh["description"]
            stored["published"] = fresh["published"]
            stored["url"] = fresh["url"]
            stored["source"] = fresh["source"]
            known += 1
        else:
            stamped: RawProject = dict(fresh)  # type: ignore[assignment]
            stamped["first_seen"] = now_iso  # type: ignore[typeddict-unknown-key]
            existing_by_id[item_id] = stamped
            added += 1

    merged: list[RawProject] = []
    removed = 0
    for item in existing_by_id.values():
        first_seen_str = item.get("first_seen")  # type: ignore[typeddict-item]
        if not first_seen_str:
            # Defensive: stamp legacy items missing the field so future
            # crawls have a comparison anchor.
            item["first_seen"] = now_iso  # type: ignore[typeddict-unknown-key]
            merged.append(item)
            continue
        try:
            first_seen_dt = datetime.fromisoformat(first_seen_str)
        except ValueError:
            logger.warning(
                "Invalid first_seen %r on id=%s — re-stamping",
                first_seen_str,
                item["id"],
            )
            item["first_seen"] = now_iso  # type: ignore[typeddict-unknown-key]
            merged.append(item)
            continue
        if first_seen_dt < cutoff:
            removed += 1
            continue
        merged.append(item)

    merged.sort(key=lambda p: p.get("first_seen", ""), reverse=True)  # type: ignore[typeddict-item]
    return merged, MergeStats(added=added, known=known, removed=removed)
