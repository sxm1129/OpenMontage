"""Job API: create, query, approve pipeline jobs."""

import asyncio
import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.store import job_store
from app.runner.stage_runner import run_pipeline_job
from app.interfaces import get_job_queue

OM_ROOT = Path(__file__).parent.parent.parent.parent

router = APIRouter()

# Stage names are always simple ASCII identifiers (CINEMATIC_STAGES / every
# pipeline_defs/*.yaml stage `name:`) — never containing a path separator.
_SAFE_STAGE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def _reject_path_traversal(v: str, field: str) -> str:
    # project_name is a free-text, human-entered field (real project names in
    # this codebase are often CJK, e.g. "小兔子电视") so it can't be locked to
    # an ASCII identifier pattern the way artifact/stage names can — but it's
    # still joined unsanitized into a filesystem path in multiple places
    # (this file's save_artifact, and stage_runner.py's project_dir), so "/"
    # and ".." must be blocked outright. Confirmed live: project_name=
    # "../../outside_target" let POST /jobs/{id}/artifact write a real file
    # entirely outside the projects/ tree.
    if "/" in v or "\\" in v or ".." in v:
        raise ValueError(f"{field} must not contain '/', '\\\\', or '..'")
    return v


class CreateJobRequest(BaseModel):
    project_name: str
    content_type: str          # e.g. "marketing_film"
    pipeline: str              # e.g. "cinematic"
    brand_info: dict[str, Any]
    options: dict[str, Any] = {}

    @field_validator("project_name")
    @classmethod
    def _validate_project_name(cls, v: str) -> str:
        return _reject_path_traversal(v, "project_name")


class ApproveStageRequest(BaseModel):
    action: str               # "approve" | "reject"
    feedback: str = ""


class SaveArtifactRequest(BaseModel):
    stage: str
    content: dict[str, Any]

    @field_validator("stage")
    @classmethod
    def _validate_stage(cls, v: str) -> str:
        if not _SAFE_STAGE_NAME.match(v):
            raise ValueError(
                "stage must contain only letters, numbers, underscores, and hyphens"
            )
        return v


@router.post("", status_code=201)
async def create_job(req: CreateJobRequest):
    job_id = str(uuid.uuid4())
    job_store.create(job_id, req.model_dump())
    get_job_queue().enqueue(run_pipeline_job, job_id, req.model_dump())
    return {"job_id": job_id, "status": "queued"}


@router.get("")
async def list_jobs():
    """Return all jobs, newest first."""
    jobs = list(job_store.all().values())
    jobs.sort(key=lambda j: j.get("created_at", 0), reverse=True)
    return {"jobs": jobs}


@router.get("/{job_id}")
async def get_job(job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/{job_id}/approve")
async def approve_stage(job_id: str, req: ApproveStageRequest):
    ok = job_store.set_approval(job_id, req.action, req.feedback)
    if not ok:
        raise HTTPException(404, "Job not found or not awaiting approval")
    return {"job_id": job_id, "action": req.action}


@router.post("/{job_id}/artifact")
async def save_artifact(job_id: str, req: SaveArtifactRequest):
    """Overwrite a stage artifact (used by inline edit in the UI)."""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    project_name = job.get("project_name", job_id)
    artifacts_dir = OM_ROOT / "projects" / project_name / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out = artifacts_dir / f"{req.stage}.json"
    out.write_text(json.dumps(req.content, ensure_ascii=False, indent=2))
    return {"saved": req.stage, "path": str(out)}


@router.post("/{job_id}/retry")
async def retry_job(job_id: str):
    """Re-run a failed job — resumes from completed_stages.

    Only "failed" is retryable. A live "running" job must NEVER be retried:
    the persistence layer already flips any job that was mid-flight when the
    process died to "failed" on startup (JobStore._load_all), so a genuinely
    orphaned job always shows up as "failed", never stuck at "running". Prior
    to this fix "running" was also accepted (meant for that orphaned case),
    but that let a still-live job be retried too — enqueuing a SECOND
    concurrent run_pipeline_job for the same job_id, racing the first one and
    corrupting whichever artifact each happened to write last.
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.get("status") != "failed":
        raise HTTPException(400, "Only failed jobs can be retried")
    job_store.update(job_id, status="queued")
    get_job_queue().enqueue(run_pipeline_job, job_id, {
        "project_name": job.get("project_name", job_id),
        "content_type": job.get("content_type", "marketing_film"),
        "pipeline": job.get("pipeline", "cinematic"),
        "brand_info": job.get("brand_info", {}),
        "options": job.get("options", {}),
    })
    return {"job_id": job_id, "status": "queued"}
