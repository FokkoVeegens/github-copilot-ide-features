"""Tests for scripts/common/extract.py"""

from scripts.common.extract import extract_copilot_mentions, html_to_markdown


class TestHtmlToMarkdown:
    def test_heading_converted(self):
        result = html_to_markdown("<h2>Changes</h2>")
        assert "## Changes" in result

    def test_list_items_converted(self):
        result = html_to_markdown("<ul><li>Fix A</li><li>Fix B</li></ul>")
        assert "Fix A" in result
        assert "Fix B" in result

    def test_script_tags_stripped(self):
        result = html_to_markdown("<p>Hello</p><script>alert(1)</script>")
        assert "alert" not in result
        assert "Hello" in result

    def test_style_tags_stripped(self):
        result = html_to_markdown("<p>Hello</p><style>.x{color:red}</style>")
        assert "color" not in result
        assert "Hello" in result

    def test_empty_html_returns_empty_string(self):
        assert html_to_markdown("") == ""

    def test_plain_text_passthrough(self):
        result = html_to_markdown("<p>Just plain text.</p>")
        assert "Just plain text." in result


class TestExtractCopilotMentions:
    def test_matches_copilot_word(self):
        md = "- Added Copilot support.\n- Fixed a bug."
        mentions = extract_copilot_mentions(md)
        assert len(mentions) == 1
        assert "Added Copilot support." in mentions[0]

    def test_matches_github_copilot(self):
        md = "Use GitHub Copilot to generate code."
        mentions = extract_copilot_mentions(md)
        assert len(mentions) == 1

    def test_case_insensitive(self):
        md = "COPILOT is now available.\nSomething else."
        mentions = extract_copilot_mentions(md)
        assert len(mentions) == 1

    def test_matches_ai_assist(self):
        md = "AI assist feature added."
        mentions = extract_copilot_mentions(md)
        assert len(mentions) == 1

    def test_matches_inline_chat(self):
        md = "Inline chat improvements shipped."
        mentions = extract_copilot_mentions(md)
        assert len(mentions) == 1

    def test_no_match_returns_empty(self):
        md = "Fixed a null pointer exception.\nUpdated dependencies."
        mentions = extract_copilot_mentions(md)
        assert mentions == []

    def test_empty_string_returns_empty(self):
        assert extract_copilot_mentions("") == []

    def test_multiple_matching_lines(self):
        md = "Copilot chat added.\nGitHub Copilot enabled by default.\nBug fix."
        mentions = extract_copilot_mentions(md)
        assert len(mentions) == 2

    def test_blank_lines_not_included(self):
        md = "\n\nCopilot enabled.\n\n"
        mentions = extract_copilot_mentions(md)
        assert all(m.strip() for m in mentions)
