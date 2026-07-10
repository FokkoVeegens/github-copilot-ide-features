"""Tests for scripts/build_search_index.py."""

import json
import pathlib

import pytest

from scripts.build_search_index import (
    _extract_snippets,
    _normalize_snippet,
    build_search_index,
)


@pytest.fixture
def tmp_config(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """Create a minimal test config and data directory structure."""
    config_path = tmp_path / "ides.yml"
    data_root = tmp_path / "data"
    
    config_path.write_text(
        "ides:\n"
        "  - id: dummy\n"
        "    name: Dummy IDE\n"
        "    data_dir: dummy\n"
        "    fetcher: dummy\n"
        "  - id: test-ide-1\n"
        "    name: Test IDE One\n"
        "    data_dir: test-ide-1\n"
        "    fetcher: test\n"
        "  - id: test-ide-2\n"
        "    name: Test IDE Two\n"
        "    data_dir: test-ide-2\n"
        "    fetcher: test\n",
        encoding="utf-8",
    )
    return config_path, data_root


@pytest.fixture
def populated_data(tmp_config: tuple[pathlib.Path, pathlib.Path]) -> tuple[pathlib.Path, pathlib.Path]:
    """Create a config and populated data directories."""
    config_path, data_root = tmp_config
    
    # Populate test-ide-1 with two releases
    (data_root / "test-ide-1").mkdir(parents=True, exist_ok=True)
    
    release1 = {
        "ide": "test-ide-1",
        "version": "1.0.0",
        "release_date": "2026-01-01",
        "title": "First Release",
        "url": "https://example.com/releases/1.0.0",
        "body_markdown": "## Features\n- New feature A\n- Bug fix B",
        "copilot_mentions": ["- New Copilot feature"],
        "schema_version": 1,
    }
    (data_root / "test-ide-1" / "1.0.0.json").write_text(
        json.dumps(release1), encoding="utf-8"
    )
    
    release2 = {
        "ide": "test-ide-1",
        "version": "1.1.0",
        "release_date": "2026-01-15",
        "title": "Second Release",
        "url": "https://example.com/releases/1.1.0",
        "body_markdown": "## Updates\n- Improved Copilot chat",
        "copilot_mentions": [],  # Empty, should fall back to body_markdown
        "schema_version": 1,
    }
    (data_root / "test-ide-1" / "1.1.0.json").write_text(
        json.dumps(release2), encoding="utf-8"
    )
    
    # Populate test-ide-2 with one release
    (data_root / "test-ide-2").mkdir(parents=True, exist_ok=True)
    
    release3 = {
        "ide": "test-ide-2",
        "version": "2.0.0",
        "release_date": "2026-02-01",
        "title": "Initial Release",
        "url": "https://example.com/releases/2.0.0",
        "body_markdown": "* [Copilot support](https://example.com)\n* Performance improvements",
        "copilot_mentions": ["* [Copilot support](https://example.com)"],
        "schema_version": 1,
    }
    (data_root / "test-ide-2" / "2.0.0.json").write_text(
        json.dumps(release3), encoding="utf-8"
    )
    
    # Add index.json files (should be skipped during indexing)
    (data_root / "test-ide-1" / "index.json").write_text(
        json.dumps({"index": True}), encoding="utf-8"
    )
    
    return config_path, data_root


def test_normalize_snippet_strips_markdown_links() -> None:
    assert _normalize_snippet("[text](url)") == "text"
    assert _normalize_snippet("[My link](https://example.com) is here") == "My link is here"


def test_normalize_snippet_strips_heading_markers() -> None:
    assert _normalize_snippet("# Main heading") == "Main heading"
    assert _normalize_snippet("### Subheading") == "Subheading"


def test_normalize_snippet_strips_bullet_markers() -> None:
    assert _normalize_snippet("- Bullet item") == "Bullet item"
    assert _normalize_snippet("* Star item") == "Star item"
    assert _normalize_snippet("+ Plus item") == "Plus item"


def test_normalize_snippet_collapses_whitespace() -> None:
    assert _normalize_snippet("Text  with   spaces") == "Text with spaces"
    assert _normalize_snippet("  leading and trailing  ") == "leading and trailing"


def test_extract_snippets_from_copilot_mentions() -> None:
    release = {
        "copilot_mentions": [
            "- Improved Copilot chat",
            "- New feature",
        ],
        "body_markdown": "This should not be used",
    }
    snippets = _extract_snippets(release)
    assert len(snippets) == 2
    assert "Improved Copilot chat" in snippets
    assert "New feature" in snippets


def test_extract_snippets_falls_back_to_body_markdown() -> None:
    release = {
        "copilot_mentions": [],  # Empty, should fall back
        "body_markdown": "- Bullet point 1\n- Bullet point 2\nNot a bullet\n* Star bullet",
    }
    snippets = _extract_snippets(release)
    assert len(snippets) == 3
    assert "Bullet point 1" in snippets
    assert "Bullet point 2" in snippets
    assert "Star bullet" in snippets


def test_extract_snippets_ignores_missing_fields() -> None:
    release = {}
    snippets = _extract_snippets(release)
    assert snippets == []


def test_build_search_index_returns_expected_structure(populated_data: tuple[pathlib.Path, pathlib.Path]) -> None:
    config_path, data_root = populated_data
    result = build_search_index(config_path, data_root)
    
    assert "records" in result
    assert "metadata" in result
    assert isinstance(result["records"], list)
    assert isinstance(result["metadata"], dict)


def test_build_search_index_excludes_dummy_ide(populated_data: tuple[pathlib.Path, pathlib.Path]) -> None:
    config_path, data_root = populated_data
    
    # Add dummy IDE data (should be skipped)
    (data_root / "dummy").mkdir(parents=True, exist_ok=True)
    dummy_release = {
        "ide": "dummy",
        "version": "1.0.0",
        "release_date": "2026-01-01",
        "url": "https://example.com",
        "copilot_mentions": ["- Should be ignored"],
    }
    (data_root / "dummy" / "1.0.0.json").write_text(
        json.dumps(dummy_release), encoding="utf-8"
    )
    
    result = build_search_index(config_path, data_root)
    for record in result["records"]:
        assert record["ide"] != "dummy"


def test_build_search_index_records_are_deterministically_sorted(populated_data: tuple[pathlib.Path, pathlib.Path]) -> None:
    config_path, data_root = populated_data
    
    # Build index twice and verify they're identical
    result1 = build_search_index(config_path, data_root)
    result2 = build_search_index(config_path, data_root)
    
    assert result1["records"] == result2["records"]


def test_build_search_index_sorts_by_ide_name_then_version(populated_data: tuple[pathlib.Path, pathlib.Path]) -> None:
    config_path, data_root = populated_data
    result = build_search_index(config_path, data_root)
    
    # Verify ordering: Test IDE One (1.0.0, 1.1.0) should come before Test IDE Two (2.0.0)
    ides_in_order = [r["ide_name"] for r in result["records"]]
    first_test_ide_one_idx = ides_in_order.index("Test IDE One")
    first_test_ide_two_idx = ides_in_order.index("Test IDE Two")
    assert first_test_ide_one_idx < first_test_ide_two_idx


def test_build_search_index_includes_all_required_fields(populated_data: tuple[pathlib.Path, pathlib.Path]) -> None:
    config_path, data_root = populated_data
    result = build_search_index(config_path, data_root)
    
    assert len(result["records"]) > 0
    for record in result["records"]:
        assert "ide" in record
        assert "ide_name" in record
        assert "version" in record
        assert "release_date" in record
        assert "url" in record
        assert "snippet" in record


def test_build_search_index_metadata_includes_version_counts(populated_data: tuple[pathlib.Path, pathlib.Path]) -> None:
    config_path, data_root = populated_data
    result = build_search_index(config_path, data_root)
    
    metadata = result["metadata"]
    assert "generated_at" in metadata
    assert "ide_version_counts" in metadata
    assert metadata["ide_version_counts"]["Test IDE One"] == 2
    assert metadata["ide_version_counts"]["Test IDE Two"] == 1


def test_build_search_index_tolerates_malformed_json(populated_data: tuple[pathlib.Path, pathlib.Path]) -> None:
    config_path, data_root = populated_data
    
    # Add a malformed JSON file
    (data_root / "test-ide-1" / "malformed.json").write_text("{ invalid json", encoding="utf-8")
    
    # Should not crash, just warn and continue
    result = build_search_index(config_path, data_root)
    # Should still have records from valid files
    assert len(result["records"]) > 0


def test_build_search_index_tolerates_missing_data_dir(populated_data: tuple[pathlib.Path, pathlib.Path]) -> None:
    config_path, data_root = populated_data
    
    # Remove data directory for test-ide-2
    import shutil
    shutil.rmtree(data_root / "test-ide-2")
    
    # Should not crash
    result = build_search_index(config_path, data_root)
    # Should still have records from test-ide-1
    for record in result["records"]:
        assert record["ide"] == "test-ide-1"


def test_build_search_index_skips_files_missing_required_fields(tmp_config: tuple[pathlib.Path, pathlib.Path]) -> None:
    config_path, data_root = tmp_config
    (data_root / "test-ide-1").mkdir(parents=True, exist_ok=True)
    
    # Release missing version
    incomplete = {
        "ide": "test-ide-1",
        "release_date": "2026-01-01",
        "url": "https://example.com",
        "copilot_mentions": ["something"],
    }
    (data_root / "test-ide-1" / "incomplete.json").write_text(
        json.dumps(incomplete), encoding="utf-8"
    )
    
    result = build_search_index(config_path, data_root)
    # Should be empty since the release is missing 'version'
    assert len(result["records"]) == 0
