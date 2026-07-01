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


def test_all_manifests_listed_even_with_schema_drift():
    # screen-demo / documentary-montage fail strict schema validation; the
    # lenient loader must still surface them (previously silently dropped, and
    # selecting them fell back to cinematic).
    from app.pipeline_catalog import list_manifest_names
    listed = {p["name"] for p in client.get("/pipelines").json()["pipelines"]}
    assert listed == set(list_manifest_names())
    assert {"screen-demo", "documentary-montage"} <= listed


def test_drifted_pipeline_resolves_own_stages():
    sd = [s["name"] for s in _resolve_stages("screen-demo")]
    assert sd and sd != [s["name"] for s in CINEMATIC_STAGES]


def test_pipeline_detail_endpoint_and_404():
    ok = client.get("/pipelines/cinematic")
    assert ok.status_code == 200
    body = ok.json()
    assert body["name"] == "cinematic"
    assert all("name" in s and "approval" in s for s in body["stages"])
    # a schema-drifted manifest still returns detail (not 400)
    assert client.get("/pipelines/screen-demo").status_code == 200
    assert client.get("/pipelines/definitely-not-real").status_code == 404
