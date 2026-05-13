"""Helpers for splitting large HTML release-notes pages into per-version sections."""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup, Tag


def normalize_human_date(date_text: str) -> str:
    """Convert a date like 'April 21st, 2026' to ISO-8601."""
    cleaned = re.sub(r"(\d{1,2})(st|nd|rd|th)", r"\1", date_text.strip(), flags=re.IGNORECASE)
    return datetime.strptime(cleaned, "%B %d, %Y").strftime("%Y-%m-%d")


def split_version_sections(
    html: str,
    *,
    heading_tags: tuple[str, ...],
    version_pattern: str,
    date_pattern: str,
) -> list[dict[str, str]]:
    """Split a release-notes page into version sections.

    Each matching heading starts a section. The section body includes all sibling
    nodes up to the next matching heading.
    """
    soup = BeautifulSoup(html, "lxml")
    version_re = re.compile(version_pattern, re.IGNORECASE)
    date_re = re.compile(date_pattern, re.IGNORECASE)

    sections: list[dict[str, str]] = []

    for heading in soup.find_all(heading_tags):
        if not isinstance(heading, Tag):
            continue

        heading_text = heading.get_text(" ", strip=True)
        version_match = version_re.search(heading_text)
        if not version_match:
            continue

        body_parts: list[str] = []
        date_match = None
        for sibling in heading.next_siblings:
            if isinstance(sibling, Tag) and sibling.name in heading_tags:
                sibling_text = sibling.get_text(" ", strip=True)
                if version_re.search(sibling_text):
                    break

            if isinstance(sibling, Tag):
                body_parts.append(str(sibling))
                if date_match is None:
                    date_match = date_re.search(sibling.get_text(" ", strip=True))

        if date_match is None:
            date_match = date_re.search(heading_text)
        if date_match is None:
            raise ValueError(f"Could not find release date for section {heading_text!r}")

        sections.append(
            {
                "version": version_match.group("version"),
                "title": heading_text,
                "release_date": normalize_human_date(date_match.group("date")),
                "body_html": "\n".join(body_parts).strip(),
            }
        )

    return sections