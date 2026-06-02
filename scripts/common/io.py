"""Idempotent JSON writer for release records."""
import json
import pathlib
from datetime import UTC, datetime


def write_release(data_dir: pathlib.Path, release: dict) -> bool:
    """Write *release* to ``<data_dir>/<version>.json``.

    Returns True when the file was written, False when it already existed
    (idempotency: existing files are never overwritten).
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{release['version']}.json"
    if path.exists():
        return False
    release.setdefault("fetched_at", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    release.setdefault("schema_version", 1)
    path.write_text(json.dumps(release, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def generate_ide_index(data_dir: pathlib.Path) -> None:
    """Generate an index.json file for all versions in the IDE data directory.
    
    The index contains an array of objects with properties:
    - version: the release version
    - release_date: the release date (YYYY-MM-DD format)
    - filename: the JSON filename (e.g., "1.83.0.json")
    
    Index is sorted by release_date in descending order (newest first).
    """
    if not data_dir.exists():
        return
    
    index_entries = []
    
    # Scan all JSON files except index.json
    for json_file in sorted(data_dir.glob("*.json")):
        if json_file.name == "index.json":
            continue
        
        try:
            with json_file.open(encoding="utf-8") as f:
                data = json.load(f)
                
            version = data.get("version")
            release_date = data.get("release_date")
            
            if version and release_date:
                index_entries.append({
                    "version": version,
                    "release_date": release_date,
                    "filename": json_file.name
                })
        except (json.JSONDecodeError, KeyError, OSError):
            # Skip files that can't be read or are missing required fields
            continue
    
    # Sort by release_date in descending order (newest first)
    index_entries.sort(key=lambda x: x["release_date"], reverse=True)
    
    # Write index.json
    index_path = data_dir / "index.json"
    index_path.write_text(json.dumps(index_entries, indent=2, ensure_ascii=False), encoding="utf-8")
