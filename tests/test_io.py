"""Tests for scripts.common.io module."""
import json
import pathlib
import tempfile

from scripts.common.io import generate_ide_index, write_release


def test_write_release_creates_file() -> None:
    """Test that write_release creates a new JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = pathlib.Path(tmpdir)
        release = {
            "ide": "test-ide",
            "version": "1.0.0",
            "release_date": "2026-01-01",
            "title": "Test Release",
            "url": "https://example.com/release",
        }
        
        result = write_release(data_dir, release)
        
        assert result is True
        assert (data_dir / "1.0.0.json").exists()
        
        # Verify file contents
        with (data_dir / "1.0.0.json").open() as f:
            data = json.load(f)
        
        assert data["version"] == "1.0.0"
        assert data["release_date"] == "2026-01-01"
        assert "fetched_at" in data
        assert data["schema_version"] == 1


def test_write_release_idempotent() -> None:
    """Test that write_release never overwrites an existing file.

    This behaviour is load-bearing for historical backfills: some IDE data
    files (e.g. the Xcode 0.31-0.46 era) were written by a one-time manual
    backfill script that enriched them with correct release dates and
    per-release changelog notes sourced from CopilotForXcode/CHANGELOG.md.
    Those files must NOT be overwritten by future scheduled workflow runs; otherwise manual corrections
    (and any future regressions in fetcher output) could be lost.

    If this test fails after a change to write_release, verify that the
    idempotency guarantee is still upheld before merging, otherwise the
    next workflow run will silently discard manually backfilled data.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = pathlib.Path(tmpdir)
        release = {
            "version": "1.0.0",
            "release_date": "2026-01-01",
        }

        # First write should succeed
        result1 = write_release(data_dir, release)
        assert result1 is True

        # Second write must be skipped — the file on disk must not change
        original_content = (data_dir / "1.0.0.json").read_text(encoding="utf-8")
        result2 = write_release(data_dir, {**release, "release_date": "2099-12-31"})
        assert result2 is False
        assert (data_dir / "1.0.0.json").read_text(encoding="utf-8") == original_content


def test_generate_ide_index_creates_index() -> None:
    """Test that generate_ide_index creates an index.json file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = pathlib.Path(tmpdir)
        
        # Create sample release files
        releases = [
            {"version": "1.0.0", "release_date": "2026-01-01"},
            {"version": "1.1.0", "release_date": "2026-01-15"},
            {"version": "1.0.1", "release_date": "2026-01-08"},
        ]
        
        for release in releases:
            write_release(data_dir, release)
        
        # Generate index
        generate_ide_index(data_dir)
        
        # Verify index exists and has correct content
        index_path = data_dir / "index.json"
        assert index_path.exists()
        
        with index_path.open() as f:
            index = json.load(f)
        
        assert len(index) == 3
        assert index[0]["version"] == "1.1.0"  # newest first
        assert index[1]["version"] == "1.0.1"
        assert index[2]["version"] == "1.0.0"  # oldest last


def test_generate_ide_index_sorted_by_release_date() -> None:
    """Test that index entries are sorted by release_date descending."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = pathlib.Path(tmpdir)
        
        # Create releases with intentionally out-of-order versions
        releases = [
            {"version": "2.0.0", "release_date": "2025-06-01"},
            {"version": "1.5.0", "release_date": "2026-02-01"},
            {"version": "1.2.0", "release_date": "2026-01-15"},
        ]
        
        for release in releases:
            write_release(data_dir, release)
        
        generate_ide_index(data_dir)
        
        with (data_dir / "index.json").open() as f:
            index = json.load(f)
        
        # Verify sorted by release_date descending (newest first)
        assert index[0]["release_date"] == "2026-02-01"
        assert index[1]["release_date"] == "2026-01-15"
        assert index[2]["release_date"] == "2025-06-01"


def test_generate_ide_index_includes_filename() -> None:
    """Test that index entries include the correct filename."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = pathlib.Path(tmpdir)
        
        release = {"version": "1.5.0", "release_date": "2026-01-01"}
        write_release(data_dir, release)
        generate_ide_index(data_dir)
        
        with (data_dir / "index.json").open() as f:
            index = json.load(f)
        
        assert index[0]["filename"] == "1.5.0.json"


def test_generate_ide_index_skips_invalid_files() -> None:
    """Test that generate_ide_index skips files without required fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = pathlib.Path(tmpdir)
        
        # Valid release
        write_release(data_dir, {"version": "1.0.0", "release_date": "2026-01-01"})
        
        # Invalid release (missing release_date)
        invalid_path = data_dir / "invalid.json"
        invalid_path.write_text(json.dumps({"version": "2.0.0"}))
        
        generate_ide_index(data_dir)
        
        with (data_dir / "index.json").open() as f:
            index = json.load(f)
        
        # Only the valid release should be in the index
        assert len(index) == 1
        assert index[0]["version"] == "1.0.0"


def test_generate_ide_index_handles_empty_directory() -> None:
    """Test that generate_ide_index handles directories with no releases."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = pathlib.Path(tmpdir)
        
        # Should not raise and should create empty index
        generate_ide_index(data_dir)
        
        # Empty index should be created for empty directory
        with (data_dir / "index.json").open() as f:
            index = json.load(f)
        assert index == []


def test_generate_ide_index_handles_nonexistent_directory() -> None:
    """Test that generate_ide_index handles nonexistent directories gracefully."""
    nonexistent_dir = pathlib.Path("/nonexistent/path/that/does/not/exist")
    
    # Should not raise an exception
    generate_ide_index(nonexistent_dir)
