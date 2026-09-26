"""Repository-wide release-data quality checks."""
import json
import pathlib
import re
from datetime import date, datetime

DATA_ROOT = pathlib.Path(__file__).parents[1] / "data"
# These synthetic era-start dates were previously used as Vim/Neovim placeholders
# before exact source dates were backfilled; extend this set if similar sentinels
# are introduced for other repositories or time ranges.
KNOWN_PLACEHOLDER_RELEASE_DATES = {"2024-01-01", "2026-01-01"}
EXPLICIT_DATE_PATTERNS = (
    re.compile(r"\*[ \t]*Release date:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})"),
    re.compile(r"^##\s+\d+\.\d+\.\d+\s+-\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})\r?$", re.MULTILINE),
)


def test_release_dates_are_iso_and_not_synthetic_placeholders() -> None:
    for path in DATA_ROOT.glob("*/[!index]*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        release_date = record["release_date"]

        if release_date is not None:
            date.fromisoformat(release_date)
            assert release_date not in KNOWN_PLACEHOLDER_RELEASE_DATES, path


def test_explicit_release_dates_match_persisted_dates() -> None:
    for path in DATA_ROOT.glob("*/[!index]*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        body = record.get("body_markdown") or ""

        for pattern in EXPLICIT_DATE_PATTERNS:
            match = pattern.search(body)
            if match:
                expected_date = datetime.strptime(match.group(1), "%B %d, %Y").date()
                assert record["release_date"] == expected_date.isoformat(), path
                break
