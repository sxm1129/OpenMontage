"""Pipeline catalogue — lists the engine's runnable pipelines for the UI."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("")
async def list_pipelines_endpoint():
    """Every pipeline_defs/*.yaml the web platform can run, with UI metadata."""
    try:
        from lib.pipeline_loader import list_pipelines, load_pipeline
    except Exception:
        return {"pipelines": []}

    out = []
    for name in sorted(list_pipelines()):
        try:
            m = load_pipeline(name)
        except Exception:
            continue
        stages = m.get("stages", [])
        out.append({
            "name": name,
            "description": (m.get("description") or "").strip(),
            "category": m.get("category"),
            "stability": m.get("stability"),
            "stages": [s["name"] for s in stages],
            "approval_stages": [s["name"] for s in stages if s.get("human_approval_default")],
        })
    return {"pipelines": out}


@router.get("/{name}")
async def get_pipeline(name: str):
    try:
        from lib.pipeline_loader import load_pipeline
        m = load_pipeline(name)
    except FileNotFoundError:
        raise HTTPException(404, f"Pipeline '{name}' not found")
    except Exception as exc:
        raise HTTPException(400, f"Failed to load pipeline '{name}': {exc}")
    stages = m.get("stages", [])
    return {
        "name": name,
        "description": (m.get("description") or "").strip(),
        "category": m.get("category"),
        "stability": m.get("stability"),
        "stages": [
            {"name": s["name"], "approval": bool(s.get("human_approval_default", False))}
            for s in stages
        ],
    }
