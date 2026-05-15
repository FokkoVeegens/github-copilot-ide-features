"""Helpers for parsing GitHub Copilot feature-matrix tables."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

_HEADING_RE = re.compile(r"^h[1-6]$")


def find_section_heading(soup: BeautifulSoup, *texts: str) -> Tag | None:
    """Find a heading element whose text content matches one of *texts*."""
    wanted = {text.lower() for text in texts}
    for tag in soup.find_all(_HEADING_RE):
        if tag.get_text(strip=True).lower() in wanted:
            return tag
    return None


def find_next_table(heading: Tag) -> Tag | None:
    """Return the first table after *heading* before the next same-or-higher heading."""
    heading_level = int(heading.name[1])
    for element in heading.next_siblings:
        if not isinstance(element, Tag):
            continue
        if _HEADING_RE.match(element.name or "") and int(element.name[1]) <= heading_level:
            break
        if element.name == "table":
            return element
        nested = element.find("table")
        if nested:
            return nested
    return None


def parse_feature_table(table: Tag) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Return the column headers and feature/value rows from a feature-matrix table."""
    rows = table.find_all("tr")
    if not rows:
        return [], []

    header_cells = rows[0].find_all(["th", "td"])
    if len(header_cells) < 2:
        return [], []

    column_headers = [cell.get_text(strip=True) for cell in header_cells[1:]]
    data_rows: list[tuple[str, list[str]]] = []
    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        feature = cells[0].get_text(strip=True)
        values = [cell.get_text(strip=True) for cell in cells[1:]]
        data_rows.append((feature, values))

    return column_headers, data_rows


def table_to_markdown(table: Tag) -> str:
    """Convert a feature-matrix table to markdown."""
    rows = table.find_all("tr")
    if not rows:
        return ""

    markdown_rows: list[str] = []
    for index, row in enumerate(rows):
        cells = [
            cell.get_text(strip=True).replace("|", "\\|")
            for cell in row.find_all(["th", "td"])
        ]
        if not cells:
            continue
        markdown_rows.append("| " + " | ".join(cells) + " |")
        if index == 0:
            markdown_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")

    return "\n".join(markdown_rows)
