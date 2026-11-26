from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize("event", ["pull_request", "push"])
def test_ci_skips_only_data_changes(event):
    path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert workflow["on"][event]["paths-ignore"] == ["data/**"]
    assert "paths" not in workflow["on"][event]
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert "workflow_dispatch" in workflow["on"]


def test_pages_workflow_can_be_manually_triggered_without_deploying_other_branches():
    path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "deploy-pages.yml"
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert "workflow_dispatch" in workflow["on"]
    assert workflow["on"]["schedule"] == [{"cron": "0 23 * * *"}]
    assert workflow["jobs"]["deploy"]["if"] == "github.ref == 'refs/heads/main'"
