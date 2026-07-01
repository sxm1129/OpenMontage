"""In-memory job store for v1 (will be replaced by Postgres in M0-3)."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

# Cap the retained per-job event ring so a long-running job can't grow the
# buffer without bound. Reconnecting clients still get recent events; very old
# events beyond the cap are no longer replayable (acceptable for a live view).
MAX_EVENTS_PER_JOB = 5000

TERMINAL_STATUSES = {"completed", "failed"}


class JobStore:
    """Thread-safe in-memory store for job state and SSE event queues."""

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._events: dict[str, list[dict]] = {}
        self._event_seq: dict[str, int] = {}   # monotonic seq per job (survives buffer trim)
        self._approval_events: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str, data: dict) -> None:
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "current_stage": None,
                "stages": [],
                "completed_stages": [],
                "cost_cny": 0.0,
                "created_at": time.time(),
                **data,
            }
            self._events[job_id] = []
            self._event_seq[job_id] = 0
            self._approval_events[job_id] = asyncio.Event()

    def all(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._jobs)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(kwargs)

    def push_event(self, job_id: str, event: dict) -> None:
        with self._lock:
            if job_id not in self._events:
                return
            seq = self._event_seq.get(job_id, 0)
            self._event_seq[job_id] = seq + 1
            buf = self._events[job_id]
            buf.append({"seq": seq, **event})
            # Trim oldest while keeping seq values intact for replay filtering.
            if len(buf) > MAX_EVENTS_PER_JOB:
                del buf[: len(buf) - MAX_EVENTS_PER_JOB]

    def get_events(self, job_id: str, after_seq: int = -1) -> list[dict]:
        with self._lock:
            events = self._events.get(job_id, [])
            return [e for e in events if e["seq"] > after_seq]

    def set_approval(self, job_id: str, action: str, feedback: str) -> bool:
        job = self.get(job_id)
        if not job or job.get("status") != "awaiting_approval":
            return False
        with self._lock:
            self._approval_results[job_id] = {"action": action, "feedback": feedback}
        ev = self._approval_events.get(job_id)
        if ev:
            # Schedule event set on the loop where it was created
            try:
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(ev.set)
            except RuntimeError:
                ev.set()
        return True

    async def wait_for_approval(self, job_id: str, timeout: float = 3600.0) -> dict:
        ev = self._approval_events.get(job_id)
        if not ev:
            return {"action": "reject", "feedback": "Job not found"}
        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return {"action": "reject", "feedback": "Approval timed out"}
        ev.clear()
        with self._lock:
            return self._approval_results.pop(job_id, {"action": "reject", "feedback": ""})


job_store = JobStore()
