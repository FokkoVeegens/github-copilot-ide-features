from pathlib import Path

import yaml


def test_pages_workflow_can_be_manually_triggered_without_deploying_other_branches():
    path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "deploy-pages.yml"
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert "workflow_dispatch" in workflow["on"]
    assert workflow["jobs"]["deploy"]["if"] == "github.ref == 'refs/heads/main'"
