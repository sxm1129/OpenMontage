"""MaasBaseTool._poll_job — the shared MaaS submit→poll loop.

maas_video/maas_tts/maas_image each carried a hand-copied deadline +
transient-error-budget loop. The helper unifies the LOOP only: timeouts
(600/60/300s), intervals, success statuses and error wording stay per-tool —
they are model-specific and doc-cited, and the strings are what operators
read (audit 2026-07-15, structural item 3).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.maas_base import (  # noqa: E402
    MAX_POLL_ERRORS,
    MaasBaseTool,
    MaasJobFailed,
    MaasPollTimeout,
    MaasPollUnreachable,
)


class _Resp:
    def __init__(self, payload, raise_exc=None):
        self._payload = payload
        self._raise = raise_exc

    def raise_for_status(self):
        if self._raise:
            raise self._raise

    def json(self):
        return self._payload


@pytest.fixture
def clock(monkeypatch):
    """Fake time: _poll_job sleeps, so the fake clock advances on sleep."""
    state = {"now": 1000.0}
    monkeypatch.setattr("tools.maas_base.time.time", lambda: state["now"])
    return state


def _patch_get(monkeypatch, responses, calls=None):
    # Resolve `requests` at call time, not module-import time: a contract
    # test drops it from sys.modules to prove lazy importing, so a stale
    # module-level binding would patch an object _poll_job never sees.
    import requests

    it = iter(responses)

    def fake_get(url, headers=None, timeout=None):
        if calls is not None:
            calls.append(url)
        item = next(it, responses[-1])
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(requests, "get", fake_get)


def _sleep_for(clock):
    def _sleep(seconds):
        clock["now"] += seconds
    return _sleep


def test_returns_final_payload_on_success(clock, monkeypatch):
    _patch_get(monkeypatch, [
        _Resp({"status": "processing"}),
        _Resp({"status": "succeeded", "url": "https://x/out.mp4"}),
    ])
    payload = MaasBaseTool._poll_job(
        "http://gw/jobs/1", {}, deadline=clock["now"] + 60, interval=2,
        sleep=_sleep_for(clock),
    )
    # image needs the final payload (it reads the result off the poll body).
    assert payload["url"] == "https://x/out.mp4"


def test_sleeps_before_first_poll(clock, monkeypatch):
    import requests

    order = []
    monkeypatch.setattr(requests, "get", lambda *a, **k: (
        order.append("poll"), _Resp({"status": "succeeded"}))[1])

    def sleep(seconds):
        order.append("sleep")
        clock["now"] += seconds

    MaasBaseTool._poll_job("http://gw/1", {}, deadline=clock["now"] + 60,
                           interval=2, sleep=sleep)
    # A job is never ready the instant it is submitted.
    assert order == ["sleep", "poll"]


def test_custom_success_statuses(clock, monkeypatch):
    # maas_image accepts "completed" too; video/tts must not.
    _patch_get(monkeypatch, [_Resp({"status": "completed"})])
    payload = MaasBaseTool._poll_job(
        "http://gw/1", {}, deadline=clock["now"] + 60, interval=1,
        success_statuses=("succeeded", "completed"), sleep=_sleep_for(clock),
    )
    assert payload["status"] == "completed"


def test_unrecognized_success_status_keeps_polling_until_timeout(clock, monkeypatch):
    _patch_get(monkeypatch, [_Resp({"status": "completed"})])
    with pytest.raises(MaasPollTimeout):
        MaasBaseTool._poll_job(
            "http://gw/1", {}, deadline=clock["now"] + 10, interval=1,
            sleep=_sleep_for(clock),  # default success = ("succeeded",)
        )


def test_terminal_failure_carries_status_and_payload(clock, monkeypatch):
    _patch_get(monkeypatch, [_Resp({"status": "failed", "error": "OOM"})])
    with pytest.raises(MaasJobFailed) as exc:
        MaasBaseTool._poll_job("http://gw/1", {}, deadline=clock["now"] + 60,
                               interval=1, sleep=_sleep_for(clock))
    # Each tool words its own message off these.
    assert exc.value.status == "failed"
    assert exc.value.payload["error"] == "OOM"


def test_transient_blips_are_tolerated(clock, monkeypatch):
    import requests

    # The job is already billed — a 502 must not abandon it.
    _patch_get(monkeypatch, [
        requests.ConnectionError("reset"),
        _Resp({"status": "processing"}),
        _Resp({"status": "succeeded"}),
    ])
    payload = MaasBaseTool._poll_job("http://gw/1", {}, deadline=clock["now"] + 60,
                                     interval=1, sleep=_sleep_for(clock))
    assert payload["status"] == "succeeded"


def test_error_budget_caps_at_max_poll_errors(clock, monkeypatch):
    import requests

    calls = []
    _patch_get(monkeypatch, [requests.ConnectionError("down")] * 20, calls)
    with pytest.raises(MaasPollUnreachable) as exc:
        MaasBaseTool._poll_job("http://gw/1", {}, deadline=clock["now"] + 3600,
                               interval=1, sleep=_sleep_for(clock))
    assert exc.value.attempts == MAX_POLL_ERRORS
    # Exactly 5 polls — pinned by test_maas_tts_async_indextts too.
    assert len(calls) == MAX_POLL_ERRORS


def test_error_budget_resets_after_a_good_poll(clock, monkeypatch):
    import requests

    # 4 blips, one success, 4 more blips → still under the cap, no raise.
    _patch_get(monkeypatch, [
        *[requests.ConnectionError("x")] * 4,
        _Resp({"status": "processing"}),
        *[requests.ConnectionError("x")] * 4,
        _Resp({"status": "succeeded"}),
    ])
    payload = MaasBaseTool._poll_job("http://gw/1", {}, deadline=clock["now"] + 3600,
                                     interval=1, sleep=_sleep_for(clock))
    assert payload["status"] == "succeeded"


def test_timeout_raises_when_deadline_passes(clock, monkeypatch):
    _patch_get(monkeypatch, [_Resp({"status": "processing"})])
    with pytest.raises(MaasPollTimeout):
        MaasBaseTool._poll_job("http://gw/1", {}, deadline=clock["now"] + 5,
                               interval=1, sleep=_sleep_for(clock))
