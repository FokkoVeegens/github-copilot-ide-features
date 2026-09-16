"""HTML-to-Markdown conversion and Copilot-mention extraction."""
import re

import markdownify
from bs4 import BeautifulSoup

# Lines/snippets matching any of these patterns are classed as Copilot mentions.
_COPILOT_PATTERN = re.compile(
    r"(github\s+copilot|copilot\b|ai\s+assist|ai-assist|chat\s+agent|inline\s+chat)",
    re.IGNORECASE,
)

# A bullet whose entire content is a bold section header (e.g. "* **New Features**")
# rather than an actual feature description.
_SECTION_HEADER_RE = re.compile(r"^[-*+]\s+\*\*[^*]+\*\*:?$")

# An ATX heading / release-date banner (e.g. "### Added" or "## 0.0.334 - 2025-10-03")
# — structural metadata rather than a feature description.
_ATX_HEADING_RE = re.compile(r"^#{1,6}\s+")


def html_to_markdown(html: str) -> str:
    """Convert *html* to Markdown using markdownify.

    ``<script>`` and ``<style>`` tags (and their content) are removed before
    conversion so they don't leak into the output.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return markdownify.markdownify(str(soup), heading_style="ATX").strip()


def extract_copilot_mentions(markdown: str, require_keyword: bool = True) -> list[str]:
    """Return list of non-empty lines in *markdown* that match the Copilot heuristic.

    Set *require_keyword* to ``False`` for sources whose release notes are
    entirely about a Copilot product (e.g. the JetBrains/Xcode/Eclipse Copilot
    plugins, or the Copilot CLI). In that case every non-empty line is
    considered relevant, since lines like "Agent skills are generally
    available." don't literally mention "Copilot" but are still Copilot
    features. Structural lines that carry no feature information on their own
    are always excluded: bullet-only section headers (e.g. "* **New
    Features**") and ATX headings / release-date banners (e.g. "### Added" or
    "## 0.0.334 - 2025-10-03").
    """
    mentions: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped or _SECTION_HEADER_RE.match(stripped) or _ATX_HEADING_RE.match(stripped):
            continue
        if not require_keyword or _COPILOT_PATTERN.search(stripped):
            mentions.append(stripped)
    return mentions
