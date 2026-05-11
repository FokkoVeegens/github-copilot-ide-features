"""Tests for scripts/common/changelog.py."""
from scripts.common.changelog import split_changelog_by_version


def test_splits_bracketed_headings():
    changelog = """
# Changelog

## [1.2.0]
Added a new feature.

## [1.1.0]
Older notes.
"""
    sections = split_changelog_by_version(changelog)
    assert sections["1.2.0"] == "Added a new feature."
    assert sections["1.1.0"] == "Older notes."


def test_splits_plain_headings():
    changelog = """
## 2.0.0
Major changes.

## 1.9.0
Smaller changes.
"""
    sections = split_changelog_by_version(changelog)
    assert sections["2.0.0"] == "Major changes."
    assert sections["1.9.0"] == "Smaller changes."


def test_normalizes_v_prefix():
    changelog = """
## [v0.48.0]
Release notes.
"""
    sections = split_changelog_by_version(changelog)
    assert "0.48.0" in sections
    assert sections["0.48.0"] == "Release notes."


def test_ignores_non_version_h2():
    changelog = """
## Unreleased
Work in progress.

## [1.0.0]
Stable notes.
"""
    sections = split_changelog_by_version(changelog)
    assert "1.0.0" in sections
    assert "Unreleased" not in sections

