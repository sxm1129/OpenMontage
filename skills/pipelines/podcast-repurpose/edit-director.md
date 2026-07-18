# Edit Director - Podcast Repurpose Pipeline

## When To Use

This stage creates the actual timeline logic for short clips and any optional full-episode companion asset. The audio remains the primary content.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["assets"]["asset_manifest"]`, `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]` | Assets, layouts, transcript timing |
| Playbook | Active style playbook | Motion and subtitle rules |

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

### 1. Build Clip Timelines Fast

For short-form clips:

- open on the hook,
- start captions immediately,
- make speaker attribution obvious,
- let the ending land cleanly.

### 2. Match The Edit To The Treatment

- source-video clips should emphasize speaker framing and reactions,
- audiogram clips should emphasize captions, speaker identity, and pacing,
- quote-led clips should preserve enough reading time after the line lands.

### 3. Keep Full-Episode Companion Simple

If producing one:

- use chapter cards,
- use limited recurring visual systems,
- do not force constant visual novelty if the assets are not there.

### 4. Use Metadata For Richer Timeline Notes

Recommended metadata keys:

- `clip_timelines`
- `quote_hold_times`
- `speaker_change_markers`
- `chapter_card_windows`

### 5. Quality Gate

- every short clip hooks quickly,
- captions and attribution are present,
- quote-led clips hold long enough to read,
- the long-form companion stays editorially honest and technically feasible.

## Common Pitfalls

- Building generic audiograms that ignore who is speaking.
- Ending quote clips as soon as the audio ends, before the text can be read.
- Turning a long-form companion into a weak imitation of a fully produced video podcast.
