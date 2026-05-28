"""Render the static HTML skeleton from a Jinja template.

The template is rendered once per crawl as a thin shell. All dynamic
content (project cards, filter chips, the "last updated" string) is
hydrated by ``docs/app.js`` from ``docs/data.json`` at page-load time —
this way hourly data updates do not require a fresh template render.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)


def render(template_path: Path, output_path: Path, context: dict[str, Any]) -> None:
    """Render the Jinja template at ``template_path`` into ``output_path``.

    Args:
        template_path: Absolute path to the ``.j2`` template file.
        output_path: Absolute path where the rendered HTML is written.
        context: Variables exposed to the template.
    """
    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        autoescape=select_autoescape(["html", "j2"]),
        keep_trailing_newline=True,
    )
    template = env.get_template(template_path.name)
    rendered = template.render(**context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    logger.debug("Rendered %s -> %s", template_path.name, output_path)
