"""Beat grid extraction for music-synced editing (卡点).

Audit 2026-07-16, Wave 3 item 15: CapCut's 卡点 templates cut on the music's
beat grid — the single strongest "feels professionally edited" signal for
short-form video. This tool extracts that grid; the edit stage snaps cut
points to it (see lib/edit_timeline.beat_alignment_report).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class BeatGrid(BaseTool):
    name = "beat_grid"
    version = "0.1.0"
    tier = ToolTier.ENHANCED
    capability = "analysis"
    provider = "librosa"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["python:librosa"]
    install_instructions = "pip install librosa  # local beat/tempo analysis, no API key"
    agent_skills = ["ffmpeg"]

    capabilities = ["beat_detection", "tempo_estimation"]
    best_for = [
        "music beat grid for 卡点 (beat-synced) editing",
        "snapping cut points to the soundtrack",
        "tempo estimation for pacing decisions",
    ]

    input_schema = {
        "type": "object",
        "required": ["audio_path"],
        "properties": {
            "audio_path": {"type": "string", "description": "Music file to analyze"},
            "max_seconds": {
                "type": "number",
                "description": "Only analyze the first N seconds (default: full track)",
            },
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=50)
    idempotency_key_fields = ["audio_path", "max_seconds"]
    side_effects = []

    def get_status(self) -> ToolStatus:
        import importlib.util
        if importlib.util.find_spec("librosa") is not None:
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # local analysis

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        audio_path = Path(inputs.get("audio_path", ""))
        if not audio_path.exists():
            return ToolResult(success=False, error=f"Audio not found: {audio_path}")
        try:
            import librosa
        except ImportError:
            return ToolResult(
                success=False,
                error="librosa not installed. " + self.install_instructions,
            )

        try:
            duration = inputs.get("max_seconds")
            y, sr = librosa.load(str(audio_path), mono=True, duration=duration)
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beats = [round(float(t), 3) for t in librosa.frames_to_time(beat_frames, sr=sr)]
        except Exception as e:
            return ToolResult(success=False, error=f"Beat analysis failed: {e}")

        return ToolResult(
            success=True,
            data={
                "tempo_bpm": round(float(tempo), 1),
                "beats": beats,
                "beat_count": len(beats),
                "audio_path": str(audio_path),
                "usage": (
                    "Write into edit_decisions.music.beats and snap cut "
                    "in_seconds to the nearest beat (±80ms) — see "
                    "lib/edit_timeline.beat_alignment_report"
                ),
            },
            duration_seconds=round(time.time() - start, 2),
        )
