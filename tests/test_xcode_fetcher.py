"""Tests for scripts/fetchers/xcode.py."""
from unittest.mock import patch

import pytest

from scripts.common.github_releases import parse_tag_version
from scripts.fetchers.xcode import fetch

_IDE_CONFIG = {
    "id": "xcode",
    "name": "GitHub Copilot for Xcode",
    "data_dir": "data/xcode",
    "fetcher": "xcode",
}

_FAKE_CHANGELOG = """
## [0.48.0]
- Added GitHub Copilot fixes.

## [0.47.0]
- Older notes.
"""

_FAKE_RELEASES = [
    {
        "tag_name": "v0.48.0",
        "name": "v0.48.0",
        "html_url": "https://github.com/github/CopilotForXcode/releases/tag/v0.48.0",
        "body": "Release placeholder body",
        "published_at": "2026-04-22T12:00:00Z",
        "prerelease": False,
    },
    {
        "tag_name": "v0.49.0",
        "name": "v0.49.0",
        "html_url": "https://github.com/github/CopilotForXcode/releases/tag/v0.49.0",
        "body": "Fallback API notes with Copilot.",
        "published_at": "2026-05-01T12:00:00Z",
        "prerelease": True,
    },
]


class TestParseTagVersion:
    def test_strips_v_prefix(self):
        assert parse_tag_version("v0.48.0", error_label="Xcode") == "0.48.0"

    def test_accepts_plain_version(self):
        assert parse_tag_version("0.48.0", error_label="Xcode") == "0.48.0"

    def test_invalid_tag_raises(self):
        with pytest.raises(ValueError):
            parse_tag_version("release-0.48.0", error_label="Xcode")


class TestFetch:
    def _run_fetch(self, pages, changelog):
        call_count = 0

        def fake_get_json(url, params=None, **kwargs):
            nonlocal call_count
            result = pages[call_count] if call_count < len(pages) else []
            call_count += 1
            return result

        with patch("scripts.fetchers.xcode.get_json", side_effect=fake_get_json), patch(
            "scripts.fetchers.xcode.get_text", return_value=changelog
        ):
            return fetch(_IDE_CONFIG)

    def test_uses_changelog_section_when_available(self):
        releases = self._run_fetch([_FAKE_RELEASES, []], _FAKE_CHANGELOG)
        by_version = {r["version"]: r for r in releases}
        assert by_version["0.48.0"]["source"] == "api"
        assert "Added GitHub Copilot fixes." in by_version["0.48.0"]["body_markdown"]

    def test_falls_back_to_api_body_when_missing_in_changelog(self):
        releases = self._run_fetch([_FAKE_RELEASES, []], _FAKE_CHANGELOG)
        by_version = {r["version"]: r for r in releases}
        assert by_version["0.49.0"]["source"] == "api_fallback"
        assert by_version["0.49.0"]["body_markdown"] == "Fallback API notes with Copilot."

    def test_prerelease_field_is_propagated(self):
        releases = self._run_fetch([_FAKE_RELEASES, []], _FAKE_CHANGELOG)
        by_version = {r["version"]: r for r in releases}
        assert by_version["0.48.0"]["prerelease"] is False
        assert by_version["0.49.0"]["prerelease"] is True

    def test_pagination_fetches_all_pages(self):
        page2 = [
            {
                "tag_name": "v0.47.0",
                "name": "v0.47.0",
                "html_url": "",
                "body": "",
                "published_at": "2026-03-10T12:00:00Z",
                "prerelease": False,
            }
        ]
        releases = self._run_fetch([_FAKE_RELEASES, page2, []], _FAKE_CHANGELOG)
        assert {r["version"] for r in releases} == {"0.48.0", "0.49.0", "0.47.0"}

    def test_uses_source_url_from_config(self):
        config = {**_IDE_CONFIG, "source_url": "https://custom.example/releases"}

        with patch("scripts.fetchers.xcode.get_text", return_value=_FAKE_CHANGELOG), patch(
            "scripts.fetchers.xcode.get_json", side_effect=[[], []]
        ) as mock_get_json:
            fetch(config)

        assert mock_get_json.call_args_list[0].args[0] == "https://custom.example/releases"
