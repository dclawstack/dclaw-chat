"""Deploy-manifest assertions (GAP v2 T3-05).

The prod fail-closed guard (refuse to boot when DEBUG=true) only fires when
ENVIRONMENT=production — these tests pin that every deploy path actually sets
it, so the guard can never silently become inert again.
"""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_compose_backend_sets_environment_production():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())
    env = compose["services"]["backend"]["environment"]
    assert "ENVIRONMENT" in env
    # default must be production (fail-closed), override only by explicit env
    assert "production" in env["ENVIRONMENT"]


def test_helm_backend_sets_environment_production():
    values = yaml.safe_load(
        (REPO_ROOT / "helm" / "dclaw-chat" / "values.yaml").read_text()
    )
    env_vars = {e["name"]: e.get("value") for e in values["backend"]["env"]}
    assert env_vars.get("ENVIRONMENT") == "production"
