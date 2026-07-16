"""Timeline validation for edit_decisions — gaps, overlaps, pacing.

Audit 2026-07-16, Wave 2 item 13: pipeline manifests promise "No timeline
gaps or overlaps" and playbooks declare motion.pacing_rules (min/max scene
hold), but NOTHING enforced either — the promises were prose. This module is
the enforcement point, wired into video_compose's pre-compose gate.

Deliberately conservative: findings are warnings for the agent to act on,
not render blockers — a gap may be an intentional beat of breathing room,
and only the humans/agents reviewing the plan can tell. The one exception
callers may choose to block on is same-layer OVERLAP, which double-renders
in the ffmpeg concat path.
"""

from __future__ import annotations

from typing import Any

# Sub-frame jitter tolerance (seconds) — float timings from LLM output.
_EPSILON = 0.05


def validate_edit_timeline(
    edit_decisions: dict[str, Any],
    playbook: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the cuts timeline. Returns {valid, issues, warnings, stats}.

    issues   — contract violations (inverted cuts, same-layer overlaps)
    warnings — pacing/quality advisories (gaps, holds outside playbook rules)
    """
    issues: list[str] = []
    warnings: list[str] = []
    cuts = list(edit_decisions.get("cuts") or [])

    # Base timeline = layer 0 (or unset); higher layers are overlays and may
    # legitimately overlap the base track.
    base = [c for c in cuts if not c.get("layer")]
    base.sort(key=lambda c: float(c.get("in_seconds", 0)))

    pacing = (playbook or {}).get("motion", {}).get("pacing_rules", {}) or {}
    min_hold = pacing.get("min_scene_hold_seconds")
    max_hold = pacing.get("max_scene_hold_seconds")

    for cut in base:
        cid = cut.get("id", "?")
        start = float(cut.get("in_seconds", 0))
        end = float(cut.get("out_seconds", 0))
        hold = end - start
        if hold <= 0:
            issues.append(f"cut {cid}: out_seconds ({end}) <= in_seconds ({start})")
            continue
        if min_hold is not None and hold < float(min_hold) - _EPSILON:
            warnings.append(
                f"cut {cid}: {hold:.2f}s hold is under the playbook minimum "
                f"({min_hold}s) — too fast to read"
            )
        if max_hold is not None and hold > float(max_hold) + _EPSILON:
            warnings.append(
                f"cut {cid}: {hold:.2f}s hold exceeds the playbook maximum "
                f"({max_hold}s) — risks dead screen time"
            )

    for prev, nxt in zip(base, base[1:]):
        prev_end = float(prev.get("out_seconds", 0))
        nxt_start = float(nxt.get("in_seconds", 0))
        if nxt_start - prev_end > _EPSILON:
            warnings.append(
                f"timeline gap {prev_end:.2f}s-{nxt_start:.2f}s "
                f"({nxt_start - prev_end:.2f}s) between cuts "
                f"{prev.get('id', '?')} and {nxt.get('id', '?')} — "
                f"background shows through"
            )
        elif prev_end - nxt_start > _EPSILON:
            issues.append(
                f"cuts {prev.get('id', '?')} and {nxt.get('id', '?')} overlap "
                f"{nxt_start:.2f}s-{prev_end:.2f}s on the base layer — "
                f"double-render in the ffmpeg path"
            )

    return {
        "valid": not issues,
        "issues": issues,
        "warnings": warnings,
        "stats": {
            "base_cuts": len(base),
            "total_cuts": len(cuts),
            "timeline_end_seconds": (
                max((float(c.get("out_seconds", 0)) for c in base), default=0.0)
            ),
        },
    }


def beat_alignment_report(
    cuts: list[dict[str, Any]],
    beats: list[float],
    tolerance_ms: float = 80.0,
) -> dict[str, Any]:
    """How well cut points land on the music's beat grid (卡点, Wave 3 item 15).

    Compares every base-layer cut's in_seconds against the nearest beat from
    beat_grid's output (edit_decisions.music.beats). ±80 ms is the perceptual
    "on the beat" window. Advisory — the edit director decides which cuts
    should snap (a narration-led cut may deliberately ignore the grid).
    """
    if not beats:
        return {"checked": 0, "on_beat": 0, "off_beat": [], "alignment_ratio": None}
    sorted_beats = sorted(beats)
    tolerance = tolerance_ms / 1000.0
    off_beat: list[dict[str, Any]] = []
    checked = 0
    for cut in cuts:
        if cut.get("layer"):
            continue
        at = float(cut.get("in_seconds", 0))
        if at <= 0:
            continue  # the opening cut has no boundary to sync
        checked += 1
        nearest = min(sorted_beats, key=lambda b: abs(b - at))
        delta = at - nearest
        if abs(delta) > tolerance:
            off_beat.append({
                "id": cut.get("id", "?"),
                "at_seconds": round(at, 3),
                "nearest_beat": round(nearest, 3),
                "delta_ms": round(delta * 1000, 1),
            })
    on_beat = checked - len(off_beat)
    return {
        "checked": checked,
        "on_beat": on_beat,
        "off_beat": off_beat,
        "alignment_ratio": round(on_beat / checked, 3) if checked else None,
        "tolerance_ms": tolerance_ms,
    }
