"""Tests for scripts/common/github_releases.py."""
import pytest

from scripts.common.github_releases import paginate_github_releases


def test_paginate_github_releases_collects_all_pages():
    pages = [[{"tag_name": "v1.0.0"}], [{"tag_name": "v1.1.0"}], []]
    call_count = 0

    def fake_get_json(url, params=None):
        nonlocal call_count
        result = pages[call_count]
        call_count += 1
        return result

    releases = paginate_github_releases("https://api.github.com/repos/example/releases", get_json_fn=fake_get_json)
    assert len(releases) == 2
    assert releases[0]["tag_name"] == "v1.0.0"
    assert releases[1]["tag_name"] == "v1.1.0"


def test_paginate_github_releases_raises_for_non_list_response():
    def fake_get_json(url, params=None):
        return {"message": "bad response"}

    with pytest.raises(ValueError, match="Expected list"):
        paginate_github_releases(
            "https://api.github.com/repos/example/releases",
            get_json_fn=fake_get_json,
        )

