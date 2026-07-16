"""Wave-3 quality mechanisms (audit 2026-07-16, items 15/17 + M6).

Beat alignment (卡点), cross-shot asset consistency, and video_stitch's
per-boundary transition mapping.
"""

from __future__ import annotations

from pathlib import Path

from lib.asset_consistency import check_asset_consistency
from lib.edit_timeline import beat_alignment_report
from tools.video.video_stitch import VideoStitch


class TestBeatAlignment:
    BEATS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

    def test_on_beat_cuts_pass(self):
        cuts = [
            {"id": "a", "in_seconds": 0, "out_seconds": 1.0},
            {"id": "b", "in_seconds": 1.02, "out_seconds": 2.0},  # 20ms off — inside ±80ms
            {"id": "c", "in_seconds": 2.5, "out_seconds": 3.0},
        ]
        report = beat_alignment_report(cuts, self.BEATS)
        assert report["checked"] == 2  # opening cut (in=0) has no boundary
        assert report["off_beat"] == []
        assert report["alignment_ratio"] == 1.0

    def test_off_beat_cut_is_reported_with_delta(self):
        cuts = [
            {"id": "a", "in_seconds": 0, "out_seconds": 1.2},
            {"id": "b", "in_seconds": 1.25, "out_seconds": 2.0},  # 250ms past beat 1.0
        ]
        report = beat_alignment_report(cuts, self.BEATS)
        [finding] = report["off_beat"]
        assert finding["id"] == "b"
        # 1.25 is equidistant from beats 1.0 and 1.5 — min() keeps the first.
        assert finding["nearest_beat"] == 1.0
        assert finding["delta_ms"] == 250.0

    def test_no_beats_returns_unchecked(self):
        report = beat_alignment_report([{"id": "a", "in_seconds": 1}], [])
        assert report["alignment_ratio"] is None

    def test_overlay_layers_ignored(self):
        cuts = [{"id": "logo", "in_seconds": 1.3, "out_seconds": 2, "layer": 1}]
        assert beat_alignment_report(cuts, self.BEATS)["checked"] == 0


class TestAssetConsistency:
    def _fake_embedder(self, mapping):
        return lambda paths: [mapping[Path(p).name] for p in paths]

    def test_consistent_assets_pass(self, tmp_path):
        for name in ("a.png", "b.png"):
            (tmp_path / name).write_bytes(b"x")
        embed = self._fake_embedder({"a.png": [1.0, 0.0], "b.png": [0.98, 0.199]})
        result = check_asset_consistency(
            {"hero_vacuum": [str(tmp_path / "a.png"), str(tmp_path / "b.png")]},
            embed_fn=embed,
        )
        assert result["ran"] is True
        assert result["findings"] == []
        assert result["critical"] is False

    def test_divergent_design_is_critical(self, tmp_path):
        # The vacuum-robot incident: same subject, visibly different design.
        for name in ("a.png", "b.png"):
            (tmp_path / name).write_bytes(b"x")
        embed = self._fake_embedder({"a.png": [1.0, 0.0], "b.png": [0.5, 0.866]})
        result = check_asset_consistency(
            {"hero_vacuum": [str(tmp_path / "a.png"), str(tmp_path / "b.png")]},
            embed_fn=embed,
        )
        assert result["critical"] is True
        [finding] = result["findings"]
        assert finding["subject"] == "hero_vacuum"
        assert finding["similarity"] < 0.8

    def test_single_asset_groups_skipped(self, tmp_path):
        (tmp_path / "a.png").write_bytes(b"x")
        result = check_asset_consistency(
            {"solo": [str(tmp_path / "a.png")]},
            embed_fn=lambda paths: [[1.0]],
        )
        assert result["ran"] is True
        assert result["subjects_checked"] == []

    def test_missing_embedder_degrades_gracefully(self, tmp_path, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def no_clip(name, *args, **kwargs):
            if name == "lib.clip_embedder":
                raise ImportError("torch not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_clip)
        for name in ("a.png", "b.png"):
            (tmp_path / name).write_bytes(b"x")
        result = check_asset_consistency(
            {"s": [str(tmp_path / "a.png"), str(tmp_path / "b.png")]}
        )
        assert result["ran"] is False
        assert "unavailable" in result["reason"]


class TestBoundaryTransitionMapping:
    def test_editorial_names_map_to_xfade_types(self):
        assert VideoStitch._normalize_boundary("dissolve") == ("fade", None)
        assert VideoStitch._normalize_boundary("wipe-left") == ("wipeleft", None)
        assert VideoStitch._normalize_boundary("slide_up") == ("slideup", None)
        assert VideoStitch._normalize_boundary("circle-open") == ("circleopen", None)

    def test_cut_becomes_near_instant_fade(self):
        xfade_type, dur = VideoStitch._normalize_boundary("cut")
        assert xfade_type == "fade"
        assert dur == VideoStitch._CUT_DURATION

    def test_unknown_degrades_to_fade(self):
        assert VideoStitch._normalize_boundary("quantum-teleport") == ("fade", None)
