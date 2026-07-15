"""Library summary cache: time-derived staleness fixes (audit 2026-07-15, BUG-9).

The cache is invalidated by FILE changes, but `live` is TIME-derived — a
project that stops writing files never generates another change event, so a
cached live=True stayed live forever. And without watchfiles installed the
cache had no invalidation signal at all. `live` is now recomputed at request
time, a short TTL covers the no-watcher case, and deleted projects are
evicted.
"""

from __future__ import annotations

import time

import pytest

from backlot import server as server_mod


@pytest.fixture
def projects_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(server_mod, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(server_mod, "_watcher_active", True)
    server_mod._summary_cache.clear()
    yield tmp_path
    server_mod._summary_cache.clear()


def _summary(project_id: str, last_activity: float) -> dict:
    return {
        "project_id": project_id, "title": project_id,
        "pipeline_type": "cinematic", "has_pipeline_state": True,
        "poster": None, "live": True, "last_activity": last_activity,
        "active_stage": "assets", "awaiting_human": False,
        "stage_states": [], "completed_count": 3,
        "render_count": 0, "scene_count": 5,
    }


def test_live_decays_at_request_time_without_a_file_change(projects_dir):
    (projects_dir / "film").mkdir()
    # Cached while genuinely live... but the last activity is now 10 minutes
    # old and no file change ever invalidated the entry.
    stale_activity = time.time() - 600
    server_mod._summary_cache["film"] = (time.time(), _summary("film", stale_activity))

    [summary] = server_mod._cached_summaries()
    assert summary["live"] is False


def test_recent_activity_still_reads_live(projects_dir):
    (projects_dir / "film").mkdir()
    server_mod._summary_cache["film"] = (time.time(), _summary("film", time.time() - 30))

    [summary] = server_mod._cached_summaries()
    assert summary["live"] is True


def test_deleted_project_entries_are_evicted(projects_dir):
    (projects_dir / "kept").mkdir()
    server_mod._summary_cache["kept"] = (time.time(), _summary("kept", 0))
    server_mod._summary_cache["deleted"] = (time.time(), _summary("deleted", 0))

    server_mod._cached_summaries()
    assert "deleted" not in server_mod._summary_cache
    assert "kept" in server_mod._summary_cache


def test_no_watcher_falls_back_to_ttl(projects_dir, monkeypatch):
    (projects_dir / "film").mkdir()
    monkeypatch.setattr(server_mod, "_watcher_active", False)
    calls = []
    monkeypatch.setattr(
        server_mod, "summarize_project",
        lambda entry: calls.append(entry.name) or _summary(entry.name, time.time()),
    )
    # Expired entry (older than the TTL) must be re-derived, not served stale.
    server_mod._summary_cache["film"] = (
        time.time() - server_mod._NO_WATCHER_TTL_SECONDS - 1,
        _summary("film", 0),
    )
    server_mod._cached_summaries()
    assert calls == ["film"]
