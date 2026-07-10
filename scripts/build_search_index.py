"""Build a searchable index from release notes across all IDEs.

Generates search-index.json and meta.json for use on GitHub Pages.
"""
import argparse
import json
import pathlib
from datetime import UTC, datetime

from scripts.common.config import load_config


def build_search_index(config_path: pathlib.Path | None = None, data_root: pathlib.Path | None = None) -> dict:
    """Build search index from all IDE data files.
    
    Args:
        config_path: path to config/ides.yml
        data_root: root data directory (defaults to ./data)
    
    Returns:
        dict with 'records' (list) and 'metadata' (dict)
    """
    if config_path is None:
        config_path = pathlib.Path(__file__).parents[1] / "config" / "ides.yml"
    if data_root is None:
        data_root = pathlib.Path(__file__).parents[1] / "data"
    
    config = load_config(config_path)
    records = []
    ide_version_counts = {}
    
    # Iterate all IDEs except 'dummy'
    for ide_config in config.get("ides", []):
        ide_id = ide_config["id"]
        if ide_id == "dummy":
            continue
        
        ide_name = ide_config.get("name", ide_id)
        # data_dir in config is like "data/eclipse", extract just the IDE part
        config_data_dir = ide_config["data_dir"]
        ide_dir_name = config_data_dir.split("/")[-1] if "/" in config_data_dir else config_data_dir
        data_dir = data_root / ide_dir_name
        
        if not data_dir.exists():
            continue
        
        # Track version counts
        ide_version_counts[ide_name] = 0
        
        # Scan all JSON files except index.json
        for json_file in sorted(data_dir.glob("*.json")):
            if json_file.name == "index.json":
                continue
            
            try:
                with json_file.open(encoding="utf-8") as f:
                    release = json.load(f)
                
                version = release.get("version")
                release_date = release.get("release_date")
                url = release.get("url")
                
                if not (version and release_date and url):
                    continue
                
                # Extract snippets from copilot_mentions; fall back to body_markdown
                snippets = _extract_snippets(release)
                
                if snippets:
                    ide_version_counts[ide_name] += 1
                    for snippet in snippets:
                        records.append({
                            "ide": ide_id,
                            "ide_name": ide_name,
                            "version": version,
                            "release_date": release_date,
                            "url": url,
                            "snippet": snippet,
                        })
            
            except (json.JSONDecodeError, KeyError, OSError) as e:
                # Skip malformed files with a warning
                print(f"  [warn] {json_file}: {e}", flush=True)
                continue
    
    # Sort records deterministically: by ide_name, then version (as tuple if numeric)
    def sort_key(r):
        # Parse version into comparable tuple: numeric parts become ints, non-numeric stay strings
        version_parts = []
        for part in r["version"].split("."):
            try:
                version_parts.append((0, int(part)))  # 0 = numeric, comes before strings
            except ValueError:
                version_parts.append((1, part))  # 1 = non-numeric string
        return (r["ide_name"], version_parts, r["snippet"])
    
    records.sort(key=sort_key)
    
    metadata = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "") + "Z",
        "ide_version_counts": ide_version_counts,
    }
    
    return {"records": records, "metadata": metadata}


def _extract_snippets(release: dict) -> list[str]:
    """Extract Copilot-related snippets from a release.
    
    Prefers copilot_mentions; falls back to body_markdown bullet lines.
    """
    snippets = []
    
    # Try copilot_mentions first
    copilot_mentions = release.get("copilot_mentions", [])
    if isinstance(copilot_mentions, list) and copilot_mentions:
        for mention in copilot_mentions:
            if isinstance(mention, str):
                cleaned = _normalize_snippet(mention)
                if cleaned:
                    snippets.append(cleaned)
        return snippets
    
    # Fall back to body_markdown
    body = release.get("body_markdown", "")
    if body:
        # Extract bullet lines (lines starting with -, *, or +)
        for line in body.split("\n"):
            line = line.strip()
            if line and line[0] in "-*+":
                # Remove the bullet marker and any following space
                content = line.lstrip("-*+ ").strip()
                if content:
                    cleaned = _normalize_snippet(content)
                    if cleaned:
                        snippets.append(cleaned)
    
    return snippets


def _normalize_snippet(text: str) -> str:
    """Normalize a snippet: strip markdown syntax, collapse whitespace.
    
    Keeps the original text for matching but removes:
    - markdown link syntax [text](url) → text
    - heading markers (# ## ###, etc.)
    - bullet markers (-, *, +)
    """
    # Remove markdown links [text](url) -> keep text
    import re
    text = re.sub(r'\[([^\]]+)\]\([^\)]*\)', r'\1', text)
    
    # Remove markdown heading markers at start
    text = re.sub(r'^#+\s+', '', text)
    
    # Remove bullet markers at start (-, *, +)
    text = re.sub(r'^[-*+]\s+', '', text)
    
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build search index from all IDE release notes."
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path.cwd() / "_site",
        help="Output directory for search-index.json and meta.json (default: _site/)",
    )
    args = parser.parse_args()
    
    result = build_search_index()
    
    args.output.mkdir(parents=True, exist_ok=True)
    
    # Write search index
    index_path = args.output / "search-index.json"
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(result["records"], f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(result['records'])} records to {index_path}")
    
    # Write metadata
    meta_path = args.output / "meta.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(result["metadata"], f, indent=2, ensure_ascii=False)
    print(f"Wrote metadata to {meta_path}")


if __name__ == "__main__":
    main()
