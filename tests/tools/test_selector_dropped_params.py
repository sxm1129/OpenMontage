"""Wave-3 item 18: selectors surface silently-dropped expressive params.

The selector schemas advertise pitch/instructions/voice_performance and
forward them wholesale; providers read only their own input_schema fields.
The mismatch used to vanish — the script stage's voice performance plan had
no mechanical path into the audio and nothing reported that. The provider's
input_schema is the support matrix; the base selector now reports what a
chosen provider will ignore.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolResult, ToolStatus  # noqa: E402
from tools.selector_base import SelectorBase  # noqa: E402


class FakeProvider(BaseTool):
    name = "fake_tts"
    version = "0.0.1"
    capability = "fake_capability"
    provider = "fake"
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "speed": {"type": "number"},
        },
    }

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def execute(self, inputs):
        return ToolResult(success=True, data={"echo": True})


class FakeSelector(SelectorBase):
    name = "fake_selector"
    version = "0.0.1"
    capability = "fake_capability"
    _prompt_key = "text"

    def _providers(self):
        return [FakeProvider()]


def test_unsupported_params_are_reported():
    result = FakeSelector().execute({
        "text": "hello",
        "speed": 1.1,
        "pitch": 4,                     # not in provider schema → dropped
        "voice_performance": {"pace": "slow"},  # dropped
        "preferred_provider": "fake",   # selector control key → ignored
    })
    assert result.success is True
    assert result.data["dropped_params"] == ["pitch", "voice_performance"]
    assert "no effect" in result.data["dropped_params_note"].lower()


def test_supported_request_reports_nothing():
    result = FakeSelector().execute({"text": "hello", "speed": 1.0})
    assert result.success is True
    assert "dropped_params" not in result.data


def test_empty_values_do_not_count_as_dropped():
    result = FakeSelector().execute({"text": "hello", "instructions": ""})
    assert result.success is True
    assert "dropped_params" not in result.data
