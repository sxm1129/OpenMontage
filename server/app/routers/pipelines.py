"""Pipeline catalogue — lists the engine's runnable pipelines for the UI."""

import logging

from fastapi import APIRouter, HTTPException

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("")
async def list_pipelines_endpoint():
    """Every pipeline_defs/*.yaml the web platform can run, with UI metadata."""
    from app.pipeline_catalog import list_manifest_names, load_manifest

    out = []
    for name in list_manifest_names():
        try:
            m = load_manifest(name)
        except Exception:
            logger.warning("Failed to load pipeline manifest %r", name, exc_info=True)
            continue
        stages = m.get("stages", [])
        # A stage dict missing "name" (schema drift in a hand-edited manifest,
        # or the lenient raw-YAML fallback in load_manifest) must not raise
        # here — an unguarded KeyError on one malformed manifest would 500 the
        # ENTIRE /pipelines list, hiding every other, valid pipeline too.
        stage_names = []
        for s in stages:
            stage_name = s.get("name")
            if stage_name is None:
                logger.warning("Pipeline %r has a stage with no 'name': %r", name, s)
                continue
            stage_names.append(stage_name)
        out.append({
            "name": name,
            "description": (m.get("description") or "").strip(),
            "category": m.get("category"),
            "stability": m.get("stability"),
            "stages": stage_names,
            "approval_stages": [s.get("name") for s in stages if s.get("name") and s.get("human_approval_default")],
        })
    return {"pipelines": out}


@router.get("/{name}")
async def get_pipeline(name: str):
    from app.pipeline_catalog import load_manifest
    try:
        m = load_manifest(name)
    except FileNotFoundError:
        raise HTTPException(404, f"Pipeline '{name}' not found")
    except Exception as exc:
        raise HTTPException(400, f"Failed to load pipeline '{name}': {exc}")
    stages = m.get("stages", [])
    # Same guard as the list endpoint above: a stage dict missing "name" must
    # degrade gracefully (skip + log), not KeyError the whole request.
    stage_entries = []
    for s in stages:
        stage_name = s.get("name")
        if stage_name is None:
            logger.warning("Pipeline %r has a stage with no 'name': %r", name, s)
            continue
        stage_entries.append({"name": stage_name, "approval": bool(s.get("human_approval_default", False))})
    return {
        "name": name,
        "description": (m.get("description") or "").strip(),
        "category": m.get("category"),
        "stability": m.get("stability"),
        "stages": stage_entries,
    }
