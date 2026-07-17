"""_requests_deadline must not leak across threads (audit 2026-07-15, RISK-5).

Tools run in parallel threads (base_tool._EXECUTE_DEPTH is thread-local for
exactly that reason). The old implementation swapped the global requests.get
for the duration of a search, so every OTHER concurrently running tool had its
timeouts clamped to this search's budget — and could get a _DeadlineExceeded
raised at it, an exception type foreign to that tool.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import requests  # noqa: E402

from tools.video import direct_clip_search as dcs  # noqa: E402


class _FakeResponse:
    def iter_content(self, chunk_size=None):
        yield b"x"


def _install_fake_get(monkeypatch, seen: list):
    """Record the timeout every requests.get call ends up with."""
    def fake_get(url, **kwargs):
        seen.append(kwargs.get("timeout"))
        return _FakeResponse()

    # Reset the install-once latch so the wrapper re-wraps OUR fake.
    monkeypatch.setattr(dcs, "_deadline_get_installed", False, raising=False)
    monkeypatch.setattr(requests, "get", fake_get)


def test_other_threads_are_unaffected_while_a_search_holds_a_deadline(monkeypatch):
    seen: list = []
    _install_fake_get(monkeypatch, seen)

    other_timeout: list = []
    started = threading.Event()
    release = threading.Event()

    def other_tool():
        # A different tool, on its own thread, with its OWN generous timeout.
        started.wait(timeout=5)
        requests.get("http://example.invalid/a", timeout=120)
        other_timeout.append(seen[-1])
        release.set()

    t = threading.Thread(target=other_tool)
    t.start()
    with dcs._requests_deadline(time.time() + 1.0):
        started.set()
        release.wait(timeout=5)
    t.join(timeout=5)

    # The other thread's 120s timeout must survive untouched. Before the fix
    # it was clamped to this search's ~1s remaining budget.
    assert other_timeout == [120]


def test_the_searching_thread_still_gets_clamped(monkeypatch):
    seen: list = []
    _install_fake_get(monkeypatch, seen)

    with dcs._requests_deadline(time.time() + 1.0):
        requests.get("http://example.invalid/b", timeout=120)

    assert seen[-1] is not None and seen[-1] <= 1.0


def test_no_deadline_passes_through_unchanged(monkeypatch):
    seen: list = []
    _install_fake_get(monkeypatch, seen)
    dcs._install_deadline_get()  # wrapper live, but no deadline on this thread

    requests.get("http://example.invalid/c", timeout=42)
    assert seen[-1] == 42


def test_nested_deadlines_restore_the_outer_one(monkeypatch):
    seen: list = []
    _install_fake_get(monkeypatch, seen)

    outer = time.time() + 100.0
    with dcs._requests_deadline(outer):
        with dcs._requests_deadline(time.time() + 1.0):
            requests.get("http://example.invalid/inner", timeout=120)
            inner_timeout = seen[-1]
        requests.get("http://example.invalid/outer", timeout=120)
        outer_timeout = seen[-1]

    assert inner_timeout <= 1.0
    assert outer_timeout > 50  # outer budget restored, not left at the inner one
