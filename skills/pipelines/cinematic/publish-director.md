# Publish Director - Cinematic Pipeline

## When To Use

Package the cinematic piece and any cutdowns so the hero version stays clear and the distribution intent is obvious.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["render_report"]`, `state.artifacts["proposal_packet"]`, `state.artifacts["research_brief"]`, `state.artifacts["script"]` | Final outputs and beat map |
| Playbook | Active style playbook | Tone and naming consistency |

## Process

### 1. Separate Hero And Derivatives

Typical deliverables:

- hero trailer or brand film,
- teaser cut,
- social cutdown,
- poster-frame or thumbnail concept.

### 2. Match Metadata To Tone

Packaging should reflect the actual mood:

- dramatic,
- premium,
- mysterious,
- reflective,
- urgent.

### 3. Preserve Editorial Truth

Store in `publish_log.metadata`:

- `hero_output`
- `derivative_outputs`
- `poster_frame_notes`
- `distribution_notes`

### 4. Produce The Real Files Before Claiming Them

Confirmed live (a full paid end-to-end run): a publish stage wrote a
`publish_log` claiming three derivative exports — a WeChat teaser, an XHS
social cutdown, a poster frame — none of which existed on disk. The
anti-fabrication guard failed the job; it will fail yours too.
`publish_log` may only describe a file a tool call in THIS turn actually
produced. For each deliverable:

- **Hero export**: call `export_bundle(video_path=<render_report's final
  output path>, title=..., description=..., tags=..., hashtags=...)`. It
  copies the file into `exports/<project>/` and returns a schema-valid
  `publish_log` in `data["publish_log"]` — persist that, don't hand-write one.
- **Teaser / short cutdown** (a shorter duration of the hero): call
  `video_trimmer(operation="cut", input_path=<hero path>, output_path=...,
  start_seconds=..., end_seconds=...)` — the file must exist before you
  mention it.
- **Social / vertical cutdown** (aspect-ratio change): call
  `auto_reframe(input_path=<hero or trimmed path>, output_path=...,
  target_aspect="portrait")` (or `"square"`).
- **Poster / thumbnail frame**: call `video_compose(operation="extract_poster",
  input_path=<hero path>, output_path=...)`.
- **`youtube_upload`** (a real, live publish) requires the user's explicit
  approval for THIS run before you call it — publishing is not a default
  action. Without that approval, describe the export as ready for manual
  upload instead.

If a tool call fails or you choose to skip a promised derivative, say so in
`publish_log` and drop it from the deliverable list — do not describe it as
delivered anyway.

### 5. Quality Gate

- hero export is clearly identified,
- every derivative referenced in `publish_log` was actually produced by a tool
  call this turn — no file, no entry,
- metadata fits the tone,
- the package is usable without manual cleanup.

## Common Pitfalls

- Mixing teaser and hero outputs without clear naming.
- Writing generic metadata that ignores the mood.
- Treating all cutdowns as interchangeable.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
