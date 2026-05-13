"""Tests for scripts/fetchers/eclipse.py"""
from unittest.mock import patch

import pytest

from scripts.fetchers.eclipse import _parse_title, fetch

_IDE_CONFIG = {
    "id": "eclipse",
    "name": "Copilot for Eclipse",
    "data_dir": "data/eclipse",
    "fetcher": "eclipse",
    "start_version": "all",
    "source_url": "https://api.github.com/repos/microsoft/copilot-for-eclipse/releases",
}

_FAKE_RELEASES = [
    {
        "name": "0.16.0 - 20260403",
        "tag_name": "v0.16.0",
        "html_url": "https://github.com/microsoft/copilot-for-eclipse/releases/tag/v0.16.0",
        "body": "<h2>Added</h2><ul><li>GitHub Copilot chat support.</li></ul>",
    },
    {
        "name": "0.9.2 - 20250723",
        "tag_name": "v0.9.2",
        "html_url": "https://github.com/microsoft/copilot-for-eclipse/releases/tag/v0.9.2",
        "body": "<h2>Added</h2><ul><li>Initial release.</li></ul>",
    },
]


class TestParseTitle:
    def test_standard_format(self):
        version, release_date = _parse_title("0.16.0 - 20260403")
        assert version == "0.16.0"
        assert release_date == "2026-04-03"

    def test_leading_trailing_spaces(self):
        version, release_date = _parse_title("  0.9.2 - 20250723  ")
        assert version == "0.9.2"
        assert release_date == "2025-07-23"

    def test_date_components_split_correctly(self):
        _, release_date = _parse_title("1.0.0 - 20260101")
        year, month, day = release_date.split("-")
        assert year == "2026"
        assert month == "01"
        assert day == "01"

    def test_invalid_title_raises_value_error(self):
        with pytest.raises(ValueError, match="Unrecognised Eclipse release title"):
            _parse_title("Some random title")

    def test_missing_date_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_title("0.16.0")

    def test_wrong_version_format_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_title("v0.16.0 - 20260403")


class TestFetch:
    def _run_fetch(self, api_pages):
        """Helper: patch get_json to return pages of releases sequentially."""
        call_count = 0

        def fake_get_json(url, params=None, **kwargs):
            nonlocal call_count
            result = api_pages[call_count] if call_count < len(api_pages) else []
            call_count += 1
            return result

        with patch("scripts.fetchers.eclipse.get_json", side_effect=fake_get_json):
            return fetch(_IDE_CONFIG)

    def test_returns_one_release_per_item(self):
        releases = self._run_fetch([_FAKE_RELEASES, []])
        assert len(releases) == 2

    def test_version_parsed_correctly(self):
        releases = self._run_fetch([_FAKE_RELEASES, []])
        versions = {r["version"] for r in releases}
        assert "0.16.0" in versions
        assert "0.9.2" in versions

    def test_release_date_parsed_correctly(self):
        releases = self._run_fetch([_FAKE_RELEASES, []])
        by_version = {r["version"]: r for r in releases}
        assert by_version["0.16.0"]["release_date"] == "2026-04-03"
        assert by_version["0.9.2"]["release_date"] == "2025-07-23"

    def test_source_is_api(self):
        releases = self._run_fetch([_FAKE_RELEASES, []])
        assert all(r["source"] == "api" for r in releases)

    def test_ide_field_matches_config(self):
        releases = self._run_fetch([_FAKE_RELEASES, []])
        assert all(r["ide"] == "eclipse" for r in releases)

    def test_body_markdown_non_empty(self):
        releases = self._run_fetch([_FAKE_RELEASES, []])
        assert all(r["body_markdown"] for r in releases)

    def test_copilot_mentions_populated_when_present(self):
        releases = self._run_fetch([_FAKE_RELEASES, []])
        by_version = {r["version"]: r for r in releases}
        # 0.16.0 body mentions "GitHub Copilot"
        assert len(by_version["0.16.0"]["copilot_mentions"]) >= 1

    def test_unexpected_title_skipped_with_warning(self, capsys):
        bad_release = [{"name": "unexpected", "tag_name": "v0.0.0", "html_url": "", "body": ""}]
        releases = self._run_fetch([bad_release, []])
        assert releases == []
        captured = capsys.readouterr()
        assert "warn" in captured.out.lower() or "Skipping" in captured.out

    def test_pagination_fetches_all_pages(self):
        # First page has 2 items, second page has 1, third is empty → 3 total
        page1 = _FAKE_RELEASES
        page2 = [
            {
                "name": "0.10.0 - 20251001",
                "tag_name": "v0.10.0",
                "html_url": "https://github.com/microsoft/copilot-for-eclipse/releases/tag/v0.10.0",
                "body": "<p>Some fix.</p>",
            }
        ]
        releases = self._run_fetch([page1, page2, []])
        assert len(releases) == 3

    def test_empty_api_returns_empty_list(self):
        releases = self._run_fetch([[]])
        assert releases == []

    def test_uses_source_url_from_config(self):
        config = {**_IDE_CONFIG, "source_url": "https://custom.example/releases"}
        with patch("scripts.fetchers.eclipse.get_json", side_effect=[[], []]) as mock_get_json:
            fetch(config)
        assert mock_get_json.call_args_list[0].args[0] == "https://custom.example/releases"

    def test_missing_source_url_raises(self):
        config = dict(_IDE_CONFIG)
        config.pop("source_url")
        with pytest.raises(ValueError, match="missing required config value 'source_url'"):
            fetch(config)
