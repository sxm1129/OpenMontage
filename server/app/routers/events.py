"""SSE event stream: GET /jobs/{id}/events"""

import asyncio
import json
import time
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.store import job_store, TERMINAL_STATUSES

router = APIRouter()


@router.get("/{job_id}/events")
async def job_events(job_id: str, lastEventId: int = -1):
    async def generator():
        seq = lastEventId
        while True:
            events = job_store.get_events(job_id, after_seq=seq)
            for ev in events:
                seq = ev["seq"]
                data = json.dumps(ev, ensure_ascii=False)
                yield f"id: {seq}\ndata: {data}\n\n"
                if ev.get("type") in ("job_completed", "job_failed"):
                    return
            # Nothing new this tick: if the job is already terminal we've drained
            # everything, so close instead of looping forever (a reconnect after
            # completion would otherwise leak a connection). No second query —
            # an empty drain IS the "caught up" signal.
            if not events:
                job = job_store.get(job_id)
                if job is None:
                    return
                if job.get("status") in TERMINAL_STATUSES:
                    # The persisted event log may predate the terminal state —
                    # e.g. a job interrupted by a server restart mid-flight is
                    # marked failed without a job_failed event ever being
                    # appended (store._load_all has no live SSE client to push
                    # to at startup time). Without this, a (re)connecting client
                    # sees the stream close with no terminal event, its local
                    # `status` stays stuck at the last real event (e.g.
                    # "awaiting_approval"), and it reconnects forever. Synthesize
                    # the terminal event here so every client — live or
                    # reconnecting — always observes one.
                    seq += 1
                    ev_type = "job_completed" if job["status"] == "completed" else "job_failed"
                    synthetic = {
                        "seq": seq,
                        "type": ev_type,
                        "ts": time.time(),
                        "render_url": job.get("render_url"),
                        "message": "Job was interrupted (e.g. a server restart) before completion" if job.get("interrupted") else None,
                    }
                    yield f"id: {seq}\ndata: {json.dumps(synthetic, ensure_ascii=False)}\n\n"
                    return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
