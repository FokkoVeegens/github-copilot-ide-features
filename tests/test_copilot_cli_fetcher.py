"""Tests for scripts/fetchers/copilot_cli.py."""
from unittest.mock import patch

from scripts.fetchers.copilot_cli import fetch

_IDE_CONFIG = {
    "id": "copilot-cli",
    "name": "GitHub Copilot CLI",
    "data_dir": "data/copilot-cli",
    "fetcher": "copilot_cli",
    "start_version": "all",
    "source_url": "https://api.github.com/repos/github/copilot-cli/releases",
}

_FAKE_RELEASES = [
    {
        "tag_name": "v1.2.3",
        "name": "v1.2.3",
        "html_url": "https://github.com/github/copilot-cli/releases/tag/v1.2.3",
        "published_at": "2026-06-01T10:00:00Z",
        "body": "Added GitHub Copilot chat improvements for the CLI.",
        "prerelease": False,
    },
    {
        "tag_name": "v1.3.0-beta.1",
        "name": "v1.3.0-beta.1",
        "html_url": "https://github.com/github/copilot-cli/releases/tag/v1.3.0-beta.1",
        "published_at": "2026-06-02T08:00:00Z",
        "body": "Preview release with Copilot onboarding updates.",
        "prerelease": True,
    },
]


class TestFetch:
    def _run_fetch(self, api_pages):
        call_count = 0

        def fake_get_json(url, params=None, **kwargs):
            nonlocal call_count
            result = api_pages[call_count] if call_count < len(api_pages) else []
            call_count += 1
            return result

        with patch("scripts.fetchers.copilot_cli.get_json", side_effect=fake_get_json):
            return fetch(_IDE_CONFIG)

    def test_returns_releases_from_all_pages(self):
        page1 = [_FAKE_RELEASES[0]]
        page2 = [_FAKE_RELEASES[1]]
        releases = self._run_fetch([page1, page2, []])
        assert len(releases) == 2

    def test_parses_versions_from_tags(self):
        releases = self._run_fetch([_FAKE_RELEASES, []])
        assert {r["version"] for r in releases} == {"1.2.3", "1.3.0-beta.1"}

    def test_populates_expected_fields(self):
        releases = self._run_fetch([_FAKE_RELEASES, []])
        stable = next(r for r in releases if r["version"] == "1.2.3")
        assert stable["ide"] == "copilot-cli"
        assert stable["release_date"] == "2026-06-01"
        assert stable["source"] == "api"
        assert stable["url"] == "https://github.com/github/copilot-cli/releases/tag/v1.2.3"
        assert stable["body_html"] is None

    def test_preserves_prerelease_flag(self):
        releases = self._run_fetch([_FAKE_RELEASES, []])
        by_version = {r["version"]: r for r in releases}
        assert by_version["1.2.3"]["prerelease"] is False
        assert by_version["1.3.0-beta.1"]["prerelease"] is True

    def test_copilot_mentions_are_extracted(self):
        releases = self._run_fetch([_FAKE_RELEASES, []])
        assert all(len(r["copilot_mentions"]) > 0 for r in releases)

    def test_unexpected_tag_is_skipped_with_warning(self, capsys):
        bad_release = [{"tag_name": "release-1", "name": "release-1", "body": "", "html_url": ""}]
        releases = self._run_fetch([bad_release, []])
        assert releases == []
        captured = capsys.readouterr()
        assert "warn" in captured.out.lower() or "skipping" in captured.out.lower()

    def test_missing_published_date_falls_back_to_epoch(self):
        no_date_release = [
            {
                "tag_name": "v1.0.0",
                "name": "v1.0.0",
                "html_url": "",
                "body": "",
            }
        ]
        releases = self._run_fetch([no_date_release, []])
        assert releases[0]["release_date"] == "1970-01-01"

    def test_uses_source_url_from_config(self):
        config = {**_IDE_CONFIG, "source_url": "https://custom.example/releases"}
        with patch("scripts.fetchers.copilot_cli.get_json", side_effect=[[], []]) as mock_get_json:
            fetch(config)
        assert mock_get_json.call_args_list[0].args[0] == "https://custom.example/releases"

    def test_default_source_url_used_when_missing(self):
        config = dict(_IDE_CONFIG)
        config.pop("source_url")
        with patch("scripts.fetchers.copilot_cli.get_json", side_effect=[[], []]) as mock_get_json:
            fetch(config)
        assert (
            mock_get_json.call_args_list[0].args[0]
            == "https://api.github.com/repos/github/copilot-cli/releases"
        )
