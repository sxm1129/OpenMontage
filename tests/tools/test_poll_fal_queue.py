"""poll_fal_queue: the bounded fal.ai queue poller (audit 2026-07-15, BUG-6).

kling/minimax/veo/seedance previously each carried an unbounded `while True`
poll loop — a job stuck in IN_QUEUE/IN_PROGRESS during a provider incident
hung the calling pipeline thread forever. The shared helper must terminate
on COMPLETED, FAILED/CANCELLED, and — critically — on deadline.
"""

from __future__ import annotations

import pytest

from tools.video import _shared


class _FakeClock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class _FakeResponse:
    def __init__(self, status: str):
        self._status = status

    def raise_for_status(self):
        pass

    def json(self):
        return {"status": self._status}


@pytest.fixture
def clock(monkeypatch):
    c = _FakeClock()
    monkeypatch.setattr(_shared.time, "time", c.time)
    monkeypatch.setattr(_shared.time, "sleep", c.sleep)
    return c


def _patch_statuses(monkeypatch, statuses):
    """requests.get yields the given statuses, repeating the last forever."""
    it = iter(statuses)
    last = statuses[-1]

    def fake_get(url, headers=None, timeout=None):
        return _FakeResponse(next(it, last))

    import requests
    monkeypatch.setattr(requests, "get", fake_get)


def test_completed_returns(clock, monkeypatch):
    _patch_statuses(monkeypatch, ["IN_QUEUE", "IN_PROGRESS", "COMPLETED"])
    assert _shared.poll_fal_queue("http://x/status", {}) is None


def test_failed_raises_with_provider_name(clock, monkeypatch):
    _patch_statuses(monkeypatch, ["FAILED"])
    with pytest.raises(RuntimeError, match="Kling"):
        _shared.poll_fal_queue("http://x/status", {}, provider="Kling")


def test_stuck_job_times_out_instead_of_hanging(clock, monkeypatch):
    # The regression case: the API keeps answering 200/IN_PROGRESS forever.
    _patch_statuses(monkeypatch, ["IN_PROGRESS"])
    with pytest.raises(TimeoutError, match="600s"):
        _shared.poll_fal_queue("http://x/status", {}, timeout=600)
    # And the fake clock proves it stopped at the deadline, not later.
    assert clock.now <= 600 + 30
