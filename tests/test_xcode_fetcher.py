"""Tests for scripts/fetchers/xcode.py."""
import datetime
import json
import pathlib
from unittest.mock import patch

import jsonschema
import pytest
from bs4 import BeautifulSoup

from scripts.fetchers.xcode import (
    _extract_plugin_versions,
    _find_next_table,
    _find_section_heading,
    _parse_feature_matrix,
    _table_to_markdown,
    fetch,
)

_IDE_CONFIG = {
    "id": "xcode",
    "name": "GitHub Copilot for Xcode",
    "data_dir": "data/xcode",
    "fetcher": "xcode",
    "source_url": "https://docs.github.com/en/copilot/reference/copilot-feature-matrix?tool=xcode",
}

# Minimal HTML that mirrors the real docs page structure.
_FAKE_HTML = """\
<!DOCTYPE html>
<html>
<body>
<h2 id="xcode-latest-releases">Xcode latest releases</h2>
<table>
  <thead>
    <tr><th>Feature</th><th>0.48.0</th><th>0.47.0</th></tr>
  </thead>
  <tbody>
    <tr><td>Code completion</td><td>✓</td><td>✓</td></tr>
    <tr><td>Copilot code review</td><td>✓</td><td>✗</td></tr>
    <tr><td>Chat</td><td>✗</td><td>✗</td></tr>
  </tbody>
</table>
<h2 id="xcode-2025-releases">Xcode 2025 releases</h2>
<table>
  <thead>
    <tr><th>Feature</th><th>0.40.0</th></tr>
  </thead>
  <tbody>
    <tr><td>Code completion</td><td>✓</td></tr>
    <tr><td>Copilot code review</td><td>✗</td></tr>
  </tbody>
</table>
</body>
</html>"""

# Table is wrapped in a div, as GitHub docs sometimes renders it.
_FAKE_HTML_TABLE_IN_DIV = """\
<html>
<body>
<h2>Xcode latest releases</h2>
<div class="ghd-tool active">
  <table>
    <tr><th>Feature</th><th>0.48.0</th></tr>
    <tr><td>Code completion</td><td>✓</td></tr>
  </table>
</div>
</body>
</html>"""


class TestFindSectionHeading:
    def test_finds_exact_heading(self):
        soup = BeautifulSoup(_FAKE_HTML, "lxml")
        heading = _find_section_heading(soup, "Xcode latest releases")
        assert heading is not None
        assert heading.get_text(strip=True) == "Xcode latest releases"

    def test_case_insensitive(self):
        soup = BeautifulSoup(_FAKE_HTML, "lxml")
        assert _find_section_heading(soup, "xcode latest releases") is not None

    def test_returns_none_when_not_found(self):
        soup = BeautifulSoup(_FAKE_HTML, "lxml")
        assert _find_section_heading(soup, "Xcode 1999 releases") is None


class TestFindNextTable:
    def test_finds_direct_sibling_table(self):
        soup = BeautifulSoup(_FAKE_HTML, "lxml")
        heading = _find_section_heading(soup, "Xcode latest releases")
        table = _find_next_table(heading)
        assert table is not None
        assert table.name == "table"

    def test_does_not_return_table_from_next_section(self):
        soup = BeautifulSoup(_FAKE_HTML, "lxml")
        heading = _find_section_heading(soup, "Xcode latest releases")
        table = _find_next_table(heading)
        assert "0.40.0" not in table.get_text()

    def test_finds_table_nested_inside_div(self):
        soup = BeautifulSoup(_FAKE_HTML_TABLE_IN_DIV, "lxml")
        heading = _find_section_heading(soup, "Xcode latest releases")
        table = _find_next_table(heading)
        assert table is not None
        assert "Code completion" in table.get_text()


class TestTableToMarkdown:
    def test_header_row_followed_by_separator(self):
        soup = BeautifulSoup(_FAKE_HTML, "lxml")
        table = soup.find("table")
        lines = _table_to_markdown(table).splitlines()
        assert lines[0].startswith("| Feature |")
        assert all(cell.strip() == "---" for cell in lines[1].strip("| ").split("|"))

    def test_includes_all_data_rows(self):
        soup = BeautifulSoup(_FAKE_HTML, "lxml")
        table = soup.find("table")
        md = _table_to_markdown(table)
        assert "Code completion" in md
        assert "✓" in md
        assert "Chat" in md

    def test_empty_table_returns_empty_string(self):
        soup = BeautifulSoup("<table></table>", "lxml")
        assert _table_to_markdown(soup.find("table")) == ""

    def test_pipe_character_is_escaped(self):
        soup = BeautifulSoup("<table><tr><th>A|B</th></tr></table>", "lxml")
        assert "A\\|B" in _table_to_markdown(soup.find("table"))


class TestExtractPluginVersions:
    def _first_table(self, html=_FAKE_HTML):
        return BeautifulSoup(html, "lxml").find("table")

    def test_returns_one_record_per_column(self):
        records = _extract_plugin_versions(
            self._first_table(), _IDE_CONFIG, "Xcode latest releases", "xcode-latest", "2026-01-01"
        )
        assert len(records) == 2  # 0.48.0 and 0.47.0

    def test_version_is_plugin_version(self):
        records = _extract_plugin_versions(
            self._first_table(), _IDE_CONFIG, "Xcode latest releases", "xcode-latest", "2026-01-01"
        )
        versions = [r["version"] for r in records]
        assert "0.48.0" in versions
        assert "0.47.0" in versions

    def test_xcode_era_is_set(self):
        records = _extract_plugin_versions(
            self._first_table(), _IDE_CONFIG, "Xcode latest releases", "xcode-latest", "2026-01-01"
        )
        assert all(r["xcode_era"] == "xcode-latest" for r in records)

    def test_body_markdown_contains_only_this_versions_features(self):
        records = _extract_plugin_versions(
            self._first_table(), _IDE_CONFIG, "Xcode latest releases", "xcode-latest", "2026-01-01"
        )
        record = next(r for r in records if r["version"] == "0.48.0")
        assert "0.47.0" not in record["body_markdown"]
        assert "Code completion" in record["body_markdown"]

    def test_cross_features_excluded(self):
        records = _extract_plugin_versions(
            self._first_table(), _IDE_CONFIG, "Xcode latest releases", "xcode-latest", "2026-01-01"
        )
        record = next(r for r in records if r["version"] == "0.48.0")
        assert "Chat" not in record["body_markdown"]

    def test_body_markdown_is_list_format(self):
        records = _extract_plugin_versions(
            self._first_table(), _IDE_CONFIG, "Xcode latest releases", "xcode-latest", "2026-01-01"
        )
        record = next(r for r in records if r["version"] == "0.48.0")
        assert record["body_markdown"].startswith("- ")

    def test_empty_table_returns_empty_list(self):
        soup = BeautifulSoup("<table></table>", "lxml")
        records = _extract_plugin_versions(
            soup.find("table"), _IDE_CONFIG, "Xcode latest releases", "xcode-latest", "2026-01-01"
        )
        assert records == []


class TestParseFeatureMatrix:
    def test_returns_one_record_per_plugin_version(self):
        results = _parse_feature_matrix(_IDE_CONFIG, _FAKE_HTML)
        versions = [r["version"] for r in results]
        assert "0.48.0" in versions
        assert "0.47.0" in versions
        assert "0.40.0" in versions

    def test_xcode_era_is_set_per_section(self):
        results = _parse_feature_matrix(_IDE_CONFIG, _FAKE_HTML)
        by_version = {r["version"]: r for r in results}
        assert by_version["0.48.0"]["xcode_era"] == "xcode-latest"
        assert by_version["0.40.0"]["xcode_era"] == "xcode-2025"

    def test_record_has_required_fields(self):
        results = _parse_feature_matrix(_IDE_CONFIG, _FAKE_HTML)
        record = next(r for r in results if r["version"] == "0.48.0")
        assert record["ide"] == "xcode"
        assert record["release_date"] == "2026-01-01"
        assert record["source"] == "html"
        assert record["prerelease"] is False
        assert "Code completion" in record["body_markdown"]

    def test_body_markdown_contains_only_this_versions_column(self):
        results = _parse_feature_matrix(_IDE_CONFIG, _FAKE_HTML)
        record = next(r for r in results if r["version"] == "0.48.0")
        assert "Code completion" in record["body_markdown"]
        assert "0.47.0" not in record["body_markdown"]

    def test_cross_features_excluded_from_body(self):
        results = _parse_feature_matrix(_IDE_CONFIG, _FAKE_HTML)
        record = next(r for r in results if r["version"] == "0.48.0")
        assert "Chat" not in record["body_markdown"]

    def test_title_contains_plugin_version_and_section(self):
        results = _parse_feature_matrix(_IDE_CONFIG, _FAKE_HTML)
        record = next(r for r in results if r["version"] == "0.48.0")
        assert "0.48.0" in record["title"]
        assert "Xcode latest releases" in record["title"]

    def test_copilot_mentions_extracted(self):
        results = _parse_feature_matrix(_IDE_CONFIG, _FAKE_HTML)
        record = next(r for r in results if r["version"] == "0.48.0")
        assert any("Copilot code review" in m for m in record["copilot_mentions"])

    def test_cross_features_not_in_copilot_mentions(self):
        results = _parse_feature_matrix(_IDE_CONFIG, _FAKE_HTML)
        # 0.47.0 has ✗ for Copilot code review, so it must not appear in copilot_mentions
        record = next(r for r in results if r["version"] == "0.47.0")
        assert not any("Copilot code review" in m for m in record["copilot_mentions"])

    def test_returns_empty_list_when_no_sections_match(self):
        results = _parse_feature_matrix(_IDE_CONFIG, "<html><body><p>No tables.</p></body></html>")
        assert results == []


class TestSchemaValidation:
    def test_xcode_record_passes_schema_validation(self):
        schema = json.loads(pathlib.Path("scripts/common/schema.json").read_text())
        results = _parse_feature_matrix(_IDE_CONFIG, _FAKE_HTML)
        for r in results:
            r["fetched_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            r["schema_version"] = 1
        for r in results:
            jsonschema.validate(r, schema)  # raises if invalid


class TestFetch:
    def test_uses_source_url_from_config(self):
        config = {**_IDE_CONFIG, "source_url": "https://custom.example/matrix"}
        with patch("scripts.fetchers.xcode.get_text", return_value=_FAKE_HTML) as mock_get:
            fetch(config)
        mock_get.assert_called_once_with("https://custom.example/matrix", use_auth=False)

    def test_missing_source_url_raises(self):
        config = dict(_IDE_CONFIG)
        config.pop("source_url")
        with patch("scripts.fetchers.xcode.get_text"):
            with pytest.raises(ValueError, match="missing required config value 'source_url'"):
                fetch(config)

    def test_returns_list_of_dicts(self):
        with patch("scripts.fetchers.xcode.get_text", return_value=_FAKE_HTML):
            results = fetch(_IDE_CONFIG)
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, dict) for r in results)

    def test_result_urls_match_resolved_source_url(self):
        config = {**_IDE_CONFIG, "source_url": "https://custom.example/matrix"}
        with patch("scripts.fetchers.xcode.get_text", return_value=_FAKE_HTML):
            results = fetch(config)
        assert all(r["url"] == "https://custom.example/matrix" for r in results)

