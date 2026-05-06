"""HTML-to-Markdown conversion and Copilot-mention extraction."""
import re

import markdownify
from bs4 import BeautifulSoup

# Lines/snippets matching any of these patterns are classed as Copilot mentions.
_COPILOT_PATTERN = re.compile(
    r"(github\s+copilot|copilot\b|ai\s+assist|ai-assist|chat\s+agent|inline\s+chat)",
    re.IGNORECASE,
)


def html_to_markdown(html: str) -> str:
    """Convert *html* to Markdown using markdownify.

    ``<script>`` and ``<style>`` tags (and their content) are removed before
    conversion so they don't leak into the output.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return markdownify.markdownify(str(soup), heading_style="ATX").strip()


def extract_copilot_mentions(markdown: str) -> list[str]:
    """Return list of non-empty lines in *markdown* that match the Copilot heuristic."""
    mentions: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped and _COPILOT_PATTERN.search(stripped):
            mentions.append(stripped)
    return mentions
