"""Pipeline manifest access for the web platform.

Wraps the engine's strict loader but degrades to a lenient raw YAML read when a
manifest fails schema validation (some engine manifests have drifted from the
schema — e.g. a category value or an extra key). This keeps every pipeline in
pipeline_defs/ runnable and listable from the web platform without editing the
engine's manifests, while still preferring strict validation when it passes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# server/app/pipeline_catalog.py → repo root is three parents up.
OM_ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE_DEFS_DIR = OM_ROOT / "pipeline_defs"


def list_manifest_names() -> list[str]:
    if not PIPELINE_DEFS_DIR.exists():
        return []
    return sorted(p.stem for p in PIPELINE_DEFS_DIR.glob("*.yaml"))


def load_manifest(name: str) -> dict[str, Any]:
    """Return a manifest dict. Strict validation first, lenient YAML on drift.

    Raises FileNotFoundError if the manifest file genuinely doesn't exist.
    """
    path = PIPELINE_DEFS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Pipeline manifest not found: {path}")
    try:
        from lib.pipeline_loader import load_pipeline
        return load_pipeline(name)
    except FileNotFoundError:
        raise
    except Exception:
        # Schema drift or a loader hiccup — fall back to a raw read so the
        # pipeline stays usable. Validation is best-effort, not a gate here.
        import yaml
        return yaml.safe_load(path.read_text())
