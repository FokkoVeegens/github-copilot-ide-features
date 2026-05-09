"""Vim/Neovim fetcher — copilot.vim releases + CHANGELOG sections."""
import re

from scripts.common.changelog import split_changelog_by_version
from scripts.common.extract import extract_copilot_mentions
from scripts.common.http import get_json, get_text

_RELEASES_API_URL = "https://api.github.com/repos/github/copilot.vim/releases"
_CHANGELOG_URL = "https://raw.githubusercontent.com/github/copilot.vim/refs/heads/release/CHANGELOG.md"
_TAG_VERSION_RE = re.compile(r"^v?(?P<version>\d+(?:\.\d+){2,3}(?:[-+][0-9A-Za-z.-]+)?)$")


def _parse_tag_version(tag: str) -> str:
    match = _TAG_VERSION_RE.match((tag or "").strip())
    if not match:
        raise ValueError(f"Unrecognised Vim/Neovim tag: {tag!r}")
    return match.group("version")


def _paginate_releases() -> list[dict]:
    releases: list[dict] = []
    page = 1
    while True:
        page_data = get_json(_RELEASES_API_URL, params={"per_page": 100, "page": page})
        if not page_data:
            break
        releases.extend(page_data)
        page += 1
    return releases


def fetch(ide_config: dict) -> list[dict]:
    changelog_url = ide_config.get("changelog_url", _CHANGELOG_URL)
    changelog_sections = split_changelog_by_version(get_text(changelog_url))
    raw_releases = _paginate_releases()
    results: list[dict] = []

    for item in raw_releases:
        tag_name: str = item.get("tag_name", "")
        try:
            version = _parse_tag_version(tag_name)
        except ValueError:
            print(f"  [warn] Skipping Vim/Neovim release with unexpected tag: {tag_name!r}")
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
                "title": item.get("name") or f"GitHub Copilot for Vim/Neovim {version}",
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
