"""Vim/Neovim fetcher — feature matrix from GitHub Copilot docs."""

from bs4 import BeautifulSoup, Tag

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
    ("NeoVim latest releases", "neovim-latest", "2026-01-01"),
    ("NeoVim 2024 releases", "neovim-2024", "2024-01-01"),
    ("NeoVim 2023 releases", "neovim-2023", "2023-01-01"),
    ("NeoVim 2022 releases", "neovim-2022", "2022-01-01"),
    ("NeoVim 2021 releases", "neovim-2021", "2021-01-01"),
]

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
                "neovim_era": era_key,
                "release_date": release_date,
                "title": f"GitHub Copilot for Vim/Neovim {plugin_version} \u2013 {heading_text}",
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
