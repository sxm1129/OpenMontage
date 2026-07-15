"""Approval-gate timeout race (audit 2026-07-15, BUG-13).

A decision landing in the instant between asyncio.wait_for timing out and the
caller processing the reject used to stay behind in _approval_results with
the asyncio.Event still set — the job's NEXT gate's wait_for_approval
returned immediately and consumed the dead gate's decision, silently
approving a different question than the one the human answered.
"""

from __future__ import annotations

import asyncio

import pytest


async def test_boundary_decision_cannot_approve_the_next_gate(store, monkeypatch):
    store.create("j1", {})
    store.update("j1", status="awaiting_approval")

    # The human's decision lands "at the boundary": recorded in the store,
    # but the waiter's asyncio.wait_for has already fired its TimeoutError.
    assert store.set_approval("j1", "approve", "late") is True

    real_wait_for = asyncio.wait_for

    async def timing_out_wait_for(awaitable, timeout):
        awaitable.close()  # avoid the un-awaited-coroutine warning
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", timing_out_wait_for)
    result = await store.wait_for_approval("j1", timeout=3600)
    assert result == {"action": "reject", "feedback": "Approval timed out"}
    monkeypatch.setattr(asyncio, "wait_for", real_wait_for)

    # Let set_approval's deferred call_soon_threadsafe(ev.set) fire — it can
    # land AFTER the timeout path's own cleanup, which is exactly why the
    # next gate must re-arm through begin_approval_gate.
    await asyncio.sleep(0)

    # The runner opens every gate through begin_approval_gate before flipping
    # status (stage_runner._pause_for_approval). The next gate must then time
    # out on its own merits — not instantly consume the dead gate's decision.
    store.begin_approval_gate("j1")
    store.update("j1", status="awaiting_approval")
    result2 = await store.wait_for_approval("j1", timeout=0.05)
    assert result2["feedback"] == "Approval timed out"


async def test_normal_approval_still_flows(store):
    store.create("j2", {})
    store.update("j2", status="awaiting_approval")

    async def approve_soon():
        await asyncio.sleep(0.01)
        store.set_approval("j2", "approve", "ok")

    task = asyncio.create_task(approve_soon())
    result = await store.wait_for_approval("j2", timeout=5)
    await task
    assert result == {"action": "approve", "feedback": "ok"}
