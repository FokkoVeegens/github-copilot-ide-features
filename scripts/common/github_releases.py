"""Shared helpers for GitHub Releases based fetchers."""
import re
from typing import Callable

from scripts.common.changelog import split_changelog_by_version
from scripts.common.extract import extract_copilot_mentions

_TAG_VERSION_RE = re.compile(r"^v?(?P<version>\d+(?:\.\d+){2,3}(?:[-+][0-9A-Za-z.-]+)?)$")


def parse_tag_version(tag: str, *, error_label: str) -> str:
    """Parse a GitHub release tag (e.g. v1.2.3) into a version string."""
    match = _TAG_VERSION_RE.match((tag or "").strip())
    if not match:
        raise ValueError(f"Unrecognised {error_label} tag: {tag!r}")
    return match.group("version")


def paginate_github_releases(
    releases_api_url: str, *, get_json_fn: Callable[..., object]
) -> list[dict]:
    """Return all release entries from a paginated GitHub Releases endpoint."""
    releases: list[dict] = []
    page = 1
    while True:
        page_data = get_json_fn(releases_api_url, params={"per_page": 100, "page": page})
        if not isinstance(page_data, list):
            raise ValueError(
                f"Expected list from GitHub releases API at page {page}, got {type(page_data).__name__}"
            )
        if not page_data:
            break
        releases.extend(page_data)
        page += 1
    return releases


def map_releases_with_changelog(
    *,
    ide_config: dict,
    raw_releases: list[dict],
    changelog_url: str,
    parse_tag_version_fn: Callable[[str], str],
    warning_label: str,
    default_title_prefix: str,
    get_text_fn: Callable[..., str],
) -> list[dict]:
    """Map GitHub releases to schema release records, preferring CHANGELOG sections."""
    changelog_sections = split_changelog_by_version(get_text_fn(changelog_url))
    results: list[dict] = []

    for item in raw_releases:
        tag_name: str = item.get("tag_name", "")
        try:
            version = parse_tag_version_fn(tag_name)
        except ValueError:
            print(f"  [warn] Skipping {warning_label} release with unexpected tag: {tag_name!r}")
            continue

        changelog_body = changelog_sections.get(version, "").strip()
        api_body = (item.get("body") or "").strip()
        is_fallback = not changelog_body
        body_markdown = api_body if is_fallback else changelog_body
        source = "api_fallback" if is_fallback else "api"

        published_at = item.get("published_at") or item.get("created_at") or ""
        release_date = published_at[:10] if len(published_at) >= 10 else "1970-01-01"

        results.append(
            {
                "ide": ide_config["id"],
                "version": version,
                "release_date": release_date,
                "title": item.get("name") or f"{default_title_prefix} {version}",
                "url": item.get("html_url", ""),
                "source": source,
                "body_markdown": body_markdown,
                "body_html": None,
                "categories": [],
                "copilot_mentions": extract_copilot_mentions(body_markdown),
                "prerelease": bool(item.get("prerelease", False)),
            }
        )

    return results
