"""SQL Server Management Studio release-notes fetcher for learn.microsoft.com HTML pages."""

from __future__ import annotations

from packaging.version import Version

from scripts.common.extract import extract_copilot_mentions, html_to_markdown
from scripts.common.html_split import split_version_sections
from scripts.common.http import get_text


def _is_at_or_above_start_version(version: str, start_version: str | None) -> bool:
    if not start_version or start_version == "all":
        return True
    return Version(version) >= Version(start_version)


def _source_urls(ide_config: dict) -> list[str]:
    urls = ide_config.get("source_urls")
    if isinstance(urls, list) and urls:
        return urls
    raise ValueError("missing required config value 'source_urls'")


def fetch(ide_config: dict) -> list[dict]:
    """Fetch SSMS release notes from SSMS 22 and SSMS 21 pages."""
    start_version = ide_config.get("start_version")
    results: list[dict] = []

    for source_url in _source_urls(ide_config):
        html = get_text(source_url, use_auth=False, encoding="utf-8")
        sections = split_version_sections(
            html,
            heading_tags=("h3",),
            version_pattern=r"^(?:Version\s+)?(?P<version>\d+\.\d+\.\d+)$",
            date_pattern=r"Release date:\s*(?P<date>[A-Za-z]+\s+\d{1,2}(?:\s*(?:st|nd|rd|th))?,?\s+\d{4})",
        )

        for section in sections:
            version = section["version"]
            if not _is_at_or_above_start_version(version, start_version):
                continue

            body_html = section["body_html"]
            body_markdown = html_to_markdown(body_html)
            results.append(
                {
                    "ide": ide_config["id"],
                    "version": version,
                    "release_date": section["release_date"],
                    "title": section["title"],
                    "url": source_url,
                    "source": "html",
                    "body_markdown": body_markdown,
                    "body_html": body_html,
                    "categories": [],
                    "copilot_mentions": extract_copilot_mentions(body_markdown),
                }
            )

    return results
