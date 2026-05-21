"""Visual Studio 2022 release-notes fetcher."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag
from packaging.version import Version

from scripts.common.config import require_config_value
from scripts.common.extract import extract_copilot_mentions, html_to_markdown
from scripts.common.html_split import normalize_human_date, split_version_sections
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
_PAGE_TITLE_MINOR_RE = re.compile(
    r"Visual Studio 2022 version (?P<minor>17\.\d+) release notes",
    re.IGNORECASE,
)
_BLOG_HEADING_RE = re.compile(r"visual studio 2022 blog", re.IGNORECASE)
_DEVBLOG_URL_RE = re.compile(r"https?://devblogs\.microsoft\.com/visualstudio/", re.IGNORECASE)
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
    history_dates = _extract_history_release_dates(history_html)
    results: list[dict] = []
    for release_url in _discover_release_note_urls(history_html, history_url=history_url, start_minor=start_minor):
        page_html = get_text(release_url, use_auth=False, encoding="utf-8")
        sections = split_version_sections(
            page_html,
            heading_tags=("h2",),
            version_pattern=_RELEASE_SECTION_VERSION_RE,
            date_pattern=_RELEASE_SECTION_DATE_RE,
        )

        discovered_versions = {section["version"] for section in sections}
        minor = _extract_page_minor(page_html, sections=sections)
        major_section = _extract_major_release_section(
            page_html,
            release_url=release_url,
            minor=minor,
            history_dates=history_dates,
        )
        if major_section is not None and not _has_baseline_version(discovered_versions, minor=minor):
            body_html = _trim_release_section_html(major_section["body_html"])
            body_markdown = html_to_markdown(body_html)
            results.append(
                {
                    "ide": ide_config["id"],
                    "version": major_section["version"],
                    "release_date": major_section["release_date"],
                    "title": major_section["title"],
                    "url": release_url,
                    "source": "html",
                    "body_markdown": body_markdown,
                    "body_html": body_html,
                    "categories": [],
                    "copilot_mentions": extract_copilot_mentions(body_markdown),
                }
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


def _extract_major_release_section(
    page_html: str,
    *,
    release_url: str,
    minor: str | None,
    history_dates: dict[str, str] | None = None,
) -> dict[str, str] | None:
    if minor is None:
        return None

    fallback_date = (history_dates or {}).get(f"{minor}.0")
    features_section = _extract_major_features_section(
        page_html, minor=minor, fallback_date=fallback_date
    )
    if features_section is not None:
        return features_section

    return _extract_major_blog_section(page_html, release_url=release_url, minor=minor)


def _extract_page_minor(
    page_html: str, *, sections: list[dict] | None = None
) -> str | None:
    soup = BeautifulSoup(page_html, "lxml")
    root = soup.find("main") or soup.body or soup

    title_tag = root.find("h1") if isinstance(root, Tag) else None
    if title_tag is not None:
        title_match = _PAGE_TITLE_MINOR_RE.search(title_tag.get_text(" ", strip=True))
        if title_match is not None:
            return title_match.group("minor")

    if not sections:
        return None

    for section in sections:
        version = section.get("version", "")
        version_match = re.match(r"^(?P<minor>\d+\.\d+)(?:\.\d+)?$", version)
        if version_match:
            return version_match.group("minor")
    return None


def _has_baseline_version(discovered_versions: set[str], *, minor: str | None) -> bool:
    if minor is None:
        return False
    return minor in discovered_versions or f"{minor}.0" in discovered_versions


def _extract_major_features_section(
    page_html: str, *, minor: str, fallback_date: str | None = None
) -> dict[str, str] | None:
    soup = BeautifulSoup(page_html, "lxml")
    root = soup.find("main") or soup.body or soup

    features_heading = None
    for heading in root.find_all("h2"):
        heading_text = heading.get_text(" ", strip=True)
        if heading_text.lower() == "features":
            features_heading = heading
            break

    if features_heading is None:
        return None

    date_re = re.compile(_RELEASE_SECTION_DATE_RE, re.IGNORECASE)
    body_parts: list[str] = []
    date_match = date_re.search(features_heading.get_text(" ", strip=True))

    version_re = re.compile(_RELEASE_SECTION_VERSION_RE, re.IGNORECASE)
    for sibling in features_heading.next_siblings:
        if isinstance(sibling, Tag) and sibling.name == "h2":
            sibling_text = sibling.get_text(" ", strip=True)
            if version_re.search(sibling_text):
                break

        if isinstance(sibling, Tag):
            body_parts.append(str(sibling))
            if date_match is None:
                date_match = date_re.search(sibling.get_text(" ", strip=True))

    if not body_parts:
        return None

    if date_match is not None:
        release_date = normalize_human_date(date_match.group("date"))
    elif fallback_date:
        release_date = fallback_date
    else:
        return None

    return {
        "version": f"{minor}.0",
        "title": f"Version {minor}.0",
        "release_date": release_date,
        "body_html": "\n".join(body_parts).strip(),
    }


def _extract_major_blog_section(
    page_html: str, *, release_url: str, minor: str
) -> dict[str, str] | None:
    soup = BeautifulSoup(page_html, "lxml")
    root = soup.find("main") or soup.body or soup
    if not isinstance(root, Tag):
        return None

    blog_url = _find_major_blog_url(root, release_url=release_url, minor=minor)
    if blog_url is None:
        return None

    try:
        blog_html = get_text(blog_url, use_auth=False, encoding="utf-8")
    except Exception as exc:
        print(
            f"[warn] Failed to fetch Visual Studio 2022 blog content for "
            f"minor {minor} from {blog_url} (release page: {release_url}): {exc}"
        )
        return None

    blog_soup = BeautifulSoup(blog_html, "lxml")
    content = blog_soup.select_one(".entry-content")
    if content is None:
        return None

    release_date = _extract_blog_release_date(blog_soup)
    if release_date is None:
        return None

    body_html = content.decode_contents().strip()
    if not body_html:
        return None

    return {
        "version": f"{minor}.0",
        "title": f"Visual Studio 2022 version {minor}.0",
        "release_date": release_date,
        "body_html": body_html,
    }


def _find_major_blog_url(root: Tag, *, release_url: str, minor: str) -> str | None:
    blog_heading = None
    for heading in root.find_all("h3"):
        if _BLOG_HEADING_RE.search(heading.get_text(" ", strip=True)):
            blog_heading = heading
            break
    if blog_heading is None:
        return None

    candidates: list[tuple[str, str]] = []
    for sibling in blog_heading.next_siblings:
        if isinstance(sibling, Tag) and sibling.name in {"h2", "h3"}:
            break
        if not isinstance(sibling, Tag):
            continue
        for link in sibling.find_all("a", href=True):
            href = urljoin(release_url, link["href"])
            text = link.get_text(" ", strip=True)
            candidates.append((href, text))

    if not candidates:
        return None

    minor_token = minor.replace(".", "-")

    for href, text in candidates:
        normalized_text = text.lower()
        if minor in normalized_text and (_DEVBLOG_URL_RE.search(href) or "aka.ms/" in href.lower()):
            return href

    for href, _ in candidates:
        normalized_href = href.lower()
        if minor_token in normalized_href and (_DEVBLOG_URL_RE.search(href) or "aka.ms/" in normalized_href):
            return href

    for href, _ in candidates:
        if _DEVBLOG_URL_RE.search(href) or "aka.ms/" in href.lower():
            return href

    return None


def _extract_blog_release_date(blog_soup: BeautifulSoup) -> str | None:
    published_meta = blog_soup.find("meta", attrs={"property": "article:published_time"})
    if published_meta is not None:
        published_raw = (published_meta.get("content") or "").strip()
        if published_raw:
            return published_raw.split("T", 1)[0]

    header_text = blog_soup.get_text(" ", strip=True)
    date_match = re.search(
        r"(?P<date>[A-Za-z]+\s+\d{1,2}(?:\s*(?:st|nd|rd|th))?\s*,\s+\d{4})",
        header_text,
        flags=re.IGNORECASE,
    )
    if date_match is None:
        return None

    return normalize_human_date(date_match.group("date"))


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


def _extract_history_release_dates(history_html: str) -> dict[str, str]:
    soup = BeautifulSoup(history_html, "lxml")
    version_cell_re = re.compile(r"^(?P<version>17\.\d+\.\d+)(?:\s|$)")
    date_re = re.compile(
        r"(?P<date>[A-Za-z]+\s+\d{1,2}(?:\s*(?:st|nd|rd|th))?\s*,\s+\d{4})"
    )

    mapping: dict[str, str] = {}
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [
                " ".join(cell.get_text(" ", strip=True).split())
                for cell in row.find_all(["td", "th"])
            ]
            if len(cells) < 2:
                continue
            version: str | None = None
            release_date: str | None = None
            for cell in cells:
                if version is None:
                    version_match = version_cell_re.match(cell)
                    if version_match:
                        version = version_match.group("version")
                        continue
                if release_date is None:
                    date_match = date_re.search(cell)
                    if date_match:
                        release_date = normalize_human_date(date_match.group("date"))
            if version and release_date and version not in mapping:
                mapping[version] = release_date
    return mapping


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
