"""Cross-shot visual consistency check for generated assets.

Audit 2026-07-16, Wave 3 item 17: the vacuum-robot incident — four generated
shots of "the same" product, four visibly different designs — had NO code
defense; AGENT_GUIDE prose told agents to reuse reference images, and the
Backlot filmstrip was the only catch. This module gives the assets stage a
hard check: embed every asset tagged with the same subject (character or
product) via CLIP and flag pairs whose cosine similarity falls below the
threshold.

Graceful degradation: without torch/transformers the check reports
ran=False + reason instead of failing the stage — availability is surfaced,
never faked (same policy as the registry's availability contract).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Sequence

# Below this cosine similarity two renderings of the SAME subject are
# suspicious. Empirically ViT-B/32 puts same-object different-angle pairs
# around 0.85+; unrelated objects drop under 0.7.
DEFAULT_THRESHOLD = 0.80


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def check_asset_consistency(
    groups: dict[str, list[str]],
    threshold: float = DEFAULT_THRESHOLD,
    embed_fn: Callable[[list[str]], Any] | None = None,
) -> dict[str, Any]:
    """Check pairwise visual similarity within each subject group.

    groups: {subject_tag: [asset image paths]} — e.g. every generated still
    or reference frame of "hero_vacuum". Frames from video shots should be
    sampled by the caller (frame_sampler) before calling.

    Returns {ran, subjects_checked, threshold, findings, critical}. Each
    finding is a below-threshold pair — a CRITICAL review item: the same
    subject rendered as visibly different designs.
    """
    if embed_fn is None:
        try:
            from lib.clip_embedder import embed_images as embed_fn  # type: ignore
        except Exception as e:  # torch/transformers not installed
            return {
                "ran": False,
                "reason": f"CLIP embedder unavailable ({e}) — install torch+transformers "
                          f"or verify consistency manually on the Backlot filmstrip",
                "findings": [],
                "critical": False,
            }

    findings: list[dict[str, Any]] = []
    subjects_checked: list[str] = []

    for subject, paths in groups.items():
        existing = [str(p) for p in paths if Path(p).exists()]
        if len(existing) < 2:
            continue
        try:
            vectors = embed_fn(existing)
        except Exception as e:
            return {
                "ran": False,
                "reason": f"embedding failed for {subject!r}: {e}",
                "findings": [],
                "critical": False,
            }
        subjects_checked.append(subject)
        for i in range(len(existing)):
            for j in range(i + 1, len(existing)):
                similarity = _dot(vectors[i], vectors[j])
                if similarity < threshold:
                    findings.append({
                        "subject": subject,
                        "asset_a": existing[i],
                        "asset_b": existing[j],
                        "similarity": round(similarity, 4),
                        "threshold": threshold,
                    })

    return {
        "ran": True,
        "subjects_checked": subjects_checked,
        "threshold": threshold,
        "findings": findings,
        # Any below-threshold pair means the same subject looks like two
        # different designs — a critical finding per the reviewer protocol.
        "critical": bool(findings),
    }
