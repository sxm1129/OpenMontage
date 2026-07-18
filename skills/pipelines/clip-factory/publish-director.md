# Publish Director - Clip Factory Pipeline

## When To Use

This stage packages the clip batch into a distribution plan. The goal is not just exported files. The goal is a usable content engine.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["compose"]["render_report"]`, `state.artifacts["idea"]["brief"]`, `state.artifacts["script"]["script"]` | Outputs, rankings, and goals |
| Playbook | Active style playbook | Brand voice |

## Process

### 1. Lead With The Strongest Clip

Do not schedule by chronology. Schedule by ranking.

The first published clip should usually be:

- the strongest hook,
- the cleanest standalone clip,
- the clip most aligned with the batch goal.

### 2. Tailor Copy By Platform

Each platform needs its own tone and packaging:

- TikTok / Reels: direct, fast, hook-led
- Shorts: searchable, keyword-aware
- LinkedIn: insight-led and more professional
- X: short, punchy, opinion-friendly

### 3. Package The Batch Cleanly

Group by platform and include ready-to-paste text assets, not just video files.

### 4. Preserve Batch Truth

Store in `publish_log.metadata`:

- `clip_catalog`
- `posting_order`
- `platform_copy_map`
- `schedule_notes`

### 5. Produce The Real Package Before Claiming It

Confirmed live (a full paid end-to-end run, a different pipeline): a publish
stage wrote a `publish_log` claiming exports that didn't exist on disk — the
anti-fabrication guard failed the job; it will fail yours too. Every clip in
`clip_catalog` must already be a real, rendered file from `render_report` —
don't invent a path for a clip that was never composed. To actually package
each clip for hand-off, call `export_bundle(video_path=<that clip's real
output path>, title=..., description=..., tags=..., hashtags=...)` once per
clip you're publishing; it copies the file into `exports/<project>/` and
returns a schema-valid `publish_log` entry — merge those rather than
hand-writing the paths. If a platform variant (a reframed or re-cut version
of a clip) is promised, call `auto_reframe`/`video_trimmer` to actually
produce it first. `youtube_upload` requires the user's explicit approval for
THIS run before you call it — publishing live is not a default action.

### 6. Quality Gate

- strongest clips lead the rollout,
- captions are platform-specific,
- every file referenced in `clip_catalog`/`publish_log` is a real, produced
  file — no file, no entry,
- export folders are usable without extra cleanup,
- the batch catalog clearly links ranking, file paths, and publishing intent.

## Common Pitfalls

- Publishing the whole batch on the same day.
- Using one caption everywhere.
- Losing the rank/order logic after rendering is complete.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
