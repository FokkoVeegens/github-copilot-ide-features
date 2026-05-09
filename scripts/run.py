"""CLI entry point: python -m scripts.run --ide <id>"""
import argparse
import importlib
import pathlib
import sys

from scripts.common.config import get_ide_config
from scripts.common.io import write_release

_REPO_ROOT = pathlib.Path(__file__).parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch release notes for a single IDE and write new JSON files."
    )
    parser.add_argument("--ide", required=True, metavar="ID", help="IDE id (from config/ides.yml)")
    args = parser.parse_args()

    ide_config = get_ide_config(args.ide)
    fetcher_module = importlib.import_module(f"scripts.fetchers.{ide_config['fetcher']}")
    data_dir = _REPO_ROOT / ide_config["data_dir"]

    releases = fetcher_module.fetch(ide_config)

    written = 0
    skipped = 0
    for release in releases:
        if write_release(data_dir, release):
            written += 1
            print(f"  [new]  {release['version']}")
        else:
            skipped += 1
            print(f"  [skip] {release['version']}")

    print(f"\nDone — {written} new, {skipped} skipped.")
    if written == 0 and skipped == 0:
        print("No releases returned by fetcher.")
    sys.exit(0)


if __name__ == "__main__":
    main()
