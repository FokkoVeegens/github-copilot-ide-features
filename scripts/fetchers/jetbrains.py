"""JetBrains fetcher — GitHub Copilot plugin via JetBrains Marketplace API.

Source: https://plugins.jetbrains.com/api/plugins/17718/updates?page=N&size=100

Version format: "1.5.6.8049-251"  →  semver=1.5.6.8049, ide_build=251
Also handles 3-part semvers like "1.5.62-241"  →  semver=1.5.62, ide_build=241
Each semver maps to multiple build-line entries (e.g. -241, -242, -243).
We group them into one JSON file per semver with a `builds[]` array.
"""
import re
from datetime import datetime, timezone

from scripts.common.extract import extract_copilot_mentions, html_to_markdown
from scripts.common.http import get_json

_API_URL = "https://plugins.jetbrains.com/api/plugins/17718/updates"
# Matches "X.Y.Z-NNN" (3-part) or "X.Y.Z.NNNN-NNN" (4-part) version strings.
_VERSION_RE = re.compile(r"^(?P<semver>\d+(?:\.\d+){2,3})-(?P<build>\d+)$")
_PLUGIN_URL = "https://plugins.jetbrains.com/plugin/17718-github-copilot/versions"


def _parse_version(version_str: str) -> tuple[str, str]:
    """Return (semver, ide_build) from a version string like '1.5.6.8049-251'."""
    m = _VERSION_RE.match(version_str.strip())
    if not m:
        raise ValueError(f"Unrecognised JetBrains version string: {version_str!r}")
    return m.group("semver"), m.group("build")


def _paginate_updates() -> list[dict]:
    """Return all plugin update objects from the JetBrains Marketplace API."""
    updates: list[dict] = []
    page = 0
    while True:
        page_data = get_json(_API_URL, params={"size": 100, "page": page})
        if not page_data:
            break
        updates.extend(page_data)
        page += 1
    return updates


def fetch(ide_config: dict) -> list[dict]:
    """Fetch all JetBrains plugin updates and return a grouped list of release dicts.

    Each element in the returned list represents one semantic version (e.g.
    ``1.5.62``) and contains a ``builds[]`` sub-array with per-IDE-build
    compatibility metadata.
    """
    raw_updates = _paginate_updates()

    # Group raw update entries by semantic version.
    groups: dict[str, list[dict]] = {}
    for item in raw_updates:
        version_str = item.get("version") or ""
        try:
            semver, ide_build = _parse_version(version_str)
        except ValueError:
            print(f"  [warn] Skipping JetBrains update with unexpected version: {version_str!r}")
            continue
        groups.setdefault(semver, []).append({"ide_build": ide_build, "item": item})

    results: list[dict] = []
    for semver, build_list in groups.items():
        # Earliest cdate (milliseconds epoch) across builds → ISO-8601 date.
        cdate_values = [b["item"].get("cdate") or 0 for b in build_list]
        earliest_cdate = min(cdate_values)
        if earliest_cdate:
            release_date = datetime.fromtimestamp(
                earliest_cdate / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%d")
        else:
            release_date = "1970-01-01"

        # Notes HTML is identical across all builds for a given semver.
        first_item = build_list[0]["item"]
        notes_html: str = first_item.get("notes") or ""
        notes_markdown = html_to_markdown(notes_html) if notes_html else ""
        copilot_mentions = extract_copilot_mentions(notes_markdown)

        # Per-build compatibility metadata.
        builds = [
            {
                "ide_build": b["ide_build"],
                "since": b["item"].get("since"),
                "until": b["item"].get("until"),
                "compatible_versions": b["item"].get("compatibleVersions"),
                "file_id": b["item"].get("id"),
                "downloads": b["item"].get("downloads"),
            }
            for b in build_list
        ]

        results.append(
            {
                "ide": ide_config["id"],
                "version": semver,
                "release_date": release_date,
                "title": f"GitHub Copilot for JetBrains {semver}",
                "url": _PLUGIN_URL,
                "source": "api",
                "body_markdown": notes_markdown,
                "body_html": notes_html,
                "categories": [],
                "copilot_mentions": copilot_mentions,
                "builds": builds,
            }
        )

    return results
