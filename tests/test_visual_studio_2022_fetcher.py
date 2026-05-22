"""Tests for scripts/fetchers/visual_studio_2022.py."""

import datetime
import json
import pathlib
from unittest.mock import patch

import jsonschema

from scripts.fetchers.visual_studio_2022 import (
    _discover_release_note_urls,
    fetch,
)

_IDE_CONFIG = {
    "id": "visual-studio-2022",
    "name": "Visual Studio 2022",
    "data_dir": "data/visual-studio-2022",
    "fetcher": "visual_studio_2022",
    "start_version": "17.7",
    "source_url": "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-history",
}

_FAKE_HISTORY_HTML = """\
<!DOCTYPE html>
<html>
<body>
  <a href="release-notes">Visual Studio 2022 version 17.14 Release Notes</a>
  <a href="release-notes-v17.13">Visual Studio 2022 version 17.13 Release Notes</a>
  <a href="release-notes-v17.7">Visual Studio 2022 version 17.7 Release Notes</a>
  <a href="release-notes-v17.6">Visual Studio 2022 version 17.6 Release Notes</a>
</body>
</html>
"""

_FAKE_HISTORY_WITH_17_10_HTML = """\
<!DOCTYPE html>
<html>
<body>
    <a href="release-notes-v17.10">Visual Studio 2022 version 17.10 Release Notes</a>
</body>
</html>
"""

_FAKE_17_14_HTML = """\
<!DOCTYPE html>
<html>
<body>
  <h2>Features</h2>
  <p>Current highlights.</p>

  <h2>Version 17.14.2</h2>
  <p>Released May 13 th , 2025</p>
  <div>
    <h3>GitHub Copilot</h3>
    <p>GitHub Copilot now supports prompt files in Visual Studio.</p>
  </div>

  <h2>Version 17.14.1</h2>
  <p>Released April 8th, 2025</p>
  <div><p>Servicing fixes.</p></div>
  <hr />
  <p>From our entire team, thank you for choosing Visual Studio!</p>
  <p><strong>Happy coding!</strong></p>
  <div class="NOTE"><p>This update may include new third-party software that is licensed separately, as set out in the 3rd Party Notices.</p></div>
</body>
</html>
"""

_FAKE_17_13_HTML = """\
<!DOCTYPE html>
<html>
<body>
    <h1>Visual Studio 2022 version 17.13 release notes</h1>
    <h2>Features</h2>
    <p>Feature list for 17.13 which was released on February 11, 2025.</p>
    <div><p>GitHub Copilot Free is now available in Visual Studio.</p></div>
    <h2>Version 17.13.1</h2>
    <p>Released February 19th, 2025</p>
    <div><p>Servicing fixes.</p></div>
</body>
</html>
"""

_FAKE_17_13_WITH_EXPLICIT_BASELINE_HTML = """\
<!DOCTYPE html>
<html>
<body>
    <h1>Visual Studio 2022 version 17.13 release notes</h1>
    <h2>Features</h2>
    <p>Feature list for 17.13 which was released on February 11, 2025.</p>
    <div><p>GitHub Copilot Free is now available in Visual Studio.</p></div>
    <h2>Version 17.13.0</h2>
    <p>Released February 11th, 2025</p>
    <div><p>Baseline section already present.</p></div>
    <h2>Version 17.13.1</h2>
    <p>Released February 19th, 2025</p>
    <div><p>Servicing fixes.</p></div>
</body>
</html>
"""

_FAKE_17_7_HTML = """\
<!DOCTYPE html>
<html>
<body>
  <h2>Visual Studio 2022 version 17.7.1</h2>
  <p>released Aug 15th, 2023</p>
  <div><p>Servicing fixes.</p></div>

  <h2>Visual Studio 2022 version 17.7</h2>
  <p>released Aug 8th, 2023</p>
  <div>
    <h3>Summary of What's New</h3>
    <p>Ask Copilot now helps explain analyzer warnings.</p>
  </div>
</body>
</html>
"""

_FAKE_17_10_RELEASE_HTML = """\
<!DOCTYPE html>
<html>
<body>
    <h1>Visual Studio 2022 version 17.10 Release Notes</h1>
    <h2>Visual Studio 2022 version 17.10 Releases</h2>
    <ul>
        <li>May 21st, 2024 - Visual Studio 2022 version 17.10.0</li>
    </ul>
    <h3>Visual Studio 2022 Blog</h3>
    <p>The Visual Studio 2022 Blog is the official source of product insight.</p>
    <ul>
        <li><a href="https://devblogs.microsoft.com/visualstudio/visual-studio-2022-17-10-now-available/">Visual Studio 2022 Version 17.10</a></li>
    </ul>

    <h2>Visual Studio 2022 version 17.10.21</h2>
    <p>released November 11th, 2025</p>
    <div><p>Servicing fixes for 17.10.21.</p></div>
</body>
</html>
"""

_FAKE_17_10_BLOG_HTML = """\
<!DOCTYPE html>
<html>
<head>
    <meta property="article:published_time" content="2024-05-21T15:30:16+00:00" />
</head>
<body>
    <h1>Visual Studio 2022 17.10 and GitHub Copilot</h1>
    <div class="entry-content">
        <p>Today we are thrilled to share the general availability of Visual Studio 2022 17.10.</p>
        <h3>Accelerating your coding experiences with GitHub Copilot</h3>
        <p>GitHub Copilot is integrated directly into Visual Studio.</p>
    </div>
</body>
</html>
"""


_FAKE_UNIFIED_HISTORY_HTML = """\
<!DOCTYPE html>
<html>
<body>
    <a href="release-notes">Visual Studio 2022 version 17.14 Release Notes</a>
    <table>
        <tr><th>Channel</th><th>Version</th><th>Release Date</th></tr>
        <tr><td>Current</td><td>17.14.32</td><td>May 12, 2026</td></tr>
        <tr><td>Current</td><td>17.14.0</td><td>May 13, 2025</td></tr>
    </table>
</body>
</html>
"""

_FAKE_UNIFIED_RELEASE_NOTES_HTML = """\
<!DOCTYPE html>
<html>
<body>
    <h1>Visual Studio release notes</h1>
    <h2>Features</h2>
    <p>Explore the latest enhancements in Visual Studio 2022 version 17.14.</p>
    <h3>IDE</h3>
    <p>GitHub Copilot now manages MCP authentication credentials in a unified experience.</p>
    <h2>Version 17.14.32</h2>
    <p>released May 12th, 2026</p>
    <div><p>Servicing fixes for 17.14.32.</p></div>
</body>
</html>
"""


class TestDiscoverReleaseNoteUrls:
    def test_filters_to_17_7_and_newer(self):
        urls = _discover_release_note_urls(
            _FAKE_HISTORY_HTML,
            history_url=_IDE_CONFIG["source_url"],
            start_minor="17.7",
        )

        assert urls == [
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes",
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes-v17.13",
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes-v17.7",
        ]

class TestFetch:
    def test_returns_release_notes_only(self):
        responses = {
            _IDE_CONFIG["source_url"]: _FAKE_HISTORY_HTML,
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes": _FAKE_17_14_HTML,
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes-v17.13": _FAKE_17_13_HTML,
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes-v17.7": _FAKE_17_7_HTML,
        }

        def fake_get_text(url: str, *, use_auth: bool, encoding: str | None = None) -> str:
            assert use_auth is False
            assert encoding == "utf-8"
            return responses[url]

        with patch("scripts.fetchers.visual_studio_2022.get_text", side_effect=fake_get_text):
            results = fetch(_IDE_CONFIG)

        versions = [record["version"] for record in results]
        assert versions == [
            "17.14.2",
            "17.14.1",
            "17.13.0",
            "17.13.1",
            "17.7.1",
            "17.7.0",
        ]

        by_version = {record["version"]: record for record in results}
        assert by_version["17.14.2"]["url"].endswith("release-notes")
        assert "prompt files" in by_version["17.14.2"]["body_markdown"].lower()
        assert "Happy coding!" not in by_version["17.14.1"]["body_markdown"]
        assert "3rd Party Notices" not in by_version["17.14.1"]["body_markdown"]
        assert "copilot free" in by_version["17.13.0"]["body_markdown"].lower()
        assert any("Copilot" in line for line in by_version["17.7.0"]["copilot_mentions"])

    def test_features_section_does_not_duplicate_explicit_baseline(self):
        responses = {
            _IDE_CONFIG["source_url"]: _FAKE_HISTORY_HTML,
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes": _FAKE_17_14_HTML,
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes-v17.13": _FAKE_17_13_WITH_EXPLICIT_BASELINE_HTML,
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes-v17.7": _FAKE_17_7_HTML,
        }

        def fake_get_text(url: str, *, use_auth: bool, encoding: str | None = None) -> str:
            assert use_auth is False
            assert encoding == "utf-8"
            return responses[url]

        with patch("scripts.fetchers.visual_studio_2022.get_text", side_effect=fake_get_text):
            results = fetch(_IDE_CONFIG)

        versions = [record["version"] for record in results if record["url"].endswith("release-notes-v17.13")]
        assert versions == ["17.13.0", "17.13.1"]

    def test_ingests_blog_content_for_legacy_baseline_release(self):
        responses = {
            _IDE_CONFIG["source_url"]: _FAKE_HISTORY_WITH_17_10_HTML,
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes-v17.10": _FAKE_17_10_RELEASE_HTML,
            "https://devblogs.microsoft.com/visualstudio/visual-studio-2022-17-10-now-available/": _FAKE_17_10_BLOG_HTML,
        }

        def fake_get_text(url: str, *, use_auth: bool, encoding: str | None = None) -> str:
            assert use_auth is False
            assert encoding == "utf-8"
            return responses[url]

        with patch("scripts.fetchers.visual_studio_2022.get_text", side_effect=fake_get_text):
            results = fetch(_IDE_CONFIG)

        versions = [record["version"] for record in results]
        assert versions == ["17.10.0", "17.10.21"]

        baseline = next(record for record in results if record["version"] == "17.10.0")
        assert baseline["release_date"] == "2024-05-21"
        assert baseline["title"] == "Visual Studio 2022 version 17.10.0"
        assert "general availability" in baseline["body_markdown"].lower()
        assert "github copilot" in baseline["body_markdown"].lower()

    def test_features_baseline_from_unified_page_without_minor_in_h1(self):
        responses = {
            _IDE_CONFIG["source_url"]: _FAKE_UNIFIED_HISTORY_HTML,
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes": _FAKE_UNIFIED_RELEASE_NOTES_HTML,
        }

        def fake_get_text(url: str, *, use_auth: bool, encoding: str | None = None) -> str:
            assert use_auth is False
            assert encoding == "utf-8"
            return responses[url]

        with patch("scripts.fetchers.visual_studio_2022.get_text", side_effect=fake_get_text):
            results = fetch(_IDE_CONFIG)

        versions = [record["version"] for record in results]
        assert versions == ["17.14.0", "17.14.32"]

        baseline = next(record for record in results if record["version"] == "17.14.0")
        assert baseline["release_date"] == "2025-05-13"
        assert baseline["title"] == "Version 17.14.0"
        assert "mcp authentication" in baseline["body_markdown"].lower()


class TestSchemaValidation:
    def test_records_pass_schema_validation(self):
        responses = {
            _IDE_CONFIG["source_url"]: _FAKE_HISTORY_HTML,
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes": _FAKE_17_14_HTML,
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes-v17.13": _FAKE_17_13_HTML,
            "https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes-v17.7": _FAKE_17_7_HTML,
        }

        def fake_get_text(url: str, *, use_auth: bool, encoding: str | None = None) -> str:
            assert use_auth is False
            assert encoding == "utf-8"
            return responses[url]

        schema = json.loads(pathlib.Path("scripts/common/schema.json").read_text())
        with patch("scripts.fetchers.visual_studio_2022.get_text", side_effect=fake_get_text):
            results = fetch(_IDE_CONFIG)

        for record in results:
            record["fetched_at"] = datetime.datetime.now(datetime.UTC).isoformat()
            record["schema_version"] = 1
            jsonschema.validate(record, schema)
