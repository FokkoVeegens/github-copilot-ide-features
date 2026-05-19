"""Tests for scripts/fetchers/ssms.py."""

from unittest.mock import patch

import pytest

from scripts.fetchers.ssms import _is_at_or_above_start_version, fetch

_IDE_CONFIG = {
    "id": "sql-server-management-studio",
    "name": "SQL Server Management Studio",
    "data_dir": "data/sql-server-management-studio",
    "fetcher": "ssms",
    "start_version": "22.0.0",
    "source_urls": [
        "https://learn.microsoft.com/en-us/ssms/release-notes-22",
        "https://learn.microsoft.com/en-us/ssms/release-notes-21",
    ],
}

_FAKE_HTML_22 = """\
<!DOCTYPE html>
<html>
<body>
  <h3>22.0.1</h3>
  <p>Release date: June 19, 2026</p>
  <h4>What's new in 22.0.1</h4>
  <ul><li>GitHub Copilot chat improvements.</li></ul>
  <h4>Bug fixes in 22.0.1</h4>
  <ul><li>Fixed query editor responsiveness.</li></ul>
</body>
</html>
"""

_FAKE_HTML_21 = """\
<!DOCTYPE html>
<html>
<body>
  <h3>20.2.9</h3>
  <p>Release date: April 10, 2025</p>
  <h4>What's new in 20.2.9</h4>
  <p>Pre-Copilot release.</p>
  <h4>Bug fixes in 20.2.9</h4>
  <p>Legacy fixes.</p>

  <h3>21.0.0</h3>
  <p>Release date: May 13, 2025</p>
  <h4>What's new in 21.0.0</h4>
  <ul><li>GitHub Copilot introduced in SSMS.</li></ul>
  <h4>Bug fixes in 21.0.0</h4>
  <ul><li>Stability fixes.</li></ul>
</body>
</html>
"""


class TestStartVersionFilter:
    def test_version_equal_to_floor_is_included(self):
        assert _is_at_or_above_start_version("22.0.0", "22.0.0") is True

    def test_version_below_floor_is_excluded(self):
        assert _is_at_or_above_start_version("21.6.17", "22.0.0") is False


class TestFetch:
    def test_uses_config_source_urls(self):
        with patch(
            "scripts.fetchers.ssms.get_text",
            side_effect=[_FAKE_HTML_22, _FAKE_HTML_21],
        ) as mock_get_text:
            fetch(_IDE_CONFIG)

        called_urls = [call.args[0] for call in mock_get_text.call_args_list]
        assert called_urls == _IDE_CONFIG["source_urls"]

    def test_filters_out_versions_below_start_version(self):
        with patch(
            "scripts.fetchers.ssms.get_text",
            side_effect=[_FAKE_HTML_22, _FAKE_HTML_21],
        ):
            results = fetch(_IDE_CONFIG)

        versions = [record["version"] for record in results]
        assert "20.2.9" not in versions
        assert "21.0.0" not in versions
        assert "22.0.1" in versions

    def test_includes_whats_new_and_bug_fixes_in_body_markdown(self):
        with patch(
            "scripts.fetchers.ssms.get_text",
            side_effect=[_FAKE_HTML_22, _FAKE_HTML_21],
        ):
            results = fetch(_IDE_CONFIG)

        record = next(item for item in results if item["version"] == "22.0.1")
        assert "What's new in 22.0.1" in record["body_markdown"]
        assert "Bug fixes in 22.0.1" in record["body_markdown"]

    def test_parses_release_date_and_populates_required_fields(self):
        with patch(
            "scripts.fetchers.ssms.get_text",
            side_effect=[_FAKE_HTML_22, _FAKE_HTML_21],
        ):
            results = fetch(_IDE_CONFIG)

        record = next(item for item in results if item["version"] == "22.0.1")
        assert record["ide"] == "sql-server-management-studio"
        assert record["release_date"] == "2026-06-19"
        assert record["title"] == "22.0.1"
        assert record["url"] == "https://learn.microsoft.com/en-us/ssms/release-notes-22"
        assert record["source"] == "html"
        assert len(record["copilot_mentions"]) >= 1

    def test_missing_source_urls_raises(self):
        config = dict(_IDE_CONFIG)
        config.pop("source_urls")
        with pytest.raises(ValueError, match="missing required config value 'source_urls'"):
            fetch(config)
