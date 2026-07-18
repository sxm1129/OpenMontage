# Publish Director - Screen Demo Pipeline

## When To Use

Package the finished demo so the user can publish it quickly and so the metadata reflects the actual task, result, and tools involved.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["compose"]["render_report"]`, `state.artifacts["idea"]["brief"]`, `state.artifacts["script"]["script"]` | Video, brief, and sections |
| Playbook | Active style playbook | Thumbnail and copy tone |

## Process

### 1. Build Searchable Metadata

Screen-demo titles work best when they combine:

- task,
- tool,
- outcome.

Good patterns:

- `How to deploy on Vercel from Next.js`
- `Fix CORS in React + Express`
- `Set up GitHub Actions for Python tests`

Pull keywords from:

- software names,
- frameworks,
- commands,
- exact error text,
- outcome words such as `deploy`, `fix`, `connect`, `publish`, `ship`.

### 2. Use Chapter Markers As Navigation

Use script sections as the basis for chapter markers and packaging bullets. A good screen-demo package makes the workflow skimmable before the user even presses play.

### 3. Thumbnail Strategy

If a thumbnail concept is needed, it should show:

- the result state, not a generic setup screen,
- the recognizable tool surface,
- 2-4 words of value text.

Store the concept in `publish_log.metadata.thumbnail_concepts`.

### 4. Package By Platform

Prepare:

- video file,
- title and description/caption,
- chapter markers where relevant,
- keyword list,
- thumbnail concept notes.

For developer or product-demo content, also package:

- commands shown,
- software/version mentions,
- error terms if it is a troubleshooting demo.

### 5. Produce The Real Files Before Claiming Them

Confirmed live (a full paid end-to-end run, a different pipeline): a publish
stage wrote a `publish_log` claiming derivative exports that didn't exist on
disk — the anti-fabrication guard failed the job; it will fail yours too.
`publish_log` may only describe a file a tool call in THIS turn actually
produced:

- **Package**: call `export_bundle(video_path=<render_report's final output
  path>, title=..., description=..., tags=..., chapters=...)`. It copies the
  file into `exports/<project>/` and returns a schema-valid `publish_log` in
  `data["publish_log"]` — persist that, don't hand-write one.
- **Thumbnail frame**: call `video_compose(operation="extract_poster",
  input_path=<video path>, output_path=...)` rather than only storing a
  concept in `publish_log.metadata.thumbnail_concepts`.
- **Platform cutdown**, if promised: call `video_trimmer(operation="cut", ...)`
  and/or `auto_reframe(...)` — the file must exist before you mention it.
- **`youtube_upload`** requires the user's explicit approval for THIS run
  before you call it — publishing live is not a default action.

If you skip a promised variant, say so and drop it — never describe it as
delivered.

### 6. Quality Gate

- metadata names the real tool and task,
- chapters match the actual rendered flow,
- every export referenced in `publish_log` was actually produced by a tool
  call this turn — no file, no entry,
- export folders are clean and reusable,
- copy is tailored to the platform instead of duplicated.

## Common Pitfalls

- Publishing with generic titles that omit the actual software or task.
- Using the same caption for YouTube, LinkedIn, and short-form social.
- Building chapter markers from the script without checking the render.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
