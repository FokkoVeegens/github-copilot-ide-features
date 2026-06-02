"""GitHub Copilot CLI fetcher — GitHub Releases API."""

from scripts.common.extract import extract_copilot_mentions
from scripts.common.github_releases import paginate_github_releases, parse_tag_version
from scripts.common.http import get_json

_DEFAULT_RELEASES_API_URL = "https://api.github.com/repos/github/copilot-cli/releases"


def fetch(ide_config: dict) -> list[dict]:
    """Fetch GitHub Copilot CLI releases and map them to release records."""
    releases_api_url = ide_config.get("source_url", _DEFAULT_RELEASES_API_URL)
    raw_releases = paginate_github_releases(releases_api_url, get_json_fn=get_json)
    results: list[dict] = []

    for item in raw_releases:
        tag_name: str = item.get("tag_name", "")
        try:
            version = parse_tag_version(tag_name, error_label="Copilot CLI")
        except ValueError:
            print(f"  [warn] Skipping Copilot CLI release with unexpected tag: {tag_name!r}")
            continue

        body_markdown = (item.get("body") or "").strip()
        published_at = item.get("published_at") or item.get("created_at") or ""
        release_date = published_at[:10] if len(published_at) >= 10 else "1970-01-01"

        results.append(
            {
                "ide": ide_config["id"],
                "version": version,
                "release_date": release_date,
                "title": item.get("name") or f"GitHub Copilot CLI {version}",
                "url": item.get("html_url", ""),
                "source": "api",
                "body_markdown": body_markdown,
                "body_html": None,
                "categories": [],
                "copilot_mentions": extract_copilot_mentions(body_markdown),
                "prerelease": bool(item.get("prerelease", False)),
            }
        )

    return results
