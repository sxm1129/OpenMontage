# Edit Director - Clip Factory Pipeline

## When To Use

This stage turns the approved clips into independent mini-edits. Each clip must work alone, but the collection should still feel like a coherent series.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["assets"]["asset_manifest"]`, `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]` | Assets, layouts, transcripts |
| Playbook | Active style playbook | Transition and subtitle consistency |

## Process

### 0. Carry `render_runtime` Forward Unchanged

`render_runtime` was locked at proposal as a plain string — `"remotion"`,
`"hyperframes"`, or `"ffmpeg"` — nothing else. Copy it into
`edit_decisions.render_runtime` byte-for-byte. Do NOT restructure it into an
object (e.g. `{engine, fps, resolution, ...}`) — that fabricates data the
schema rejects (`is not of type 'string'`) and trips the render-runtime
consistency guard, failing the job outright. Delivery specs like
resolution/fps/aspect_ratio/output format are NOT part of this field; they
belong to the compose stage's `profile`/`output_profile` selection (see
`compose-director.md` and `lib/media_profiles.py`), not to `render_runtime`.
Changing the runtime requires a logged `render_runtime_selection` decision —
never silently.

Two sibling proposal-locked fields need the same treatment — confirmed live
(a full paid end-to-end run): `renderer_family` was absent from
`edit_decisions` entirely, forcing the compose agent to guess and patch it
in mid-render as a "data-completion fix". `composition_mode` was silently
dropped too, which defeated the atelier/templated routing check in
`video_compose._render` (`composition_mode == "atelier"`), silently
downgrading an intended atelier render to the templated `cuts[]` path
instead. Copy both forward unchanged from `production_plan.renderer_family`
/ `production_plan.composition_mode` into `edit_decisions.renderer_family` /
`edit_decisions.composition_mode` — same rule as `render_runtime`: no
inventing, no omitting, no restructuring.

### 1. Build A Shared Edit Template

Lock the batch defaults first:

- subtitle style,
- hook timing,
- lower-third timing,
- watermark behavior,
- audio fade lengths.

Then apply per-clip overrides only where necessary.

### 2. Optimize The First 2-3 Seconds

For every clip:

- start on motion, face, or result,
- show hook text immediately if needed,
- let subtitles begin with the first spoken word,
- avoid intros that delay the point.

### 3. Keep Boundaries Clean

- no cuts mid-word,
- no trailing silence after the point lands,
- no "setup for setup's sake" before the hook,
- no outro cards unless they earn the time.

### 4. Use Metadata For Multi-Variant Detail

Recommended metadata keys:

- `batch_template`
- `clip_variants`
- `hook_windows`
- `cta_windows`

### 5. Quality Gate

- each clip is self-contained,
- the first seconds hook fast,
- overlay stack is readable on mobile,
- the batch retains consistent styling and fades.

## Common Pitfalls

- Building one highlight reel instead of independent clips.
- Letting branding delay the hook.
- Overcrowding the screen with hook text, subtitles, watermark, and lower third simultaneously.
- Applying inconsistent transition timing across the batch.
