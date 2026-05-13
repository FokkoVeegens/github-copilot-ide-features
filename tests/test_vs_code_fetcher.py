"""Tests for scripts/fetchers/vs_code.py"""
from unittest.mock import patch

import pytest

from scripts.fetchers.vs_code import (
    _extract_date_from_html,
    _parse_feed,
    _parse_minor_from_start_version,
    fetch,
)

_IDE_CONFIG = {
    "id": "vs-code",
    "name": "GitHub Copilot for VS Code",
    "data_dir": "data/vs-code",
    "fetcher": "vs_code",
    "start_version": "1.75.0",
    "source_url": "https://code.visualstudio.com/feed.xml",
    "release_url_template": "https://code.visualstudio.com/updates/v1_{n}",
}

# Minimal Atom feed XML with two release entries and one blog entry.
# Uses <updated> (not <published>) to match the real VS Code feed format.
_FAKE_FEED_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Visual Studio Code</title>
  <entry>
    <title>VS Code 1.76</title>
    <link rel="alternate" href="https://code.visualstudio.com/updates/v1_76"/>
    <category term="release"/>
    <updated>2023-03-01T00:00:00Z</updated>
  </entry>
  <entry>
    <title>VS Code 1.75</title>
    <link rel="alternate" href="https://code.visualstudio.com/updates/v1_75"/>
    <category term="release"/>
    <updated>2023-02-01T00:00:00Z</updated>
  </entry>
  <entry>
    <title>A blog post</title>
    <link rel="alternate" href="https://code.visualstudio.com/blogs/2023/02/15/some-post"/>
    <category term="blog"/>
    <updated>2023-02-15T00:00:00Z</updated>
  </entry>
</feed>
"""

# Minimal HTML for a VS Code release-notes page with JSON-LD date.
_FAKE_PAGE_HTML_76 = """\
<!DOCTYPE html>
<html>
<head>
  <title>Visual Studio Code February 2023</title>
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"Article","datePublished":"2023-03-01","headline":"Visual Studio Code March 2023"}
  </script>
</head>
<body>
  <main>
    <h1>Visual Studio Code March 2023</h1>
    <p>GitHub Copilot inline chat is now available.</p>
  </main>
</body>
</html>
"""

# Minimal HTML for a page that uses <meta property="article:published_time">.
_FAKE_PAGE_HTML_75 = """\
<!DOCTYPE html>
<html>
<head>
  <title>Visual Studio Code January 2023</title>
  <meta property="article:published_time" content="2023-02-01T00:00:00Z"/>
</head>
<body>
  <main>
    <h1>Visual Studio Code February 2023</h1>
    <p>Copilot suggestions are faster in this release.</p>
  </main>
</body>
</html>
"""

# HTML with no date information at all.
_FAKE_PAGE_HTML_NO_DATE = """\
<!DOCTYPE html>
<html>
<head><title>Some page</title></head>
<body><main><p>Content here, no AI mentions.</p></main></body>
</html>
"""


class TestParseMinorFromStartVersion:
    def test_three_part_version(self):
        assert _parse_minor_from_start_version("1.75.0") == 75

    def test_two_part_version(self):
        assert _parse_minor_from_start_version("1.90") == 90

    def test_large_minor(self):
        assert _parse_minor_from_start_version("1.100.0") == 100

    def test_invalid_single_part_raises(self):
        with pytest.raises(ValueError, match="Cannot extract minor"):
            _parse_minor_from_start_version("1")


class TestParseFeed:
    def test_returns_latest_minor(self):
        latest_minor, _ = _parse_feed(_FAKE_FEED_XML)
        assert latest_minor == 76

    def test_returns_feed_dates(self):
        _, feed_dates = _parse_feed(_FAKE_FEED_XML)
        assert 75 in feed_dates
        assert 76 in feed_dates
        assert feed_dates[75] == "2023-02-01"
        assert feed_dates[76] == "2023-03-01"

    def test_blog_entries_are_excluded(self):
        _, feed_dates = _parse_feed(_FAKE_FEED_XML)
        # No entry for a blog URL should appear (blog entry has no /updates/v1_N link)
        assert len(feed_dates) == 2

    def test_no_release_entries_raises(self):
        blog_only_feed = """\
<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <link href="https://code.visualstudio.com/blog/2023/01/01/some-blog"/>
    <category term="blog"/>
    <updated>2023-01-01T00:00:00Z</updated>
  </entry>
</feed>
"""
        with pytest.raises(ValueError, match="No release entries found"):
            _parse_feed(blog_only_feed)

    def test_updated_field_used_when_no_published(self):
        """Feed entries that only have <updated> (no <published>) still yield a date."""
        feed_with_updated_only = """\
<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <link rel="alternate" href="https://code.visualstudio.com/updates/v1_80"/>
    <category term="release"/>
    <updated>2023-08-01T00:00:00Z</updated>
  </entry>
</feed>
"""
        latest, dates = _parse_feed(feed_with_updated_only)
        assert latest == 80
        assert dates[80] == "2023-08-01"


class TestExtractDateFromHtml:
    def test_json_ld_date(self):
        assert _extract_date_from_html(_FAKE_PAGE_HTML_76) == "2023-03-01"

    def test_meta_article_published_time(self):
        assert _extract_date_from_html(_FAKE_PAGE_HTML_75) == "2023-02-01"

    def test_returns_none_when_no_date(self):
        assert _extract_date_from_html(_FAKE_PAGE_HTML_NO_DATE) is None

    def test_json_ld_date_truncated_to_10_chars(self):
        html = """\
<html><head>
<script type="application/ld+json">{"datePublished": "2023-03-01T12:00:00Z"}</script>
</head><body></body></html>"""
        assert _extract_date_from_html(html) == "2023-03-01"


class TestFetch:
    def _make_get_text_side_effect(self, pages: dict[str, str]):
        """Return a side-effect function that dispatches by URL."""
        def side_effect(url, *, use_auth=True):
            if url not in pages:
                raise ValueError(f"Unexpected URL in test: {url}")
            return pages[url]
        return side_effect

    def test_returns_one_record_per_version_in_range(self):
        pages = {
            "https://code.visualstudio.com/feed.xml": _FAKE_FEED_XML,
            "https://code.visualstudio.com/updates/v1_75": _FAKE_PAGE_HTML_75,
            "https://code.visualstudio.com/updates/v1_76": _FAKE_PAGE_HTML_76,
        }
        with patch("scripts.fetchers.vs_code.get_text", side_effect=self._make_get_text_side_effect(pages)):
            results = fetch(_IDE_CONFIG)

        assert len(results) == 2
        versions = {r["version"] for r in results}
        assert versions == {"1.75.0", "1.76.0"}

    def test_record_fields_are_populated(self):
        pages = {
            "https://code.visualstudio.com/feed.xml": _FAKE_FEED_XML,
            "https://code.visualstudio.com/updates/v1_75": _FAKE_PAGE_HTML_75,
            "https://code.visualstudio.com/updates/v1_76": _FAKE_PAGE_HTML_76,
        }
        with patch("scripts.fetchers.vs_code.get_text", side_effect=self._make_get_text_side_effect(pages)):
            results = fetch(_IDE_CONFIG)

        r75 = next(r for r in results if r["version"] == "1.75.0")
        assert r75["ide"] == "vs-code"
        assert r75["release_date"] == "2023-02-01"
        assert r75["url"] == "https://code.visualstudio.com/updates/v1_75"
        assert r75["source"] == "feed"
        assert r75["title"] == "Visual Studio Code January 2023"
        assert r75["body_markdown"] != ""
        assert isinstance(r75["categories"], list)
        assert isinstance(r75["copilot_mentions"], list)

    def test_copilot_mentions_populated(self):
        pages = {
            "https://code.visualstudio.com/feed.xml": _FAKE_FEED_XML,
            "https://code.visualstudio.com/updates/v1_75": _FAKE_PAGE_HTML_75,
            "https://code.visualstudio.com/updates/v1_76": _FAKE_PAGE_HTML_76,
        }
        with patch("scripts.fetchers.vs_code.get_text", side_effect=self._make_get_text_side_effect(pages)):
            results = fetch(_IDE_CONFIG)

        # Both pages reference Copilot in body text.
        for r in results:
            assert len(r["copilot_mentions"]) > 0, f"No copilot_mentions for {r['version']}"

    def test_feed_date_used_for_recent_versions(self):
        """Versions present in the feed get their date from the feed, not the page."""
        pages = {
            "https://code.visualstudio.com/feed.xml": _FAKE_FEED_XML,
            "https://code.visualstudio.com/updates/v1_75": _FAKE_PAGE_HTML_75,
            "https://code.visualstudio.com/updates/v1_76": _FAKE_PAGE_HTML_76,
        }
        with patch("scripts.fetchers.vs_code.get_text", side_effect=self._make_get_text_side_effect(pages)):
            results = fetch(_IDE_CONFIG)

        r76 = next(r for r in results if r["version"] == "1.76.0")
        # Feed date is 2023-03-01; page JSON-LD also says 2023-03-01 for this test.
        assert r76["release_date"] == "2023-03-01"

    def test_page_with_no_date_is_skipped(self):
        """Versions where neither feed nor HTML yields a date are skipped."""
        feed_xml_no_date = """\
<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <link rel="alternate" href="https://code.visualstudio.com/updates/v1_76"/>
    <category term="release"/>
    <updated>2023-03-01T00:00:00Z</updated>
  </entry>
</feed>
"""
        pages = {
            "https://code.visualstudio.com/feed.xml": feed_xml_no_date,
            "https://code.visualstudio.com/updates/v1_75": _FAKE_PAGE_HTML_NO_DATE,
            "https://code.visualstudio.com/updates/v1_76": _FAKE_PAGE_HTML_76,
        }
        with patch("scripts.fetchers.vs_code.get_text", side_effect=self._make_get_text_side_effect(pages)):
            results = fetch(_IDE_CONFIG)

        # v1_75 has no date in feed and no date in HTML → skipped.
        versions = {r["version"] for r in results}
        assert "1.75.0" not in versions
        assert "1.76.0" in versions

    def test_http_error_skips_version(self):
        """Pages that raise HTTP errors are skipped with a warning."""
        def side_effect(url, *, use_auth=True):
            if "feed.xml" in url:
                return _FAKE_FEED_XML
            if "v1_75" in url:
                raise Exception("HTTP 404")
            return _FAKE_PAGE_HTML_76

        with patch("scripts.fetchers.vs_code.get_text", side_effect=side_effect):
            results = fetch(_IDE_CONFIG)

        versions = {r["version"] for r in results}
        assert "1.75.0" not in versions
        assert "1.76.0" in versions

    def test_uses_custom_source_url(self):
        """fetch() uses ide_config source_url instead of the default."""
        custom_config = {**_IDE_CONFIG, "source_url": "https://custom.example.com/feed.xml"}
        pages = {
            "https://custom.example.com/feed.xml": _FAKE_FEED_XML,
            "https://code.visualstudio.com/updates/v1_75": _FAKE_PAGE_HTML_75,
            "https://code.visualstudio.com/updates/v1_76": _FAKE_PAGE_HTML_76,
        }
        with patch("scripts.fetchers.vs_code.get_text", side_effect=self._make_get_text_side_effect(pages)):
            results = fetch(custom_config)

        assert len(results) == 2

    def test_uses_custom_release_url_template(self):
        custom_config = {
            **_IDE_CONFIG,
            "release_url_template": "https://custom.example.com/updates/v1_{n}",
        }
        pages = {
            "https://code.visualstudio.com/feed.xml": _FAKE_FEED_XML,
            "https://custom.example.com/updates/v1_75": _FAKE_PAGE_HTML_75,
            "https://custom.example.com/updates/v1_76": _FAKE_PAGE_HTML_76,
        }
        with patch("scripts.fetchers.vs_code.get_text", side_effect=self._make_get_text_side_effect(pages)):
            results = fetch(custom_config)

        assert len(results) == 2

    def test_missing_release_url_template_raises(self):
        config = dict(_IDE_CONFIG)
        config.pop("release_url_template")
        with pytest.raises(ValueError, match="missing required config value 'release_url_template'"):
            fetch(config)

    def test_start_version_respected(self):
        """Only versions >= start_version are fetched."""
        config_76_start = {**_IDE_CONFIG, "start_version": "1.76.0"}
        pages = {
            "https://code.visualstudio.com/feed.xml": _FAKE_FEED_XML,
            "https://code.visualstudio.com/updates/v1_76": _FAKE_PAGE_HTML_76,
        }
        with patch("scripts.fetchers.vs_code.get_text", side_effect=self._make_get_text_side_effect(pages)):
            results = fetch(config_76_start)

        assert len(results) == 1
        assert results[0]["version"] == "1.76.0"
