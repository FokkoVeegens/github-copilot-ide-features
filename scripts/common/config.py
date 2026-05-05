"""Config loader — reads config/ides.yml and returns per-IDE config dicts."""
import pathlib

import yaml

_CONFIG_PATH = pathlib.Path(__file__).parents[2] / "config" / "ides.yml"


def load_config(config_path: pathlib.Path = _CONFIG_PATH) -> dict:
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_ide_config(ide_id: str, config_path: pathlib.Path = _CONFIG_PATH) -> dict:
    config = load_config(config_path)
    for ide in config.get("ides", []):
        if ide["id"] == ide_id:
            return ide
    raise ValueError(f"IDE '{ide_id}' not found in {config_path}")
