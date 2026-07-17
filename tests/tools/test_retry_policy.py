"""retry_policy is now honored (audit 2026-07-15, S-5).

56 tools declared a policy and NOTHING read it — `max_retries=2,
retryable_errors=["rate_limit", "timeout"]` was a promise to every reader (and
to any agent reading get_info()) that no code kept.

The load-bearing rule: a PAID call never auto-retries a timeout. rate_limit
means the provider refused the request — nothing ran, nothing was billed. A
timeout means we don't know: kling/veo/seedance raise TimeoutError from
poll_fal_queue at 600s precisely while the queue job is still alive and
billing, so retrying submits a SECOND paid job.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import (  # noqa: E402
    BaseTool,
    RetryPolicy,
    ToolResult,
    ToolStatus,
)


class _Tool(BaseTool):
    """Configurable stand-in: a scripted sequence of outcomes."""

    name = "retry_probe"
    version = "0.0.1"
    capability = "test"
    provider = "test"
    retry_policy = RetryPolicy(max_retries=2, backoff_seconds=0, retryable_errors=["rate_limit", "timeout"])

    def __init__(self, outcomes, cost=0.0):
        super().__init__()
        self.outcomes = list(outcomes)
        self.calls = 0
        self._cost = cost

    def estimate_cost(self, inputs):
        return self._cost

    def get_status(self):
        return ToolStatus.AVAILABLE

    def execute(self, inputs):
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else ToolResult(success=True)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _fail(msg):
    return ToolResult(success=False, error=msg)


class TestFreeTools:
    def test_retries_a_declared_error_and_succeeds(self):
        t = _Tool([_fail("rate_limit exceeded"), ToolResult(success=True)])
        r = t.execute({})
        assert r.success is True
        assert t.calls == 2

    def test_free_tool_retries_timeout(self):
        # Retrying a local/free tool costs nothing.
        t = _Tool([_fail("connection timeout"), ToolResult(success=True)], cost=0.0)
        assert t.execute({}).success is True
        assert t.calls == 2

    def test_gives_up_after_max_retries(self):
        t = _Tool([_fail("rate_limit"), _fail("rate_limit"), _fail("rate_limit")])
        r = t.execute({})
        assert r.success is False
        assert t.calls == 3  # 1 initial + max_retries=2

    def test_undeclared_error_is_not_retried(self):
        t = _Tool([_fail("invalid api key")])
        assert t.execute({}).success is False
        assert t.calls == 1

    def test_retryable_exception_is_retried_then_re_raised(self):
        t = _Tool([TimeoutError("timeout"), TimeoutError("timeout"), TimeoutError("timeout")])
        with pytest.raises(TimeoutError):
            t.execute({})
        assert t.calls == 3

    def test_unretryable_exception_propagates_immediately(self):
        t = _Tool([ValueError("bad input")])
        with pytest.raises(ValueError):
            t.execute({})
        assert t.calls == 1


class TestPaidTools:
    """The money rule."""

    def test_paid_tool_NEVER_retries_a_timeout(self):
        # The double-billing case: the queue job may still be running.
        t = _Tool([_fail("Kling queue job still not finished after 600s")], cost=0.30)
        r = t.execute({})
        assert r.success is False
        assert t.calls == 1, "a paid timeout must not be re-submitted"

    def test_paid_tool_still_retries_rate_limit(self):
        # Provider refused the request — nothing ran, nothing billed.
        t = _Tool([_fail("rate_limit exceeded"), ToolResult(success=True)], cost=0.30)
        assert t.execute({}).success is True
        assert t.calls == 2

    def test_paid_timeout_exception_is_not_retried(self):
        t = _Tool([TimeoutError("queue job timed out")], cost=0.20)
        with pytest.raises(TimeoutError):
            t.execute({})
        assert t.calls == 1

    def test_estimate_cost_blowing_up_is_treated_as_paid(self):
        # Fail closed: guessing "free" would be the expensive mistake.
        class _Exploding(_Tool):
            def estimate_cost(self, inputs):
                raise ValueError("cannot parse duration '8.0'")

        t = _Exploding([_fail("timeout")])
        assert t.execute({}).success is False
        assert t.calls == 1


class TestDefaults:
    def test_a_tool_declaring_nothing_never_retries(self):
        class _NoPolicy(_Tool):
            retry_policy = RetryPolicy()  # max_retries=0 — the default

        t = _NoPolicy([_fail("rate_limit"), ToolResult(success=True)])
        assert t.execute({}).success is False
        assert t.calls == 1

    def test_success_first_time_runs_once(self):
        t = _Tool([ToolResult(success=True)])
        assert t.execute({}).success is True
        assert t.calls == 1


class TestRealToolDeclarations:
    def test_paid_video_tools_declare_rate_limit_and_timeout(self):
        # Pins the situation this design exists for: they all ask for both,
        # and only rate_limit may be honored.
        from tools.video.kling_video import KlingVideo

        errs = [e.lower() for e in KlingVideo.retry_policy.retryable_errors]
        assert "rate_limit" in errs and "timeout" in errs
        assert KlingVideo.retry_policy.max_retries > 0
