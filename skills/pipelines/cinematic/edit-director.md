# Edit Director - Cinematic Pipeline

## When To Use

This stage turns the beat map into a paced cinematic timeline. Rhythm and restraint matter more than effect count.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["asset_manifest"]`, `state.artifacts["scene_plan"]`, `state.artifacts["script"]` | Assets, hero frames, beat map |
| Playbook | Active style playbook | Typography and transition consistency |

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

### 0b. Native Title/Text Cards Use `cut.text`, Never A Fabricated Asset

For `render_runtime="remotion"` (non-atelier / templated path), a title card,
slogan card, or hero-title beat is a **native Remotion component**, not a
media file. Author it directly as a cut:

```json
{
  "id": "cut_sc05_title",
  "type": "hero_title",
  "text": "一整天",
  "in_seconds": 19,
  "out_seconds": 23
}
```

Recognized native types and their required field: `text_card` (`cut.text`),
`hero_title` (`cut.text`, optional `cut.heroSubtitle`), `stat_card`
(`cut.stat`), `callout` (`cut.text`), `comparison` (`cut.leftLabel` /
`cut.rightLabel` / `cut.leftValue` / `cut.rightValue`). See
`remotion-composer/src/Explainer.tsx` for the full list and field names.

Do **not** invent an `asset_manifest` entry with a placeholder path (e.g.
`assets/title_cards/x.remotion`) and point `cut.source` at it — there is no
file there. Confirmed live (2026-07-19): a cut shaped this way resolves to a
real-looking absolute path that doesn't exist, which `video_compose` now
rejects outright before rendering ("local asset path(s) ... do not exist on
disk") rather than letting it reach Remotion as an opaque proxy error. If the
asset stage already logged such an entry with `format: "remotion_component"`,
that's fine as a planning record — just don't let `cut.source` reference it;
give the cut its own `text` field instead.

### 1. Cut By Emotion First

Cuts should follow:

- emotional emphasis,
- reveal timing,
- musical turns,
- visual contrast.

Do not optimize only for information density.

### 2. Protect Strong Moments

If a look, line, or gesture is doing the work, let it live. Do not over-cover it with extra inserts.

### 3. Use Sound To Push The Edit

Ambience, impacts, dropouts, and music changes should help create momentum between scenes.

### 4. Use Metadata For Timing Logic

Recommended metadata keys:

- `beat_timing`
- `audio_turns`
- `title_card_windows`
- `reframe_notes`

### 5. Quality Gate

- the emotional arc is intact,
- reveals land clearly,
- title cards are sparse and timed with intent,
- strong moments are not buried under coverage.

## Common Pitfalls

- Overcutting emotional material.
- Using speed ramps or flashy transitions by default.
- Letting title cards replace editorial clarity.
