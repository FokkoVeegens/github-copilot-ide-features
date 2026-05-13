"""VS Code fetcher — release notes via Atom feed + per-version page scrape.

Source:
  Feed (latest ~30 entries): https://code.visualstudio.com/feed.xml
  Per-version page          : https://code.visualstudio.com/updates/v1_<N>

The feed is used only to discover the latest minor version N.  All versions
from start_version up to (and including) the latest are then fetched by
constructing the URL directly, so a full backfill is possible even when older
entries have aged out of the feed.

Version scheme: 1.<N>.0  (e.g. v1_75 → version "1.75.0")
"""

import json
import re
from datetime import datetime

import feedparser
from bs4 import BeautifulSoup

from scripts.common.config import require_config_value
from scripts.common.extract import extract_copilot_mentions, html_to_markdown
from scripts.common.http import get_text

# Matches the minor version in VS Code release-notes URLs (/updates/v1_75).
_RELEASE_URL_RE = re.compile(r"/updates/v1_(\d+)")


def _parse_minor_from_start_version(start_version: str) -> int:
    """Return the minor part of a version string like '1.75.0' or '1.75'."""
    parts = start_version.split(".")
    if len(parts) < 2:
        raise ValueError(f"Cannot extract minor version from start_version: {start_version!r}")
    return int(parts[1])


def _parse_feed(feed_xml: str) -> tuple[int, dict[int, str]]:
    """Parse the Atom feed XML and return (latest_minor, {minor: date}).

    Only entries whose tags include ``release`` and whose link matches the
    ``/updates/v1_N`` pattern are considered.  Blog or other entries are
    silently skipped.

    Returns:
        latest_minor: the highest minor N found in the feed.
        feed_dates:   mapping of minor → ISO-8601 date string (YYYY-MM-DD).

    Raises:
        ValueError: when no release entries are found in the feed.
    """
    parsed = feedparser.parse(feed_xml)
    feed_dates: dict[int, str] = {}

    for entry in parsed.entries:
        tags = [t.get("term", "") for t in getattr(entry, "tags", [])]
        if "release" not in tags:
            continue
        link = entry.get("link", "")
        m = _RELEASE_URL_RE.search(link)
        if not m:
            continue
        minor = int(m.group(1))
        date_struct = (
            getattr(entry, "published_parsed", None)
            or getattr(entry, "updated_parsed", None)
        )
        if date_struct:
            feed_dates[minor] = datetime(*date_struct[:3]).strftime("%Y-%m-%d")

    if not feed_dates:
        raise ValueError("No release entries found in the VS Code Atom feed.")

    return max(feed_dates.keys()), feed_dates


def _extract_date_from_html(html: str) -> str | None:
    """Try to extract an ISO-8601 date from VS Code release-notes HTML.

    Checks (in order):
    1. JSON-LD ``<script type="application/ld+json">`` with a ``datePublished`` key.
    2. ``<meta property="article:published_time">`` tag.
    """
    soup = BeautifulSoup(html, "lxml")

    # 1. JSON-LD structured data (most reliable)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, AttributeError):
            continue
        if isinstance(data, dict):
            date_str = data.get("datePublished") or data.get("dateModified")
            if date_str:
                return str(date_str)[:10]

    # 2. Open Graph / article meta tag
    meta = soup.find("meta", attrs={"property": "article:published_time"})
    if meta and meta.get("content"):
        return str(meta["content"])[:10]

    return None


def fetch(ide_config: dict) -> list[dict]:
    """Fetch all VS Code release notes from start_version to the latest.

    For each minor version N in [start_minor, latest_minor]:
    - Fetch ``https://code.visualstudio.com/updates/v1_N``.
    - Extract ``<main>`` content and convert to Markdown.
    - Determine the release date (feed first, then HTML meta, then skip gracefully).

    Returns a list of release dicts conforming to the shared JSON schema.
    Pages that return an HTTP error are warned about and skipped.
    """
    feed_url = require_config_value(ide_config, "source_url")
    release_url_template = require_config_value(ide_config, "release_url_template")
    start_version = require_config_value(ide_config, "start_version")
    start_minor = _parse_minor_from_start_version(start_version)

    feed_xml = get_text(feed_url, use_auth=False)
    latest_minor, feed_dates = _parse_feed(feed_xml)

    results: list[dict] = []
    for n in range(start_minor, latest_minor + 1):
        version = f"1.{n}.0"
        page_url = release_url_template.format(n=n)

        try:
            html = get_text(page_url, use_auth=False)
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] Failed to fetch {page_url}: {exc}")
            continue

        # Extract <main> for body content (falls back to full body if absent).
        soup = BeautifulSoup(html, "lxml")
        main_tag = soup.find("main") or soup.find("article") or soup.body
        body_html = str(main_tag) if main_tag else html

        # Release date: feed (for recent entries) → HTML meta → skip with warning.
        release_date: str | None = feed_dates.get(n) or _extract_date_from_html(html)
        if not release_date:
            print(f"  [warn] Could not determine release_date for {version}; skipping.")
            continue

        body_markdown = html_to_markdown(body_html)
        copilot_mentions = extract_copilot_mentions(body_markdown)

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else f"VS Code {version}"

        results.append(
            {
                "ide": ide_config["id"],
                "version": version,
                "release_date": release_date,
                "title": title,
                "url": page_url,
                "source": "feed",
                "body_markdown": body_markdown,
                "body_html": body_html,
                "categories": [],
                "copilot_mentions": copilot_mentions,
            }
        )

    return results
