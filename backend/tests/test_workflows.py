import json
from pathlib import Path

from app.services.workflow import validate_api_workflow


def test_bundled_api_workflows_are_well_formed():
    root = Path(__file__).parents[2] / "workflows" / "api"
    for path in sorted(root.glob("*.json")):
        workflow = json.loads(path.read_text(encoding="utf-8"))
        assert not validate_api_workflow(workflow), path.name
