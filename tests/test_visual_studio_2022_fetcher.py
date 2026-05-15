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
  <h2>Version 17.13.0</h2>
  <p>Released February 11th, 2025</p>
  <div><p>GitHub Copilot Free is now available in Visual Studio.</p></div>
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
            "17.7.1",
            "17.7",
        ]

        by_version = {record["version"]: record for record in results}
        assert by_version["17.14.2"]["url"].endswith("release-notes")
        assert "prompt files" in by_version["17.14.2"]["body_markdown"].lower()
        assert "Happy coding!" not in by_version["17.14.1"]["body_markdown"]
        assert "3rd Party Notices" not in by_version["17.14.1"]["body_markdown"]
        assert any("Copilot" in line for line in by_version["17.7"]["copilot_mentions"])


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
