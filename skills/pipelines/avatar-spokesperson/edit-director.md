# Edit Director - Avatar Spokesperson Pipeline

## When To Use

Turn the planned presenter scenes and produced assets into a coherent spokesperson timeline. The quality bar is steady delivery, readable support layers, and a clear CTA landing.

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

### 1. Cut The Presenter Track First

Assemble the core spokesperson performance before adding support layers. If the presenter cut is weak, extra graphics will not rescue it.

### 2. Add Support Layers Sparingly

Use overlays only where they help:

- short proof points,
- product names,
- pricing or feature cards,
- CTA reinforcement,
- subtitles.

### 3. Respect Spoken Rhythm

Keep pauses where they help emphasis. Do not trim so tightly that the avatar feels rushed or robotic.

### 4. Plan Deliverables Clearly

Recommended metadata keys:

- `hero_cut_order`
- `cta_frame_range`
- `overlay_timing_map`
- `variant_decisions`

### 5. Quality Gate

- the presenter remains the anchor,
- overlays are timed cleanly,
- scene transitions are calm and intentional,
- the CTA lands once and clearly.

## Common Pitfalls

- Overcutting to simulate energy.
- Letting captions, side panels, and lower thirds compete for the same area.
- Ending without a clean CTA hold.
