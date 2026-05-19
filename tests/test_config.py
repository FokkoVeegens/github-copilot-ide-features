"""Tests for scripts/common/config.py."""

import pathlib

import pytest

from scripts.common.config import get_ide_config


def test_get_ide_config_by_id_works() -> None:
    config = get_ide_config("sql-server-management-studio")
    assert config["id"] == "sql-server-management-studio"


def test_get_ide_config_by_alias_works() -> None:
    config = get_ide_config("ssms")
    assert config["id"] == "sql-server-management-studio"


def test_get_ide_config_unknown_raises() -> None:
    with pytest.raises(ValueError, match="IDE 'does-not-exist' not found"):
        get_ide_config("does-not-exist", config_path=pathlib.Path("config/ides.yml"))


def test_get_ide_config_string_alias_is_treated_as_single_alias(tmp_path: pathlib.Path) -> None:
    config_path = tmp_path / "ides.yml"
    config_path.write_text(
        "ides:\n"
        "  - id: sql-server-management-studio\n"
        "    aliases: ssms\n",
        encoding="utf-8",
    )
    config = get_ide_config("ssms", config_path=config_path)
    assert config["id"] == "sql-server-management-studio"


def test_get_ide_config_invalid_alias_type_raises(tmp_path: pathlib.Path) -> None:
    config_path = tmp_path / "ides.yml"
    config_path.write_text(
        "ides:\n"
        "  - id: sql-server-management-studio\n"
        "    aliases: 42\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid 'aliases'"):
        get_ide_config("ssms", config_path=config_path)
