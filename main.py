"""Entry point for the Freelancer Scout crawl pipeline."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from src import config
from src.crawler import FeedFetchError, fetch_feed
from src.filter import filter_relevant, load_keywords
from src.renderer import render
from src.storage import (
    load_projects,
    merge_projects,
    save_docs_data,
    save_projects,
)


def configure_logging() -> None:
    """Configure root logger with a concise console format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def main() -> int:
    """Run one crawl pipeline iteration.

    Returns:
        Process exit code (0 on success, 1 on fetch failure).
    """
    configure_logging()
    logger = logging.getLogger("freelancer_scout")

    logger.info("Loading existing state from %s", config.PROJECTS_JSON)
    existing = load_projects(config.PROJECTS_JSON)

    logger.info("Fetching feed from %s", config.FEED_URL)
    try:
        fresh = fetch_feed(config.FEED_URL)
    except FeedFetchError as exc:
        logger.error("Feed fetch failed: %s — keeping previous state", exc)
        return 1

    logger.info("Fetched %d projects from feed", len(fresh))

    merged, stats = merge_projects(existing, fresh)
    save_projects(merged, config.PROJECTS_JSON)
    logger.info(
        "Merge complete: %d new, %d known, %d removed (total stored: %d)",
        stats.added,
        stats.known,
        stats.removed,
        len(merged),
    )

    logger.info("Filtering against keywords from %s", config.KEYWORDS_JSON)
    keywords = load_keywords(config.KEYWORDS_JSON)
    relevant = filter_relevant(merged, keywords)

    updated_at = datetime.now(UTC)
    save_docs_data(relevant, updated_at, config.DOCS_DATA_JSON)
    logger.info(
        "Filter complete: %d/%d projects relevant -> %s",
        len(relevant),
        len(merged),
        config.DOCS_DATA_JSON,
    )

    bootstrap_json = json.dumps(
        {"updated_at": updated_at.isoformat(), "projects": relevant},
        ensure_ascii=False,
    ).replace("</", "<\\/")  # protect against </script> breakout

    render(
        config.TEMPLATE_INDEX,
        config.DOCS_INDEX_HTML,
        context={
            "site_title": config.SITE_TITLE,
            "source_url": config.FEED_URL,
            "source_label": config.SOURCE,
            "repo_url": config.REPO_URL,
            "bootstrap_json": bootstrap_json,
        },
    )
    logger.info("Rendered %s", config.DOCS_INDEX_HTML)

    return 0


if __name__ == "__main__":
    sys.exit(main())
