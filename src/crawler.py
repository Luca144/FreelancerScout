"""Fetch and parse freelancermap.de project listings.

The project board at ``https://www.freelancermap.de/projekte`` is a React app
that embeds its initial state in a ``<script type="application/json">`` tag.
We download the HTML, locate the JSON island, and extract the project list.
"""

from __future__ import annotations

import hashlib
import html as html_module
import json
import logging
import re
from typing import TypedDict

import requests

from src import config

logger = logging.getLogger(__name__)

# Match every <script type="application/json"> ... </script> block.
_JSON_ISLAND_RE = re.compile(
    r'<script[^>]+type=["\']application/json["\'][^>]*>([\s\S]*?)</script>',
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


class RawProject(TypedDict):
    """Normalized project shape used between crawler and storage layers.

    ``matched_keywords`` is always present but stays empty until Phase 2
    applies the keyword filter.
    """

    id: str
    title: str
    url: str
    description: str
    published: str
    matched_keywords: list[str]
    source: str


class FeedFetchError(RuntimeError):
    """Raised when the project listing cannot be fetched or parsed."""


def compute_id(url: str) -> str:
    """Return a stable 16-character SHA-256 prefix of ``url``."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _strip_html(value: str) -> str:
    """Strip HTML tags, decode entities, and collapse whitespace."""
    no_tags = _HTML_TAG_RE.sub(" ", value)
    decoded = html_module.unescape(no_tags)
    return _WHITESPACE_RE.sub(" ", decoded).strip()


def _build_url(plink: str) -> str:
    if plink.startswith("http://") or plink.startswith("https://"):
        return plink
    if not plink.startswith("/"):
        plink = "/" + plink
    return config.PROJECT_BASE_URL + plink


def _normalize(item: dict) -> RawProject | None:
    """Convert a raw freelancermap project dict into a ``RawProject``.

    Returns ``None`` when required fields (title, plink) are missing — we
    skip such items rather than fail the whole crawl.
    """
    plink = item.get("plink") or ""
    title = item.get("title") or ""
    if not plink or not title:
        return None

    url = _build_url(plink)
    description_raw = item.get("description") or ""
    published = item.get("created") or item.get("updated") or ""

    return RawProject(
        id=compute_id(url),
        title=title.strip(),
        url=url,
        description=_strip_html(description_raw),
        published=published,
        matched_keywords=[],
        source=config.SOURCE,
    )


def _extract_state(html: str) -> dict:
    """Find the largest JSON island in ``html`` and return it parsed.

    The freelancermap page emits multiple ``application/json`` scripts; the
    one carrying the project state is by far the largest. We pick the first
    parseable island that contains either ``initialResults`` or
    ``initialTopResults`` at the top level.
    """
    islands = _JSON_ISLAND_RE.findall(html)
    if not islands:
        raise FeedFetchError("No <script type='application/json'> tag found in HTML")

    candidate: dict | None = None
    for raw in sorted(islands, key=len, reverse=True):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        if "initialResults" in data or "initialTopResults" in data:
            candidate = data
            break

    if candidate is None:
        raise FeedFetchError(
            "No JSON island contained initialResults/initialTopResults — page layout may have changed"
        )
    return candidate


def parse_projects(html: str) -> list[RawProject]:
    """Parse a freelancermap.de listing page into normalized projects.

    Combines ``initialResults`` and ``initialTopResults``, deduplicates by
    URL hash, and drops items missing required fields.

    Raises:
        FeedFetchError: if the JSON island cannot be located or parsed.
    """
    state = _extract_state(html)
    regular = state.get("initialResults") or []
    top = state.get("initialTopResults") or []

    seen_ids: set[str] = set()
    projects: list[RawProject] = []
    for raw in [*regular, *top]:
        if not isinstance(raw, dict):
            continue
        project = _normalize(raw)
        if project is None:
            continue
        if project["id"] in seen_ids:
            continue
        seen_ids.add(project["id"])
        projects.append(project)

    logger.debug(
        "parse_projects: %d regular + %d top -> %d unique",
        len(regular),
        len(top),
        len(projects),
    )
    return projects


def fetch_feed(url: str = config.FEED_URL) -> list[RawProject]:
    """Fetch the freelancermap project page and return parsed projects.

    Raises:
        FeedFetchError: on HTTP failure, non-200 status, or missing JSON island.
    """
    headers = {
        "User-Agent": config.HTTP_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }
    try:
        response = requests.get(url, headers=headers, timeout=config.HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise FeedFetchError(f"HTTP request to {url} failed: {exc}") from exc

    if response.status_code != 200:
        raise FeedFetchError(f"Unexpected status {response.status_code} for {url}")

    return parse_projects(response.text)
