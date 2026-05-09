"""Idempotent JSON writer for release records."""
import json
import pathlib
from datetime import datetime, timezone


def write_release(data_dir: pathlib.Path, release: dict) -> bool:
    """Write *release* to ``<data_dir>/<version>.json``.

    Returns True when the file was written, False when it already existed
    (idempotency: existing files are never overwritten).
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{release['version']}.json"
    if path.exists():
        return False
    release.setdefault("fetched_at", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    release.setdefault("schema_version", 1)
    path.write_text(json.dumps(release, indent=2, ensure_ascii=False), encoding="utf-8")
    return True
