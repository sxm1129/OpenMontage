"""System capabilities: live view of the active evolution-seam backends."""

from fastapi import APIRouter

from app.interfaces import active_backends
from app.runner.stage_runner import LLM_MODEL

router = APIRouter()

# The curated set of models the wizard offers for each generation capability.
# Single source of truth — the wizard (web/app/dashboard/new/page.tsx) and the
# settings page (web/app/dashboard/settings/page.tsx) used to each hardcode
# their own independent copy of this same list, which could silently drift
# (confirmed by the deep quality review). Both now fetch this from
# /system/capabilities instead. Kept as a small curated list rather than the
# MaaS gateway's full live catalog (133+ models) since the wizard
# deliberately only surfaces a handful of vetted options, not every model
# the gateway happens to support.
MODEL_CATALOG = {
    "video_models": ["leapfast/ltx-2.3", "leapfast/wan2.2", "volcengine/doubao-seedance-2.0"],
    "image_models": ["leapfast/flux2", "gemini-3.1-flash-image-preview"],
    "tts_models": ["qwen3-tts-flash", "leapfast/indextts"],
}


@router.get("/capabilities")
async def capabilities():
    """Which storage/queue/auth adapter is live, plus the planned roadmap.

    Backs the settings page so it reports real state instead of static text.
    `llm_model` reflects MAAS_LLM_MODEL if set, so the settings page can't
    drift out of sync with the model actually driving the pipeline the way
    a hardcoded display string would. `model_catalog` serves the same
    purpose for the wizard's video/image/TTS model pickers.
    """
    return {"backends": active_backends(), "llm_model": LLM_MODEL, "model_catalog": MODEL_CATALOG}
