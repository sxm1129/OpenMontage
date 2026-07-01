"""Dynamic pipeline resolution + the /pipelines catalogue endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.runner.stage_runner import _resolve_stages, CINEMATIC_STAGES, PIPELINE_MAP


client = TestClient(main.app)


def test_override_wins_over_manifest():
    # cinematic/marketing_film are explicit overrides → the hardcoded stages
    names = [s["name"] for s in _resolve_stages("cinematic")]
    assert names == [s["name"] for s in CINEMATIC_STAGES]
    assert _resolve_stages("marketing_film") is PIPELINE_MAP["marketing_film"]


def test_dynamic_manifest_load():
    stages = _resolve_stages("animated-explainer")
    names = [s["name"] for s in stages]
    assert "research" in names and "compose" in names
    # skill paths are normalized to skills/....md
    assert all(s["skill"].startswith("skills/") and s["skill"].endswith(".md")
               for s in stages if s["skill"])
    # manifest-declared approval gates survive
    assert any(s["approval"] for s in stages)


def test_unknown_pipeline_falls_back_to_cinematic():
    names = [s["name"] for s in _resolve_stages("no-such-pipeline-xyz")]
    assert names == [s["name"] for s in CINEMATIC_STAGES]


def test_pipelines_list_endpoint():
    r = client.get("/pipelines")
    assert r.status_code == 200
    pipes = r.json()["pipelines"]
    assert len(pipes) >= 5
    names = {p["name"] for p in pipes}
    assert "cinematic" in names and "animated-explainer" in names
    sample = next(p for p in pipes if p["name"] == "cinematic")
    for key in ("description", "category", "stability", "stages", "approval_stages"):
        assert key in sample
    assert isinstance(sample["stages"], list) and sample["stages"]


def test_pipeline_detail_endpoint_and_404():
    ok = client.get("/pipelines/cinematic")
    assert ok.status_code == 200
    body = ok.json()
    assert body["name"] == "cinematic"
    assert all("name" in s and "approval" in s for s in body["stages"])
    assert client.get("/pipelines/definitely-not-real").status_code == 404
