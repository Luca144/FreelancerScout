"""Project-wide constants and filesystem paths."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
DOCS_DIR: Path = PROJECT_ROOT / "docs"
CONFIG_DIR: Path = PROJECT_ROOT / "config"
TEMPLATES_DIR: Path = PROJECT_ROOT / "templates"

PROJECTS_JSON: Path = DATA_DIR / "projects.json"
DOCS_DATA_JSON: Path = DOCS_DIR / "data.json"
DOCS_INDEX_HTML: Path = DOCS_DIR / "index.html"
KEYWORDS_JSON: Path = CONFIG_DIR / "keywords.json"
TEMPLATE_INDEX: Path = TEMPLATES_DIR / "index.html.j2"

SITE_TITLE: str = "Freelancer Scout"


def _resolve_repo_url() -> str:
    """Use explicit override, then GitHub Actions context, then a safe fallback."""
    override = os.environ.get("REPO_URL")
    if override:
        return override
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return f"https://github.com/{repo}"
    return "https://github.com/"


REPO_URL: str = _resolve_repo_url()

FEED_URL: str = "https://www.freelancermap.de/projekte"
PROJECT_BASE_URL: str = "https://www.freelancermap.de"
SOURCE: str = "freelancermap.de"

MAX_AGE_DAYS: int = 14

HTTP_TIMEOUT_SECONDS: int = 30
HTTP_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
