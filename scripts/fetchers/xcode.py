"""Xcode fetcher — feature matrix from GitHub Copilot docs."""
import re

from bs4 import BeautifulSoup, Tag

from scripts.common.config import require_config_value
from scripts.common.extract import extract_copilot_mentions
from scripts.common.http import get_text

# (heading text on the page, version key for the JSON file, approximate release date)
_SECTIONS: list[tuple[str, str, str]] = [
    ("Xcode latest releases", "xcode-latest", "2026-01-01"),
    ("Xcode 2025 releases", "xcode-2025", "2025-01-01"),
    ("Xcode 2024 releases", "xcode-2024", "2024-01-01"),
]

_HEADING_RE = re.compile(r"^h[1-6]$")


def fetch(ide_config: dict) -> list[dict]:
    source_url = require_config_value(ide_config, "source_url")
    html = get_text(source_url, use_auth=False)
    return _parse_feature_matrix(ide_config, html, source_url=source_url)


def _parse_feature_matrix(
    ide_config: dict, html: str, *, source_url: str | None = None
) -> list[dict]:
    source_url = source_url or require_config_value(ide_config, "source_url")
    soup = BeautifulSoup(html, "lxml")
    results = []

    for heading_text, era_key, release_date in _SECTIONS:
        heading = _find_section_heading(soup, heading_text)
        if heading is None:
            print(f"  [warn] Section '{heading_text}' not found in feature matrix page.")
            continue

        table = _find_next_table(heading)
        if table is None:
            print(f"  [warn] No table found after '{heading_text}'.")
            continue

        records = _extract_plugin_versions(
            table,
            ide_config,
            heading_text,
            era_key,
            release_date,
            source_url=source_url,
        )
        results.extend(records)

    return results


_NOT_SUPPORTED = "✗"


def _extract_plugin_versions(
    table: Tag,
    ide_config: dict,
    heading_text: str,
    era_key: str,
    release_date: str,
    *,
    source_url: str | None = None,
) -> list[dict]:
    """Return one record per plugin-version column found in the table header.

    Only features whose cell value is not ✗ (i.e. supported or partially
    supported) are included in the record's body_markdown.
    """
    source_url = source_url or require_config_value(ide_config, "source_url")
    rows = table.find_all("tr")
    if not rows:
        return []

    header_cells = rows[0].find_all(["th", "td"])
    if len(header_cells) < 2:
        return []

    plugin_versions = [c.get_text(strip=True) for c in header_cells[1:]]

    data_rows: list[tuple[str, list[str]]] = []
    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        feature = cells[0].get_text(strip=True)
        values = [c.get_text(strip=True) for c in cells[1:]]
        data_rows.append((feature, values))

    results = []
    for col_idx, plugin_version in enumerate(plugin_versions):
        supported = [
            (feature, value)
            for feature, values in data_rows
            for value in [values[col_idx] if col_idx < len(values) else ""]
            if value != _NOT_SUPPORTED and value != ""
        ]
        body_markdown = "\n".join(
            f"- {feature} ({value})" if value != "✓" else f"- {feature}"
            for feature, value in supported
        )

        results.append(
            {
                "ide": ide_config["id"],
                "version": plugin_version,
                "xcode_era": era_key,
                "release_date": release_date,
                "title": f"GitHub Copilot for Xcode {plugin_version} \u2013 {heading_text}",
                "url": source_url,
                "source": "html",
                "body_markdown": body_markdown,
                "body_html": None,
                "categories": [],
                "copilot_mentions": extract_copilot_mentions(body_markdown),
                "prerelease": False,
            }
        )

    return results


def _find_section_heading(soup: BeautifulSoup, text: str) -> Tag | None:
    """Find a heading element whose text content matches *text* (case-insensitive)."""
    text_lower = text.lower()
    for tag in soup.find_all(_HEADING_RE):
        if tag.get_text(strip=True).lower() == text_lower:
            return tag
    return None


def _find_next_table(heading: Tag) -> Tag | None:
    """Return the first <table> after *heading*, stopping before the next same-or-higher heading."""
    heading_level = int(heading.name[1])
    for element in heading.next_siblings:
        if not isinstance(element, Tag):
            continue
        if _HEADING_RE.match(element.name or ""):
            if int(element.name[1]) <= heading_level:
                break
        if element.name == "table":
            return element
        nested = element.find("table")
        if nested:
            return nested
    return None


def _table_to_markdown(table: Tag) -> str:
    """Convert a <table> element to a Markdown table string."""
    rows = table.find_all("tr")
    if not rows:
        return ""

    md_rows: list[str] = []
    for i, row in enumerate(rows):
        cells = [
            c.get_text(strip=True).replace("|", "\\|") for c in row.find_all(["th", "td"])
        ]
        if not cells:
            continue
        md_rows.append("| " + " | ".join(cells) + " |")
        if i == 0:
            md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")

    return "\n".join(md_rows)
