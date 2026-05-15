"""Visual Studio 2022 release-notes fetcher."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag
from packaging.version import Version

from scripts.common.config import require_config_value
from scripts.common.extract import extract_copilot_mentions, html_to_markdown
from scripts.common.html_split import split_version_sections
from scripts.common.http import get_text

_RELEASE_NOTE_LINK_RE = re.compile(
    r"Visual Studio 2022 version (?P<minor>17\.\d+) Release Notes",
    re.IGNORECASE,
)
_RELEASE_SECTION_VERSION_RE = (
    r"^(?:Version|Visual Studio 2022 version)\s+(?P<version>17\.\d+(?:\.\d+)?)$"
)
_RELEASE_SECTION_DATE_RE = (
    r"released(?:\s+on)?\s+(?P<date>[A-Za-z]+\s+\d{1,2}(?:\s*(?:st|nd|rd|th))?\s*,?\s+\d{4})"
)
_FOOTER_TEXT_SNIPPETS = (
    "thank you for choosing visual studio",
    "visual studio hub",
    "happy coding!",
    "3rd party notices",
    "licensed separately",
)


def fetch(ide_config: dict) -> list[dict]:
    history_url = require_config_value(ide_config, "source_url")
    start_minor = ide_config.get("start_version", "17.7")
    history_html = get_text(history_url, use_auth=False, encoding="utf-8")

    return _fetch_release_note_records(
        ide_config,
        history_html,
        history_url=history_url,
        start_minor=start_minor,
    )


def _fetch_release_note_records(
    ide_config: dict,
    history_html: str,
    *,
    history_url: str,
    start_minor: str,
) -> list[dict]:
    results: list[dict] = []
    for release_url in _discover_release_note_urls(history_html, history_url=history_url, start_minor=start_minor):
        page_html = get_text(release_url, use_auth=False, encoding="utf-8")
        sections = split_version_sections(
            page_html,
            heading_tags=("h2",),
            version_pattern=_RELEASE_SECTION_VERSION_RE,
            date_pattern=_RELEASE_SECTION_DATE_RE,
        )
        for section in sections:
            body_html = _trim_release_section_html(section["body_html"])
            body_markdown = html_to_markdown(body_html)
            results.append(
                {
                    "ide": ide_config["id"],
                    "version": section["version"],
                    "release_date": section["release_date"],
                    "title": section["title"],
                    "url": release_url,
                    "source": "html",
                    "body_markdown": body_markdown,
                    "body_html": body_html,
                    "categories": [],
                    "copilot_mentions": extract_copilot_mentions(body_markdown),
                }
            )
    return results


def _trim_release_section_html(body_html: str) -> str:
    soup = BeautifulSoup(f"<div>{body_html}</div>", "lxml")
    container = soup.div
    if container is None:
        return body_html

    stripped_footer = False
    for child in reversed(list(container.contents)):
        if _is_whitespace_node(child):
            child.extract()
            continue
        if _is_footer_node(child):
            stripped_footer = True
            child.extract()
            continue
        if stripped_footer and isinstance(child, Tag) and child.name == "hr":
            child.extract()
            continue
        break

    if container.contents:
        last_child = container.contents[-1]
        if isinstance(last_child, Tag) and last_child.name == "hr":
            last_child.extract()

    return "".join(str(child) for child in container.contents).strip()


def _is_whitespace_node(node: Tag | NavigableString) -> bool:
    return isinstance(node, NavigableString) and not node.strip()


def _is_footer_node(node: Tag | NavigableString) -> bool:
    if isinstance(node, NavigableString):
        return False

    text = node.get_text(" ", strip=True).lower()
    if not text:
        return False
    return any(snippet in text for snippet in _FOOTER_TEXT_SNIPPETS)


def _discover_release_note_urls(
    history_html: str,
    *,
    history_url: str,
    start_minor: str,
) -> list[str]:
    soup = BeautifulSoup(history_html, "lxml")
    urls: list[str] = []
    for link in soup.find_all("a", href=True):
        match = _RELEASE_NOTE_LINK_RE.fullmatch(link.get_text(" ", strip=True))
        if match is None:
            continue
        minor = match.group("minor")
        if Version(minor) < Version(start_minor):
            continue
        urls.append(urljoin(history_url, link["href"]))
    return list(dict.fromkeys(urls))
