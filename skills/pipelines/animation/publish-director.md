# Publish Director - Animation Pipeline

## When To Use

Package the animation so the metadata, thumbnail concept, and platform framing reflect the actual visual system of the project.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["compose"]["render_report"]`, `state.artifacts["proposal"]["proposal_packet"]`, `state.artifacts["research"]["research_brief"]`, `state.artifacts["script"]["script"]` | Final outputs and topic framing |
| Playbook | Active style playbook | Visual naming consistency |

## Process

### 1. Match Packaging To The Animation Mode

Examples:

- diagram-heavy videos should look structured and legible,
- kinetic-type pieces should package around strong copy,
- illustrative animation should package around hero imagery.

### 2. Preserve Visual-System Truth

Store in `publish_log.metadata`:

- `animation_mode`
- `hero_frame_notes`
- `thumbnail_concept`
- `platform_notes`

### 3. Produce The Real Files Before Claiming Them

Confirmed live (a full paid end-to-end run, a different pipeline): a publish
stage wrote a `publish_log` claiming derivative exports that didn't exist on
disk — the anti-fabrication guard failed the job; it will fail yours too.
`publish_log` may only describe a file a tool call in THIS turn actually
produced:

- **Hero export**: call `export_bundle(video_path=<render_report's final
  output path>, title=..., description=..., tags=..., hashtags=...)`. It
  copies the file into `exports/<project>/` and returns a schema-valid
  `publish_log` in `data["publish_log"]` — persist that, don't hand-write one.
- **Platform-variant cutdowns**, if promised: call
  `video_trimmer(operation="cut", ...)` for a shorter duration and/or
  `auto_reframe(input_path=..., output_path=..., target_aspect="portrait"/
  "square")` for an aspect-ratio change — the file must exist before you
  mention it.
- **Poster / thumbnail frame**: call `video_compose(operation="extract_poster",
  input_path=<hero path>, output_path=...)` rather than only describing a
  concept.
- **`youtube_upload`** requires the user's explicit approval for THIS run
  before you call it — publishing live is not a default action.

If you skip a promised variant, say so and drop it from the deliverable list
— never describe it as delivered.

### 4. Quality Gate

- metadata fits the actual animation mode,
- thumbnail concept matches the final visual system,
- every export referenced in `publish_log` was actually produced by a tool
  call this turn — no file, no entry,
- the package is usable without extra manual work.

## Common Pitfalls

- Writing generic metadata that ignores the animation style.
- Creating a thumbnail concept unrelated to the final frames.
- Mixing platform variants without clear labels.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
