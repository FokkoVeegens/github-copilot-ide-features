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
