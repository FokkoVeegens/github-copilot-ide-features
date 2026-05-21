"""Tests for scripts/fetchers/visual_studio.py."""

from unittest.mock import patch

import pytest

from scripts.fetchers.visual_studio import _is_at_or_above_start_version, fetch

_IDE_CONFIG = {
    "id": "visual-studio-2026",
    "name": "Visual Studio 2026",
    "data_dir": "data/visual-studio-2026",
    "fetcher": "visual_studio",
    "start_version": "17.14.0",
    "source_url": "https://learn.microsoft.com/en-us/visualstudio/releases/2026/release-notes",
}

_FAKE_HTML = """\
<!DOCTYPE html>
<html>
<body>
  <h2>Version 17.13.9</h2>
    <p>Released on December 12th, 2025.</p>
  <div><p>Older content.</p></div>

  <h2>March Update 17.14.0</h2>
    <p>Released on January 8th, 2026.</p>
  <div>
    <h3>GitHub Copilot</h3>
    <p>Major feature wave for the 17.14 baseline release.</p>
  </div>

  <h2>Version 17.14.1</h2>
    <p>Released on January 15th, 2026.</p>
  <div>
    <h3>What's new</h3>
    <p>GitHub Copilot agent mode is now included.</p>
  </div>

  <h2>Version 17.14.31</h2>
    <p>Released on April 21th, 2026.</p>
  <div>
    <h3>Improvements</h3>
    <p>GitHub Copilot chat fixes and performance updates.</p>
  </div>
</body>
</html>
"""


class TestStartVersionFilter:
    def test_version_equal_to_floor_is_included(self):
        assert _is_at_or_above_start_version("17.14.0", "17.14.0") is True

    def test_version_below_floor_is_excluded(self):
        assert _is_at_or_above_start_version("17.13.9", "17.14.0") is False


class TestFetch:
    def test_returns_one_record_per_matching_section_at_or_above_start_version(self):
        with patch("scripts.fetchers.visual_studio.get_text", return_value=_FAKE_HTML):
            results = fetch(_IDE_CONFIG)

        assert [record["version"] for record in results] == ["17.14.0", "17.14.1", "17.14.31"]

    def test_record_fields_are_populated(self):
        with patch("scripts.fetchers.visual_studio.get_text", return_value=_FAKE_HTML):
            results = fetch(_IDE_CONFIG)

        record = next(item for item in results if item["version"] == "17.14.31")
        assert record["ide"] == "visual-studio-2026"
        assert record["release_date"] == "2026-04-21"
        assert record["title"] == "Version 17.14.31"
        assert record["url"] == _IDE_CONFIG["source_url"]
        assert record["source"] == "html"
        assert "GitHub Copilot chat fixes" in record["body_markdown"]
        assert len(record["copilot_mentions"]) == 1

    def test_uses_source_url_from_config(self):
        config = {**_IDE_CONFIG, "source_url": "https://example.test/visual-studio-2026"}
        with patch("scripts.fetchers.visual_studio.get_text", return_value=_FAKE_HTML) as mock_get_text:
            fetch(config)

        assert mock_get_text.call_args.args[0] == "https://example.test/visual-studio-2026"

    def test_missing_source_url_raises(self):
        config = dict(_IDE_CONFIG)
        config.pop("source_url")
        with patch("scripts.fetchers.visual_studio.get_text"), pytest.raises(
            ValueError, match="missing required config value 'source_url'"
        ):
            fetch(config)