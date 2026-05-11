"""Helpers for parsing markdown changelogs by version heading."""
import re

_VERSION_HEADING_RE = re.compile(
    r"^##\s+(?:\[(?P<bracketed>v?\d+(?:\.\d+){1,3})\]|(?P<plain>v?\d+(?:\.\d+){1,3}))(?=\s|$).*$",
    re.MULTILINE,
)


def split_changelog_by_version(changelog_markdown: str) -> dict[str, str]:
    """Return ``{version: section_markdown}`` parsed from a markdown changelog.

    Supported heading formats:
    - ``## [1.2.3]``
    - ``## 1.2.3``
    """
    matches = list(_VERSION_HEADING_RE.finditer(changelog_markdown))
    sections: dict[str, str] = {}

    for i, match in enumerate(matches):
        version = (match.group("bracketed") or match.group("plain") or "").lstrip("vV")
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(changelog_markdown)
        section = changelog_markdown[start:end].strip()
        if version and version not in sections:
            sections[version] = section

    return sections
