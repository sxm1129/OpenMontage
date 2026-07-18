# Publish Director - Hybrid Pipeline

## When To Use

Package the hybrid outputs so the hero cut and its derivatives stay organized and the source/support mix remains clear.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["compose"]["render_report"]`, `state.artifacts["idea"]["brief"]`, `state.artifacts["script"]["script"]` | Final outputs and hybrid framing |
| Playbook | Active style playbook | Tone consistency |

## Process

### 1. Distinguish Master And Variants

Group outputs as:

- master cut,
- short-form derivatives,
- format variants,
- chaptered or contextual variants.

### 2. Preserve Source Truth In Packaging

If the project uses interview footage, screen recording, or product footage as its anchor, the metadata should reflect that instead of packaging it like a pure generated piece.

### 3. Store Cross-Output Notes

Recommended metadata keys:

- `master_output`
- `derivative_outputs`
- `source_mix_notes`
- `platform_copy_map`

### 4. Produce The Real Files Before Claiming Them

Confirmed live (a full paid end-to-end run, a different pipeline): a publish
stage wrote a `publish_log` claiming derivative exports that didn't exist on
disk — the anti-fabrication guard failed the job; it will fail yours too.
`publish_log` may only describe a file a tool call in THIS turn actually
produced:

- **Master export**: call `export_bundle(video_path=<render_report's final
  output path>, title=..., description=..., tags=..., hashtags=...)`. It
  copies the file into `exports/<project>/` and returns a schema-valid
  `publish_log` in `data["publish_log"]` — persist that, don't hand-write one.
- **Short-form derivative**: call `video_trimmer(operation="cut", ...)` for a
  shorter duration.
- **Format variant**: call `auto_reframe(input_path=..., output_path=...,
  target_aspect="portrait"/"square")` — the file must exist before you
  mention it.
- **Poster / thumbnail frame**: call `video_compose(operation="extract_poster",
  input_path=<master path>, output_path=...)`.
- **`youtube_upload`** requires the user's explicit approval for THIS run
  before you call it — publishing live is not a default action.

If you skip a promised variant, say so and drop it from `derivative_outputs`
— never describe it as delivered.

### 5. Quality Gate

- master and variants are clearly labeled,
- metadata matches the true source mix,
- every export referenced in `publish_log` was actually produced by a tool
  call this turn — no file, no entry,
- export folders are organized by purpose,
- the package is ready to use without manual cleanup.

## Common Pitfalls

- Hiding which output is the hero cut.
- Packaging a source-led project like a generic generated asset.
- Losing platform-specific copy and labeling across variants.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
