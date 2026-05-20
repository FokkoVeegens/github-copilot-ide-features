"""Visual Studio release-notes fetcher for learn.microsoft.com HTML pages."""

from __future__ import annotations

from packaging.version import Version

from scripts.common.config import require_config_value
from scripts.common.extract import extract_copilot_mentions, html_to_markdown
from scripts.common.html_split import split_version_sections
from scripts.common.http import get_text

_RELEASE_SECTION_VERSION_RE = r"^(?:Version|.+\s+Update)\s+(?P<version>\d+\.\d+\.\d+)$"


def _is_at_or_above_start_version(version: str, start_version: str | None) -> bool:
    if not start_version or start_version == "all":
        return True
    return Version(version) >= Version(start_version)


def fetch(ide_config: dict) -> list[dict]:
    """Fetch Visual Studio 2026 release notes from the unified HTML page."""
    source_url = require_config_value(ide_config, "source_url")
    start_version = ide_config.get("start_version")

    html = get_text(source_url, use_auth=False)
    sections = split_version_sections(
        html,
        heading_tags=("h2",),
        version_pattern=_RELEASE_SECTION_VERSION_RE,
        date_pattern=r"Released(?:\s+on)?\s+(?P<date>[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4})",
    )

    results: list[dict] = []
    for section in sections:
        version = section["version"]
        if not _is_at_or_above_start_version(version, start_version):
            continue

        body_html = section["body_html"]
        body_markdown = html_to_markdown(body_html)
        results.append(
            {
                "ide": ide_config["id"],
                "version": version,
                "release_date": section["release_date"],
                "title": section["title"],
                "url": source_url,
                "source": "html",
                "body_markdown": body_markdown,
                "body_html": body_html,
                "categories": [],
                "copilot_mentions": extract_copilot_mentions(body_markdown),
            }
        )

    return results