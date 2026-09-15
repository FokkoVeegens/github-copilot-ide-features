"""Recompute ``copilot_mentions`` for existing release data files.

The Copilot-dedicated IDEs (Eclipse, Copilot CLI, JetBrains, Xcode,
Vim/Neovim) extract mentions with ``require_keyword=False`` because their
entire changelog is about a Copilot product. Because ``write_release`` never
overwrites existing files, changes to the extraction heuristic
(:func:`scripts.common.extract.extract_copilot_mentions`) don't reach files
that were already committed. This idempotent backfill re-derives
``copilot_mentions`` from each file's stored ``body_markdown`` so the current
heuristic applies retroactively — running it again is a no-op once files are
up to date.
"""
import argparse
import json
import pathlib

from scripts.common.config import load_config
from scripts.common.extract import extract_copilot_mentions

# IDE ids whose fetchers call extract_copilot_mentions(require_keyword=False).
REQUIRE_KEYWORD_FALSE_IDES = frozenset(
    {"eclipse", "copilot-cli", "jetbrains", "xcode", "vim-neovim"}
)


def backfill_file(path: pathlib.Path) -> bool:
    """Recompute copilot_mentions for one file; return True if it changed."""
    release = json.loads(path.read_text(encoding="utf-8"))
    body_markdown = release.get("body_markdown") or ""
    new_mentions = extract_copilot_mentions(body_markdown, require_keyword=False)
    if release.get("copilot_mentions") == new_mentions:
        return False
    release["copilot_mentions"] = new_mentions
    path.write_text(json.dumps(release, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def backfill(config_path: pathlib.Path | None = None, data_root: pathlib.Path | None = None) -> int:
    """Backfill all keyword-free IDE data dirs; return count of updated files."""
    repo_root = pathlib.Path(__file__).parents[1]
    if config_path is None:
        config_path = repo_root / "config" / "ides.yml"
    if data_root is None:
        data_root = repo_root / "data"

    config = load_config(config_path)
    updated = 0

    for ide_config in config.get("ides", []):
        if ide_config["id"] not in REQUIRE_KEYWORD_FALSE_IDES:
            continue
        ide_rel_path = ide_config["data_dir"]
        data_dir = data_root / ide_rel_path.removeprefix("./").removeprefix("/")
        if not data_dir.exists():
            continue

        ide_updated = 0
        for json_file in sorted(data_dir.glob("*.json")):
            if json_file.name == "index.json":
                continue
            if backfill_file(json_file):
                ide_updated += 1
        updated += ide_updated
        print(f"  {ide_config['id']}: {ide_updated} file(s) updated")

    print(f"Backfill complete: {updated} file(s) updated")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    backfill()


if __name__ == "__main__":
    main()
