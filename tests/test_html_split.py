"""Tests for scripts/common/html_split.py."""

import pytest

from scripts.common.html_split import normalize_human_date, split_version_sections

_FAKE_HTML = """\
<html>
<body>
  <h2>Version 17.14.31</h2>
    <p>Released on April 21th, 2026.</p>
  <div><h3>Highlights</h3><p>GitHub Copilot chat improvements.</p></div>
  <h2>Version 17.14.1</h2>
    <p>Released on January 15th, 2026.</p>
  <div><p>Servicing fixes.</p></div>
</body>
</html>
"""


class TestNormalizeHumanDate:
    def test_strips_ordinal_suffixes(self):
        assert normalize_human_date("April 21st, 2026") == "2026-04-21"

    def test_handles_typo_like_21th(self):
        assert normalize_human_date("April 21th, 2026") == "2026-04-21"

    def test_handles_abbreviated_month_without_comma(self):
        assert normalize_human_date("Nov 14th 2023") == "2023-11-14"

    def test_handles_split_ordinal_suffix(self):
        assert normalize_human_date("May 13 th , 2025") == "2025-05-13"

    def test_handles_common_month_typo(self):
        assert normalize_human_date("Novemeber 12th, 2024") == "2024-11-12"


class TestSplitVersionSections:
    def test_returns_one_section_per_matching_heading(self):
        sections = split_version_sections(
            _FAKE_HTML,
            heading_tags=("h2",),
            version_pattern=r"^Version\s+(?P<version>\d+\.\d+\.\d+)$",
            date_pattern=r"Released(?:\s+on)?\s+(?P<date>[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4})",
        )
        assert [section["version"] for section in sections] == ["17.14.31", "17.14.1"]

    def test_keeps_nested_content_inside_section_body(self):
        sections = split_version_sections(
            _FAKE_HTML,
            heading_tags=("h2",),
            version_pattern=r"^Version\s+(?P<version>\d+\.\d+\.\d+)$",
            date_pattern=r"Released(?:\s+on)?\s+(?P<date>[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4})",
        )
        assert "GitHub Copilot chat improvements." in sections[0]["body_html"]
        assert "Servicing fixes." not in sections[0]["body_html"]

    def test_raises_when_date_missing(self):
        html = "<html><body><h2>Version 17.14.31</h2><p>No date here</p></body></html>"
        with pytest.raises(ValueError, match="Could not find release date"):
            split_version_sections(
                html,
                heading_tags=("h2",),
                version_pattern=r"^Version\s+(?P<version>\d+\.\d+\.\d+)$",
                date_pattern=r"Released(?:\s+on)?\s+(?P<date>[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4})",
            )
