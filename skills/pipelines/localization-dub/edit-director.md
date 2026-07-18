# Edit Director - Localization Dub Pipeline

## When To Use

Translate the scene plan and localized asset kit into concrete timeline decisions for each language output. The goal is to preserve the source structure where possible without pretending all languages land on the same timing.

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

### 1. Preserve Structure By Default

Keep the original scene order and major timing unless the translated audio clearly requires extension, compression, or coverage.

### 2. Apply The Chosen Dub Mode

Per deliverable, decide where to:

- keep original picture with new subtitles,
- replace only the audio,
- use lip-sync output,
- cover mismatch with graphics or B-roll.

### 3. Keep Language Variants Organized

Separate timeline decisions by locale so versioning stays clear all the way into compose and publish.

### 4. Use Metadata For Variant Control

Recommended metadata keys:

- `locale_timeline_map`
- `timing_adjustments`
- `coverage_sections`
- `subtitle_strategy_by_locale`

### 5. Quality Gate

- language variants are explicit,
- timing changes are recorded,
- coverage decisions are deliberate,
- the original structure is only changed where necessary.

## Common Pitfalls

- Forcing every language to match source timing exactly.
- Mixing locale-specific notes into one ambiguous edit list.
- Hiding sections where the dub treatment is visually weak.
