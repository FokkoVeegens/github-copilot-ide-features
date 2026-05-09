"""Dummy fetcher — no network, used for MVP 0 walking skeleton."""


def fetch(ide_config: dict) -> list[dict]:
    """Return two hardcoded releases to exercise the pipeline end-to-end."""
    return [
        {
            "ide": "dummy",
            "version": "0.0.1",
            "release_date": "2024-01-01",
            "title": "Dummy Release 0.0.1",
            "url": "https://example.com/releases/0.0.1",
            "source": "api",
            "body_markdown": "## Changes\n\n- Initial release.",
            "body_html": "<h2>Changes</h2><ul><li>Initial release.</li></ul>",
            "categories": [],
            "copilot_mentions": [],
        },
        {
            "ide": "dummy",
            "version": "0.0.2",
            "release_date": "2024-02-01",
            "title": "Dummy Release 0.0.2",
            "url": "https://example.com/releases/0.0.2",
            "source": "api",
            "body_markdown": "## Changes\n\n- Added GitHub Copilot integration.",
            "body_html": "<h2>Changes</h2><ul><li>Added GitHub Copilot integration.</li></ul>",
            "categories": [],
            "copilot_mentions": ["Added GitHub Copilot integration."],
        },
    ]
