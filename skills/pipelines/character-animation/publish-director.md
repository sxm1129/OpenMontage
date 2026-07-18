# Publish Director - Character Animation Pipeline

## Goal

Package the final character-animation deliverable with honest metadata and a
strong character-forward thumbnail concept.

## Requirements

- Mention the actual visual treatment: local rigged character animation,
  procedural effects, Remotion/HyperFrames render, or mixed.
- Pick a poster frame where the main character's emotion is readable.
- If the output is a sample, label it as a sample.
- If the final is inspired by a reference, describe the inspiration without
  claiming duplication.

## Producing The Files

Confirmed live (a full paid end-to-end run, a different pipeline): a publish
stage wrote a `publish_log` claiming exports that didn't exist on disk — the
anti-fabrication guard failed the job; it will fail yours too. `publish_log`
may only describe a file a tool call in THIS turn actually produced:

- Call `export_bundle(video_path=<render_report's final output path>,
  title=..., description=..., tags=...)`. It copies the file into
  `exports/<project>/` and returns a schema-valid `publish_log` in
  `data["publish_log"]` — persist that, don't hand-write one.
- For the poster frame, call `video_compose(operation="extract_poster",
  input_path=<video path>, output_path=...)` rather than only writing notes
  about where the character's emotion reads best.
- `youtube_upload` requires the user's explicit approval for THIS run before
  you call it — publishing live is not a default action.

## Output

Produce `publish_log` with:

- final video path (from `export_bundle`'s real output),
- thumbnail/poster-frame path (from `video_compose`'s real output),
- title ideas,
- description,
- platform-specific export notes,
- limitations or follow-up recommendations.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
