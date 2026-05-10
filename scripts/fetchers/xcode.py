"""Xcode fetcher — GitHub Copilot for Xcode releases + CHANGELOG sections."""
from scripts.common.github_releases import (
    map_releases_with_changelog,
    paginate_github_releases,
    parse_tag_version,
)
from scripts.common.http import get_json, get_text

_RELEASES_API_URL = "https://api.github.com/repos/github/CopilotForXcode/releases"
_CHANGELOG_URL = "https://raw.githubusercontent.com/github/CopilotForXcode/refs/heads/main/CHANGELOG.md"

def fetch(ide_config: dict) -> list[dict]:
    changelog_url = ide_config.get("changelog_url", _CHANGELOG_URL)
    raw_releases = paginate_github_releases(_RELEASES_API_URL, get_json_fn=get_json)
    return map_releases_with_changelog(
        ide_config=ide_config,
        raw_releases=raw_releases,
        changelog_url=changelog_url,
        parse_tag_version_fn=lambda tag: parse_tag_version(tag, error_label="Xcode"),
        warning_label="Xcode",
        default_title_prefix="GitHub Copilot for Xcode",
        get_text_fn=get_text,
    )
