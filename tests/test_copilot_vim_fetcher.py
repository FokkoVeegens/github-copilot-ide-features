"""Tests for scripts/fetchers/copilot_vim.py."""
from unittest.mock import patch

import pytest

from scripts.common.github_releases import parse_tag_version
from scripts.fetchers.copilot_vim import fetch

_IDE_CONFIG = {
    "id": "vim-neovim",
    "name": "GitHub Copilot for Vim/Neovim",
    "data_dir": "data/vim-neovim",
    "fetcher": "copilot_vim",
}

_FAKE_CHANGELOG = """
## 1.59.0
- Copilot chat improvements.

## 1.58.0
- Older notes.
"""

_FAKE_RELEASES = [
    {
        "tag_name": "v1.59.0",
        "name": "Copilot.vim 1.59.0",
        "html_url": "https://github.com/github/copilot.vim/releases/tag/v1.59.0",
        "body": "Placeholder body",
        "published_at": "2026-04-20T12:00:00Z",
        "prerelease": False,
    },
    {
        "tag_name": "v1.60.0",
        "name": "Copilot.vim 1.60.0",
        "html_url": "https://github.com/github/copilot.vim/releases/tag/v1.60.0",
        "body": "Fallback API body with Copilot mention.",
        "published_at": "2026-05-04T12:00:00Z",
        "prerelease": False,
    },
]


class TestParseTagVersion:
    def test_strips_v_prefix(self):
        assert parse_tag_version("v1.59.0", error_label="Vim/Neovim") == "1.59.0"

    def test_accepts_plain_version(self):
        assert parse_tag_version("1.59.0", error_label="Vim/Neovim") == "1.59.0"

    def test_invalid_tag_raises(self):
        with pytest.raises(ValueError):
            parse_tag_version("release-1.59.0", error_label="Vim/Neovim")


class TestFetch:
    def _run_fetch(self, pages, changelog):
        call_count = 0

        def fake_get_json(url, params=None, **kwargs):
            nonlocal call_count
            result = pages[call_count] if call_count < len(pages) else []
            call_count += 1
            return result

        with patch("scripts.fetchers.copilot_vim.get_json", side_effect=fake_get_json), patch(
            "scripts.fetchers.copilot_vim.get_text", return_value=changelog
        ):
            return fetch(_IDE_CONFIG)

    def test_uses_changelog_section_when_available(self):
        releases = self._run_fetch([_FAKE_RELEASES, []], _FAKE_CHANGELOG)
        by_version = {r["version"]: r for r in releases}
        assert by_version["1.59.0"]["source"] == "api"
        assert "Copilot chat improvements." in by_version["1.59.0"]["body_markdown"]

    def test_falls_back_to_api_body_when_missing_in_changelog(self):
        releases = self._run_fetch([_FAKE_RELEASES, []], _FAKE_CHANGELOG)
        by_version = {r["version"]: r for r in releases}
        assert by_version["1.60.0"]["source"] == "api_fallback"
        assert by_version["1.60.0"]["body_markdown"] == "Fallback API body with Copilot mention."

    def test_release_date_parsed_from_published_at(self):
        releases = self._run_fetch([_FAKE_RELEASES, []], _FAKE_CHANGELOG)
        by_version = {r["version"]: r for r in releases}
        assert by_version["1.59.0"]["release_date"] == "2026-04-20"

    def test_pagination_fetches_all_pages(self):
        page2 = [
            {
                "tag_name": "v1.58.0",
                "name": "Copilot.vim 1.58.0",
                "html_url": "",
                "body": "",
                "published_at": "2026-03-01T12:00:00Z",
                "prerelease": False,
            }
        ]
        releases = self._run_fetch([_FAKE_RELEASES, page2, []], _FAKE_CHANGELOG)
        assert {r["version"] for r in releases} == {"1.59.0", "1.60.0", "1.58.0"}
