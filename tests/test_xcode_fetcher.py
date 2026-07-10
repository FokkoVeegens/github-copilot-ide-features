"""Tests for scripts/fetchers/xcode.py."""
import datetime
import json
import pathlib
from unittest.mock import patch

import jsonschema
import pytest
from bs4 import BeautifulSoup

from scripts.fetchers.xcode import (
    _era_for_date,
    _extract_changelog_dates,
    _extract_plugin_versions,
    _find_next_table,
    _find_section_heading,
    _merge_changelog,
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

_FAKE_CHANGELOG = """\
# Changelog

## 0.48.0 - April 23, 2026
### Added
- Context window usage details in chat.

### Changed
- Custom agents are now generally available.

## 0.40.0 - July 24, 2025
### Added
- Support disabling Agent mode when disabled by policy.

## 0.31.0 - February 11, 2025 (Public Preview)
### Added
- Added Copilot Chat support.
"""

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
            r["fetched_at"] = datetime.datetime.now(datetime.UTC).isoformat()
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
        with patch("scripts.fetchers.xcode.get_text"), pytest.raises(
            ValueError, match="missing required config value 'source_url'"
        ):
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


class TestExtractChangelogDates:
    def test_parses_dates_per_version(self):
        dates = _extract_changelog_dates(_FAKE_CHANGELOG)
        assert dates["0.48.0"] == "2026-04-23"
        assert dates["0.40.0"] == "2025-07-24"

    def test_ignores_trailing_heading_text(self):
        dates = _extract_changelog_dates(_FAKE_CHANGELOG)
        # "## 0.31.0 - February 11, 2025 (Public Preview)"
        assert dates["0.31.0"] == "2025-02-11"

    def test_returns_empty_for_no_dates(self):
        assert _extract_changelog_dates("## 1.0.0\nNo date here.") == {}


class TestEraForDate:
    def test_2026_is_latest(self):
        assert _era_for_date("2026-04-23") == ("xcode-latest", "Xcode latest releases")

    def test_2025(self):
        assert _era_for_date("2025-07-24") == ("xcode-2025", "Xcode 2025 releases")

    def test_2024_and_older(self):
        assert _era_for_date("2024-01-05") == ("xcode-2024", "Xcode 2024 releases")

    def test_missing_date_defaults_to_latest(self):
        assert _era_for_date(None) == ("xcode-latest", "Xcode latest releases")


class TestMergeChangelog:
    def test_matrix_record_gets_real_release_date(self):
        results = _parse_feature_matrix(
            _IDE_CONFIG, _FAKE_HTML, changelog_markdown=_FAKE_CHANGELOG
        )
        record = next(r for r in results if r["version"] == "0.48.0")
        assert record["release_date"] == "2026-04-23"

    def test_matrix_record_keeps_supported_features(self):
        results = _parse_feature_matrix(
            _IDE_CONFIG, _FAKE_HTML, changelog_markdown=_FAKE_CHANGELOG
        )
        record = next(r for r in results if r["version"] == "0.48.0")
        assert "### Supported features" in record["body_markdown"]
        assert "Code completion" in record["body_markdown"]

    def test_matrix_record_includes_changelog_notes(self):
        results = _parse_feature_matrix(
            _IDE_CONFIG, _FAKE_HTML, changelog_markdown=_FAKE_CHANGELOG
        )
        record = next(r for r in results if r["version"] == "0.48.0")
        assert "Context window usage details" in record["body_markdown"]

    def test_version_without_changelog_is_unchanged(self):
        results = _parse_feature_matrix(
            _IDE_CONFIG, _FAKE_HTML, changelog_markdown=_FAKE_CHANGELOG
        )
        # 0.47.0 is in the matrix but not the fake changelog.
        record = next(r for r in results if r["version"] == "0.47.0")
        assert "### Supported features" not in record["body_markdown"]
        assert record["release_date"] == "2026-01-01"

    def test_changelog_only_version_is_added(self):
        results = _parse_feature_matrix(
            _IDE_CONFIG, _FAKE_HTML, changelog_markdown=_FAKE_CHANGELOG
        )
        versions = {r["version"] for r in results}
        # 0.31.0 is only in the changelog, not the matrix.
        assert "0.31.0" in versions
        record = next(r for r in results if r["version"] == "0.31.0")
        assert record["xcode_era"] == "xcode-2025"
        assert record["release_date"] == "2025-02-11"
        assert "Copilot Chat support" in record["body_markdown"]

    def test_changelog_only_url_points_to_changelog(self):
        results = _merge_changelog(
            [],
            _IDE_CONFIG,
            _FAKE_CHANGELOG,
            changelog_url="https://example.test/CHANGELOG.md",
        )
        record = next(r for r in results if r["version"] == "0.48.0")
        assert record["url"] == "https://example.test/CHANGELOG.md"

    def test_changelog_url_falls_back_to_config_when_not_passed(self):
        # A direct caller supplies changelog_markdown but omits changelog_url;
        # the config's changelog_url must be used, not the feature-matrix source_url.
        config = {**_IDE_CONFIG, "changelog_url": "https://example.test/CHANGELOG.md"}
        results = _parse_feature_matrix(
            config, _FAKE_HTML, changelog_markdown=_FAKE_CHANGELOG
        )
        # 0.31.0 is changelog-only, so its url comes from the changelog_url fallback.
        record = next(r for r in results if r["version"] == "0.31.0")
        assert record["url"] == "https://example.test/CHANGELOG.md"

    def test_merged_records_pass_schema_validation(self):
        schema = json.loads(pathlib.Path("scripts/common/schema.json").read_text())
        results = _parse_feature_matrix(
            _IDE_CONFIG, _FAKE_HTML, changelog_markdown=_FAKE_CHANGELOG
        )
        for r in results:
            r["fetched_at"] = datetime.datetime.now(datetime.UTC).isoformat()
            r["schema_version"] = 1
            jsonschema.validate(r, schema)


class TestFetchWithChangelog:
    def test_fetches_changelog_without_auth(self):
        config = {**_IDE_CONFIG, "changelog_url": "https://example.test/CHANGELOG.md"}

        def fake_get_text(url, *, use_auth):
            assert use_auth is False
            return _FAKE_CHANGELOG if url.endswith("CHANGELOG.md") else _FAKE_HTML

        with patch("scripts.fetchers.xcode.get_text", side_effect=fake_get_text):
            results = fetch(config)

        versions = {r["version"] for r in results}
        assert "0.31.0" in versions  # changelog-only version present
        record = next(r for r in results if r["version"] == "0.48.0")
        assert record["release_date"] == "2026-04-23"

    def test_without_changelog_url_only_calls_source_once(self):
        with patch("scripts.fetchers.xcode.get_text", return_value=_FAKE_HTML) as mock_get:
            fetch(_IDE_CONFIG)
        mock_get.assert_called_once()


