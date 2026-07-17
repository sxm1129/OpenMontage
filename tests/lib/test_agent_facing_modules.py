"""Contract tests for the lib/ modules that only AGENTS call.

These three have no Python importers — they are invoked via ad-hoc `python -c`
by skill markdown, which makes them live API surface with (until now) zero CI
coverage (audit 2026-07-15, S-3). That is precisely the condition that let
BUG-1 (checkpoint's hardcoded stage→artifact map) drift away from reality
unnoticed: nothing failed when the contract moved.

The skills that depend on them:
  - skills/pipelines/screen-demo/asset-director.md:21 — verify_scene_pacing's
    assert_alignment "must pass before render" (a MANDATORY gate)
  - skills/pipelines/explainer/asset-director.md:115 — shot_prompt_builder
  - skills/meta/capability-extension.md:59 + animation/proposal-director.md —
    playbook_generator

Each test pins the call shape those skills document, so renaming or
re-signaturing one of these breaks CI instead of breaking an agent mid-run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib import shot_prompt_builder, verify_scene_pacing  # noqa: E402
from lib.playbook_generator import generate_playbook, list_playbooks  # noqa: E402
from styles.playbook_loader import validate_playbook  # noqa: E402


def _steps() -> list[dict]:
    """TerminalScene-shaped steps, as screen-demo's asset-director authors."""
    return [
        {"kind": "cmd", "text": "npm install", "pause": 1.0},
        {"kind": "out", "text": "added 42 packages", "pause": 1.0},
        {"kind": "cmd", "text": "npm run build", "pause": 1.0},
    ]


class TestVerifyScenePacing:
    """The screen-demo gate: narration cues must land on visual landmarks."""

    def test_trace_returns_a_landmark_per_step(self):
        landmarks = verify_scene_pacing.trace(_steps(), scene_start=0.0, quiet=True)
        assert len(landmarks) >= len(_steps())
        assert all(hasattr(lm, "video_time") and hasattr(lm, "kind") for lm in landmarks)

    def test_landmarks_advance_monotonically(self):
        landmarks = verify_scene_pacing.trace(_steps(), scene_start=5.0, quiet=True)
        times = [lm.video_time for lm in landmarks]
        assert times == sorted(times)
        assert times[0] >= 5.0, "scene_start must offset the timeline"

    def test_aligned_cues_pass(self):
        steps = _steps()
        landmarks = verify_scene_pacing.trace(steps, scene_start=0.0, quiet=True)
        cues = [(landmarks[0].video_time, "install starts")]
        scene_end = landmarks[-1].video_time + 0.5
        # Must not raise.
        verify_scene_pacing.assert_alignment(
            steps, scene_start=0.0, scene_end=scene_end, narration_cues=cues
        )

    def test_a_cue_with_no_nearby_visual_fails(self):
        # This is the gate's whole purpose: narration talking about something
        # the screen never shows.
        with pytest.raises(AssertionError, match="no visual"):
            verify_scene_pacing.assert_alignment(
                _steps(),
                scene_start=0.0,
                scene_end=45.5,
                narration_cues=[(45.0, "the build finishes")],
                tolerance=1.0,
            )

    def test_steps_overflowing_the_scene_fail(self):
        with pytest.raises(AssertionError):
            verify_scene_pacing.assert_alignment(
                _steps(), scene_start=0.0, scene_end=0.5, narration_cues=[]
            )

    def test_steps_underfilling_the_scene_fail(self):
        # The other half of the gate: steps that end long before the scene
        # does leave the last frame frozen on screen.
        with pytest.raises(AssertionError, match="underfill"):
            verify_scene_pacing.assert_alignment(
                _steps(), scene_start=0.0, scene_end=60.0, narration_cues=[]
            )


class TestShotPromptBuilder:
    def test_builds_a_prompt_from_a_scene(self):
        prompt = shot_prompt_builder.build_shot_prompt(
            {"description": "a robot vacuum glides across oak flooring"}
        )
        assert isinstance(prompt, str) and prompt.strip()
        assert "robot vacuum" in prompt

    def test_style_context_adapts_rather_than_pasting_a_prefix(self):
        # Deliberate design: the playbook's style is ADAPTED (aesthetic/mood),
        # never pasted verbatim — a fixed prefix on every shot is what makes a
        # video's imagery look identical. The docstring used to advertise a
        # `generation_prefix` key that was never read.
        prompt = shot_prompt_builder.build_shot_prompt(
            {"description": "a robot vacuum on oak flooring"},
            {"mood": "warm and domestic", "visual_language": {"aesthetic": "editorial product photography"}},
        )
        assert "editorial product photography" in prompt

    def test_mood_is_the_fallback_when_no_aesthetic(self):
        prompt = shot_prompt_builder.build_shot_prompt(
            {"description": "a robot vacuum"}, {"mood": "warm and domestic"}
        )
        assert "warm and domestic" in prompt

    def test_batch_returns_one_prompt_per_scene(self):
        scenes = [{"description": "shot one"}, {"description": "shot two"}]
        prompts = shot_prompt_builder.build_batch_prompts(scenes)
        assert len(prompts) == 2


class TestPlaybookGenerator:
    def test_lists_the_real_playbooks(self):
        names = list_playbooks()
        assert "clean-professional" in names

    def test_generated_playbook_validates_against_the_schema(self):
        # The whole point: capability-extension.md tells agents to generate a
        # playbook with this. If the output doesn't satisfy playbook.schema,
        # load_playbook() rejects it later and the agent is stuck.
        pb = generate_playbook(
            "test-generated",
            {"mood": "warm", "tone": "cinematic", "pace": "moderate"},
        )
        validate_playbook(pb)  # raises on any schema violation
        assert pb["identity"]["name"]

    def test_context_pace_reaches_identity(self):
        pb = generate_playbook("t", {"mood": "calm", "tone": "educational", "pace": "slow"})
        assert pb["identity"]["pace"] == "slow"

    def test_base_playbook_is_used_as_the_starting_point(self):
        pb = generate_playbook(
            "derived", {"mood": "warm", "tone": "corporate"}, base_playbook="clean-professional"
        )
        validate_playbook(pb)
        assert pb["identity"]["name"] != "clean-professional"
