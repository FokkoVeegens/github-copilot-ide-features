"""Eclipse fetcher — Microsoft Copilot for Eclipse via GitHub Releases API.

Source: https://api.github.com/repos/microsoft/copilot-for-eclipse/releases
Title format: "0.16.0 - 20260403"  →  version=0.16.0, release_date=2026-04-03
"""
import re

from scripts.common.config import require_config_value
from scripts.common.extract import extract_copilot_mentions, html_to_markdown
from scripts.common.github_releases import paginate_github_releases
from scripts.common.http import get_json

_TITLE_RE = re.compile(r"^(?P<version>\d+\.\d+\.\d+)\s*-\s*(?P<date>\d{8})$")


def _parse_title(title: str) -> tuple[str, str]:
    """Return (version, release_date) from a title like '0.16.0 - 20260403'."""
    m = _TITLE_RE.match(title.strip())
    if not m:
        raise ValueError(f"Unrecognised Eclipse release title: {title!r}")
    raw_date = m.group("date")  # "20260403"
    release_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
    return m.group("version"), release_date


def fetch(ide_config: dict) -> list[dict]:
    """Fetch all Copilot for Eclipse releases and return a list of release dicts."""
    releases_api_url = require_config_value(ide_config, "source_url")
    raw_releases = paginate_github_releases(releases_api_url, get_json_fn=get_json)
    results: list[dict] = []

    for item in raw_releases:
        title: str = item.get("name") or item.get("tag_name", "")
        try:
            version, release_date = _parse_title(title)
        except ValueError:
            # Skip releases whose title doesn't match the expected pattern
            print(f"  [warn] Skipping Eclipse release with unexpected title: {title!r}")
            continue

        body_html: str = item.get("body") or ""
        body_markdown = html_to_markdown(body_html) if body_html else ""
        copilot_mentions = extract_copilot_mentions(body_markdown)

        html_url: str = item.get("html_url", "")

        results.append(
            {
                "ide": ide_config["id"],
                "version": version,
                "release_date": release_date,
                "title": title,
                "url": html_url,
                "source": "api",
                "body_markdown": body_markdown,
                "body_html": body_html,
                "categories": [],
                "copilot_mentions": copilot_mentions,
            }
        )

    return results
