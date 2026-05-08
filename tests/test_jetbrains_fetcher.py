"""Tests for scripts/fetchers/jetbrains.py"""
from unittest.mock import patch

import pytest

from scripts.fetchers.jetbrains import _parse_version, fetch

_IDE_CONFIG = {
    "id": "jetbrains",
    "name": "GitHub Copilot for JetBrains",
    "data_dir": "data/jetbrains",
    "fetcher": "jetbrains",
    "start_version": "all",
}

# Fake API update entries (two builds for 1.5.62, one for 1.5.63)
_FAKE_UPDATES_PAGE1 = [
    {
        "id": 1001,
        "version": "1.5.62-241",
        "since": "241.1",
        "until": "241.*",
        "cdate": 1700000000000,
        "downloads": 5000,
        "compatibleVersions": {"IntelliJ IDEA": ["2024.1"]},
        "notes": "<h2>Changes</h2><ul><li>GitHub Copilot inline completions improved.</li></ul>",
    },
    {
        "id": 1002,
        "version": "1.5.62-242",
        "since": "242.1",
        "until": "242.*",
        "cdate": 1700000000000,
        "downloads": 3000,
        "compatibleVersions": {"IntelliJ IDEA": ["2024.2"]},
        "notes": "<h2>Changes</h2><ul><li>GitHub Copilot inline completions improved.</li></ul>",
    },
    {
        "id": 1003,
        "version": "1.5.63-241",
        "since": "241.1",
        "until": "241.*",
        "cdate": 1701000000000,
        "downloads": 2000,
        "compatibleVersions": {"IntelliJ IDEA": ["2024.1"]},
        "notes": "<h2>Changes</h2><ul><li>Bug fix in Copilot chat.</li></ul>",
    },
]

_FAKE_UPDATES_PAGE2 = [
    {
        "id": 1004,
        "version": "1.5.62-243",
        "since": "243.1",
        "until": "243.*",
        "cdate": 1700000000000,
        "downloads": 1500,
        "compatibleVersions": {"IntelliJ IDEA": ["2024.3"]},
        "notes": "<h2>Changes</h2><ul><li>GitHub Copilot inline completions improved.</li></ul>",
    },
]

# Realistic 4-part version format as returned by the actual JetBrains Marketplace API
_FAKE_UPDATES_FOUR_PART = [
    {
        "id": 2001,
        "version": "1.5.6.8049-251",
        "since": "251.1",
        "until": "251.*",
        "cdate": 1745280000000,  # 2025-04-22
        "downloads": 84321,
        "compatibleVersions": {"IntelliJ IDEA": ["2025.1"]},
        "notes": "<h2>What's new</h2><ul><li>GitHub Copilot improved inline chat experience.</li></ul>",
    },
    {
        "id": 2002,
        "version": "1.5.6.8049-243",
        "since": "243.1",
        "until": "243.*",
        "cdate": 1745280000000,
        "downloads": 39201,
        "compatibleVersions": {"IntelliJ IDEA": ["2024.3"]},
        "notes": "<h2>What's new</h2><ul><li>GitHub Copilot improved inline chat experience.</li></ul>",
    },
    {
        "id": 2003,
        "version": "1.5.5.7956-251",
        "since": "251.1",
        "until": "251.*",
        "cdate": 1744070400000,  # 2025-04-08
        "downloads": 12000,
        "compatibleVersions": {"IntelliJ IDEA": ["2025.1"]},
        "notes": "<h2>What's new</h2><ul><li>Copilot Chat now supports multi-file context.</li></ul>",
    },
]


class TestParseVersion:
    def test_standard_format(self):
        semver, ide_build = _parse_version("1.5.62-241")
        assert semver == "1.5.62"
        assert ide_build == "241"

    def test_four_part_version(self):
        semver, ide_build = _parse_version("1.5.6.8049-251")
        assert semver == "1.5.6.8049"
        assert ide_build == "251"

    def test_leading_trailing_spaces(self):
        semver, ide_build = _parse_version("  1.8.2-243  ")
        assert semver == "1.8.2"
        assert ide_build == "243"

    def test_four_part_leading_trailing_spaces(self):
        semver, ide_build = _parse_version("  1.5.6.8049-251  ")
        assert semver == "1.5.6.8049"
        assert ide_build == "251"

    def test_large_build_number(self):
        semver, ide_build = _parse_version("2.0.0-9999")
        assert semver == "2.0.0"
        assert ide_build == "9999"

    def test_invalid_format_raises_value_error(self):
        with pytest.raises(ValueError, match="Unrecognised JetBrains version string"):
            _parse_version("1.5.62")

    def test_legacy_no_build_suffix_format(self):
        # 4-part version with no build suffix (legacy universal releases)
        semver, ide_build = _parse_version("1.5.29.7524")
        assert semver == "1.5.29.7524"
        assert ide_build is None

    def test_three_part_no_suffix_raises_value_error(self):
        # 3-part without suffix is not a recognised format
        with pytest.raises(ValueError):
            _parse_version("1.5.62")

    def test_no_build_suffix_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_version("1.5.62-abc")

    def test_wrong_semver_format_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_version("v1.5.62-241")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_version("")


class TestFetch:
    def _run_fetch(self, api_pages):
        """Helper: patch get_json to return pages of updates sequentially."""
        call_count = 0

        def fake_get_json(url, params=None, **kwargs):
            nonlocal call_count
            result = api_pages[call_count] if call_count < len(api_pages) else []
            call_count += 1
            return result

        with patch("scripts.fetchers.jetbrains.get_json", side_effect=fake_get_json):
            return fetch(_IDE_CONFIG)

    def test_groups_builds_by_semver(self):
        # 1.5.62 has 2 builds, 1.5.63 has 1 build → 2 release dicts
        releases = self._run_fetch([_FAKE_UPDATES_PAGE1, []])
        versions = {r["version"] for r in releases}
        assert "1.5.62" in versions
        assert "1.5.63" in versions
        assert len(releases) == 2

    def test_builds_array_populated(self):
        releases = self._run_fetch([_FAKE_UPDATES_PAGE1, []])
        by_version = {r["version"]: r for r in releases}
        assert len(by_version["1.5.62"]["builds"]) == 2
        assert len(by_version["1.5.63"]["builds"]) == 1

    def test_builds_array_contains_ide_build(self):
        releases = self._run_fetch([_FAKE_UPDATES_PAGE1, []])
        by_version = {r["version"]: r for r in releases}
        ide_builds = {b["ide_build"] for b in by_version["1.5.62"]["builds"]}
        assert "241" in ide_builds
        assert "242" in ide_builds

    def test_pagination_fetches_all_pages(self):
        # Page 1: 1.5.62-241, 1.5.62-242, 1.5.63-241; Page 2: 1.5.62-243
        releases = self._run_fetch([_FAKE_UPDATES_PAGE1, _FAKE_UPDATES_PAGE2, []])
        by_version = {r["version"]: r for r in releases}
        # 1.5.62 should now have 3 builds
        assert len(by_version["1.5.62"]["builds"]) == 3
        ide_builds = {b["ide_build"] for b in by_version["1.5.62"]["builds"]}
        assert "241" in ide_builds
        assert "242" in ide_builds
        assert "243" in ide_builds

    def test_pagination_deduplicates_by_id(self):
        """Entries repeated across pages (real API behaviour) must not be counted twice."""
        # id=1001 (1.5.62-241) appears on both pages
        page1 = _FAKE_UPDATES_PAGE1  # contains id 1001, 1002, 1003
        page2_with_dupe = [
            _FAKE_UPDATES_PAGE1[0],  # id=1001 again (duplicate)
            _FAKE_UPDATES_PAGE2[0],  # id=1004 (new)
        ]
        releases = self._run_fetch([page1, page2_with_dupe, []])
        by_version = {r["version"]: r for r in releases}
        # 1.5.62 should have 3 unique builds (241, 242, 243), not 4
        assert len(by_version["1.5.62"]["builds"]) == 3
        ids = [b["file_id"] for b in by_version["1.5.62"]["builds"]]
        assert len(ids) == len(set(ids)), "Duplicate file IDs in builds"

    def test_release_date_uses_earliest_cdate(self):
        # Both 1.5.62 builds share cdate 1700000000000 → 2023-11-14
        releases = self._run_fetch([_FAKE_UPDATES_PAGE1, []])
        by_version = {r["version"]: r for r in releases}
        assert by_version["1.5.62"]["release_date"] == "2023-11-14"

    def test_release_date_format_is_iso8601(self):
        releases = self._run_fetch([_FAKE_UPDATES_PAGE1, []])
        for r in releases:
            parts = r["release_date"].split("-")
            assert len(parts) == 3
            assert len(parts[0]) == 4  # year
            assert len(parts[1]) == 2  # month
            assert len(parts[2]) == 2  # day

    def test_source_is_api(self):
        releases = self._run_fetch([_FAKE_UPDATES_PAGE1, []])
        assert all(r["source"] == "api" for r in releases)

    def test_ide_field_matches_config(self):
        releases = self._run_fetch([_FAKE_UPDATES_PAGE1, []])
        assert all(r["ide"] == "jetbrains" for r in releases)

    def test_body_markdown_non_empty_when_notes_present(self):
        releases = self._run_fetch([_FAKE_UPDATES_PAGE1, []])
        assert all(r["body_markdown"] for r in releases)

    def test_copilot_mentions_populated(self):
        releases = self._run_fetch([_FAKE_UPDATES_PAGE1, []])
        by_version = {r["version"]: r for r in releases}
        # Both releases mention "Copilot"
        assert len(by_version["1.5.62"]["copilot_mentions"]) >= 1
        assert len(by_version["1.5.63"]["copilot_mentions"]) >= 1

    def test_unexpected_version_skipped_with_warning(self, capsys):
        bad_update = [{"id": 9999, "version": "unexpected", "cdate": 0, "notes": ""}]
        releases = self._run_fetch([bad_update, []])
        assert releases == []
        captured = capsys.readouterr()
        assert "warn" in captured.out.lower() or "Skipping" in captured.out

    def test_empty_api_returns_empty_list(self):
        releases = self._run_fetch([[]])
        assert releases == []

    def test_builds_contain_since_and_until(self):
        releases = self._run_fetch([_FAKE_UPDATES_PAGE1, []])
        by_version = {r["version"]: r for r in releases}
        for build in by_version["1.5.62"]["builds"]:
            assert "since" in build
            assert "until" in build

    def test_builds_contain_downloads(self):
        releases = self._run_fetch([_FAKE_UPDATES_PAGE1, []])
        by_version = {r["version"]: r for r in releases}
        for build in by_version["1.5.62"]["builds"]:
            assert "downloads" in build

    def test_missing_cdate_falls_back_to_epoch(self):
        update_no_cdate = [
            {
                "id": 2001,
                "version": "2.0.0-241",
                "since": "241.1",
                "until": "241.*",
                "cdate": None,
                "downloads": 100,
                "notes": "",
            }
        ]
        releases = self._run_fetch([update_no_cdate, []])
        assert releases[0]["release_date"] == "1970-01-01"

    def test_cdate_as_string_parsed_correctly(self):
        """Real API returns cdate as a string, not an integer."""
        update_string_cdate = [
            {
                "id": 3001,
                "version": "2.1.0-251",
                "since": "251.0",
                "until": "",
                "cdate": "1778131970000",  # string, as returned by real API
                "downloads": 500,
                "notes": "<ul><li>GitHub Copilot update.</li></ul>",
            }
        ]
        releases = self._run_fetch([update_string_cdate, []])
        assert len(releases) == 1
        # 1778131970 seconds → 2026-05-07
        assert releases[0]["release_date"] == "2026-05-07"


class TestFetchLegacyVersions:
    """Tests for legacy 4-part no-build-suffix versions (e.g. 1.5.29.7524)."""

    _FAKE_LEGACY = [
        {
            "id": 5001,
            "version": "1.5.29.7524",
            "since": "231.0",
            "until": "243.*",
            "cdate": 1700000000000,
            "downloads": 661644,
            "compatibleVersions": {"IntelliJ IDEA": ["2023.1", "2023.3"]},
            "notes": "<h2>Changes</h2><ul><li>GitHub Copilot stability improvements.</li></ul>",
        },
        {
            "id": 5002,
            "version": "1.5.28.7313",
            "since": "231.0",
            "until": "242.*",
            "cdate": 1695000000000,
            "downloads": 174214,
            "compatibleVersions": {"IntelliJ IDEA": ["2023.1", "2023.2"]},
            "notes": "<h2>Changes</h2><ul><li>Copilot Chat beta improvements.</li></ul>",
        },
    ]

    def _run_fetch(self, api_pages):
        call_count = 0

        def fake_get_json(url, params=None, **kwargs):
            nonlocal call_count
            result = api_pages[call_count] if call_count < len(api_pages) else []
            call_count += 1
            return result

        with patch("scripts.fetchers.jetbrains.get_json", side_effect=fake_get_json):
            return fetch(_IDE_CONFIG)

    def test_legacy_versions_are_included(self):
        releases = self._run_fetch([self._FAKE_LEGACY, []])
        versions = {r["version"] for r in releases}
        assert "1.5.29.7524" in versions
        assert "1.5.28.7313" in versions

    def test_legacy_version_has_single_build_entry(self):
        releases = self._run_fetch([self._FAKE_LEGACY, []])
        by_version = {r["version"]: r for r in releases}
        assert len(by_version["1.5.29.7524"]["builds"]) == 1

    def test_legacy_version_ide_build_is_none(self):
        releases = self._run_fetch([self._FAKE_LEGACY, []])
        by_version = {r["version"]: r for r in releases}
        assert by_version["1.5.29.7524"]["builds"][0]["ide_build"] is None

    def test_legacy_version_passes_schema_validation(self):
        import json, pathlib
        import jsonschema

        schema = json.loads(
            pathlib.Path("scripts/common/schema.json").read_text()
        )
        releases = self._run_fetch([self._FAKE_LEGACY, []])
        # Add required fields that write_release would normally inject
        import datetime as _dt
        for r in releases:
            r["fetched_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
            r["schema_version"] = 1
        for r in releases:
            jsonschema.validate(r, schema)  # raises if invalid


class TestFetchFourPartVersions:
    """Tests that verify the fetcher handles 4-part version strings (actual API format)."""

    def _run_fetch(self, api_pages):
        call_count = 0

        def fake_get_json(url, params=None, **kwargs):
            nonlocal call_count
            result = api_pages[call_count] if call_count < len(api_pages) else []
            call_count += 1
            return result

        with patch("scripts.fetchers.jetbrains.get_json", side_effect=fake_get_json):
            return fetch(_IDE_CONFIG)

    def test_groups_four_part_versions_by_semver(self):
        releases = self._run_fetch([_FAKE_UPDATES_FOUR_PART, []])
        versions = {r["version"] for r in releases}
        assert "1.5.6.8049" in versions
        assert "1.5.5.7956" in versions
        assert len(releases) == 2

    def test_four_part_builds_array_populated(self):
        releases = self._run_fetch([_FAKE_UPDATES_FOUR_PART, []])
        by_version = {r["version"]: r for r in releases}
        # 1.5.6.8049 has 2 builds (-251 and -243)
        assert len(by_version["1.5.6.8049"]["builds"]) == 2

    def test_four_part_ide_builds_captured(self):
        releases = self._run_fetch([_FAKE_UPDATES_FOUR_PART, []])
        by_version = {r["version"]: r for r in releases}
        ide_builds = {b["ide_build"] for b in by_version["1.5.6.8049"]["builds"]}
        assert "251" in ide_builds
        assert "243" in ide_builds

    def test_four_part_release_date_derived_from_cdate(self):
        releases = self._run_fetch([_FAKE_UPDATES_FOUR_PART, []])
        by_version = {r["version"]: r for r in releases}
        # cdate 1745280000000 → 2025-04-22
        assert by_version["1.5.6.8049"]["release_date"] == "2025-04-22"
        # cdate 1744070400000 → 2025-04-08
        assert by_version["1.5.5.7956"]["release_date"] == "2025-04-08"

    def test_four_part_copilot_mentions_extracted(self):
        releases = self._run_fetch([_FAKE_UPDATES_FOUR_PART, []])
        assert all(len(r["copilot_mentions"]) >= 1 for r in releases)

