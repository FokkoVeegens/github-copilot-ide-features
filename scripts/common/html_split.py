"""Helpers for splitting large HTML release-notes pages into per-version sections."""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup, Tag

_MONTH_ALIASES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "novemeber": 11,
    "dec": 12,
    "december": 12,
}


def normalize_human_date(date_text: str) -> str:
    """Convert a human-readable date like 'April 21st, 2026' to ISO-8601."""
    cleaned = re.sub(
        r"(\d{1,2})\s*(st|nd|rd|th)",
        r"\1",
        date_text.strip(),
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).replace(" ,", ",").strip()

    for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    normalized = cleaned.replace(",", "")
    parts = normalized.split()
    if len(parts) != 3:
        raise ValueError(f"Unsupported date format: {date_text!r}")

    month_text, day_text, year_text = parts
    month = _MONTH_ALIASES.get(month_text.lower())
    if month is None:
        raise ValueError(f"Unsupported date format: {date_text!r}")

    return datetime(int(year_text), month, int(day_text)).strftime("%Y-%m-%d")


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
