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
        aliases = ide.get("aliases") or []
        if ide["id"] == ide_id or ide_id in aliases:
            return ide
    raise ValueError(f"IDE '{ide_id}' not found in {config_path}")


def require_config_value(ide_config: dict, key: str) -> str:
    """Return a required non-empty config value for an IDE."""
    value = ide_config.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        ide_id = ide_config.get("id", "<unknown>")
        raise ValueError(f"IDE '{ide_id}' is missing required config value '{key}'")
    return value
