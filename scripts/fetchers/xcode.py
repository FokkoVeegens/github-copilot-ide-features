"""Xcode fetcher — feature matrix from GitHub Copilot docs.

The record set combines two complementary sources:

* the GitHub Copilot **feature matrix** docs page, which lists which features
  each plugin version supports, and
* the CopilotForXcode **CHANGELOG.md**, which describes what actually changed in
  each release (and carries the real release date).

The changelog notes are merged into the matching feature-matrix records and any
changelog-only versions are added as extra records, so no feature data is lost.
"""

import re
from datetime import datetime

from bs4 import BeautifulSoup, Tag

from scripts.common.changelog import split_changelog_by_version
from scripts.common.config import require_config_value
from scripts.common.extract import extract_copilot_mentions
from scripts.common.feature_matrix import (
    find_next_table as _find_next_table,
)
from scripts.common.feature_matrix import (
    find_section_heading as _find_section_heading,
)
from scripts.common.feature_matrix import (
    parse_feature_table,
)
from scripts.common.feature_matrix import (
    table_to_markdown as _shared_table_to_markdown,
)
from scripts.common.http import get_text

# (heading text on the page, version key for the JSON file, approximate release date)
_SECTIONS: list[tuple[str, str, str]] = [
    ("Xcode latest releases", "xcode-latest", "2026-01-01"),
    ("Xcode 2025 releases", "xcode-2025", "2025-01-01"),
    ("Xcode 2024 releases", "xcode-2024", "2024-01-01"),
]

# Fallback release date for changelog-only records whose heading has no parseable date.
_DEFAULT_ERA_DATE = next(date for _, key, date in _SECTIONS if key == "xcode-latest")

# Matches changelog headings like "## 0.50.0 - May 20, 2026" or "## [0.50.0] - May 20, 2026"
# (optional brackets around the version, hyphen or en-dash separator).
_CHANGELOG_DATE_RE = re.compile(
    r"^##\s+\[?v?(?P<version>\d+(?:\.\d+){1,3})\]?\s*[-\u2013]\s*"
    r"(?P<date>[A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
    re.MULTILINE,
)


def fetch(ide_config: dict) -> list[dict]:
    source_url = require_config_value(ide_config, "source_url")
    html = get_text(source_url, use_auth=False)

    changelog_markdown = None
    changelog_url = ide_config.get("changelog_url")
    if changelog_url:
        # Never send the GitHub token when fetching data destined for ./data.
        changelog_markdown = get_text(changelog_url, use_auth=False)

    return _parse_feature_matrix(
        ide_config,
        html,
        source_url=source_url,
        changelog_markdown=changelog_markdown,
        changelog_url=changelog_url,
    )


def _parse_feature_matrix(
    ide_config: dict,
    html: str,
    *,
    source_url: str | None = None,
    changelog_markdown: str | None = None,
    changelog_url: str | None = None,
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

    if changelog_markdown:
        effective_changelog_url = changelog_url or ide_config.get("changelog_url") or source_url
        results = _merge_changelog(
            results,
            ide_config,
            changelog_markdown,
            changelog_url=effective_changelog_url,
        )

    return results


def _extract_changelog_dates(changelog_markdown: str) -> dict[str, str]:
    """Return ``{version: YYYY-MM-DD}`` parsed from changelog headings."""
    dates: dict[str, str] = {}
    for match in _CHANGELOG_DATE_RE.finditer(changelog_markdown):
        version = match.group("version").lstrip("vV")
        if version in dates:
            continue
        try:
            parsed = datetime.strptime(match.group("date"), "%B %d, %Y")
        except ValueError:
            continue
        dates[version] = parsed.strftime("%Y-%m-%d")
    return dates


def _era_for_date(iso_date: str | None) -> tuple[str, str]:
    """Return the ``(era_key, heading_text)`` for a changelog-only version."""
    year: int | None = None
    if iso_date:
        try:
            year = int(iso_date[:4])
        except ValueError:
            year = None
    if year is None or year >= 2026:
        return "xcode-latest", "Xcode latest releases"
    if year == 2025:
        return "xcode-2025", "Xcode 2025 releases"
    return "xcode-2024", "Xcode 2024 releases"


def _compose_body(changelog_body: str, feature_body: str) -> str:
    """Combine changelog notes with the supported-feature list."""
    parts: list[str] = []
    if changelog_body.strip():
        parts.append(changelog_body.strip())
    if feature_body.strip():
        parts.append(f"### Supported features\n{feature_body.strip()}")
    return "\n\n".join(parts)


def _merge_changelog(
    records: list[dict],
    ide_config: dict,
    changelog_markdown: str,
    *,
    changelog_url: str,
) -> list[dict]:
    """Enrich matrix records with changelog notes and add changelog-only versions."""
    sections = split_changelog_by_version(changelog_markdown)
    dates = _extract_changelog_dates(changelog_markdown)
    matrix_versions = {record["version"] for record in records}

    for record in records:
        version = record["version"]
        changelog_body = sections.get(version, "").strip()
        if changelog_body:
            record["body_markdown"] = _compose_body(changelog_body, record["body_markdown"])
            record["copilot_mentions"] = extract_copilot_mentions(record["body_markdown"])
        if version in dates:
            record["release_date"] = dates[version]

    for version, changelog_body in sections.items():
        if version in matrix_versions:
            continue
        release_date = dates.get(version)
        era_key, heading_text = _era_for_date(release_date)
        body_markdown = changelog_body.strip()
        records.append(
            {
                "ide": ide_config["id"],
                "version": version,
                "xcode_era": era_key,
                "release_date": release_date or _DEFAULT_ERA_DATE,
                "title": f"GitHub Copilot for Xcode {version} \u2013 {heading_text}",
                "url": changelog_url,
                "source": "html",
                "body_markdown": body_markdown,
                "body_html": None,
                "categories": [],
                "copilot_mentions": extract_copilot_mentions(body_markdown),
                "prerelease": False,
            }
        )

    return records


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
    plugin_versions, data_rows = parse_feature_table(table)
    if not plugin_versions:
        return []

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


def _table_to_markdown(table: Tag) -> str:
    return _shared_table_to_markdown(table)
