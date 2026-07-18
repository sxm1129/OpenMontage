# Publish Director — Talking Head Pipeline

## When to Use

You have a render report with the final video. Your job is to prepare metadata, thumbnails, and an export package for publishing.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | Render report, Brief | Video file and context |

## Process

### Step 1: Generate Metadata

Create platform-specific metadata:
- **Title**: Based on the brief's title and hook
- **Description**: Summary of the content with relevant keywords
- **Tags**: Derived from brief's key_points
- **Chapters**: From script section timestamps

### Step 2: Thumbnail Frame

Call `video_compose(operation="extract_poster", input_path=<render_report's
final output path>, output_path=...)` to actually extract a real frame, then
note the text-overlay concept (title or key stat) alongside it. Do not only
describe a concept when the tool can produce the real frame.

### Step 3: Package Export

Call `export_bundle(video_path=<render_report's final output path>, title=...,
description=..., tags=..., chapters=..., thumbnail_path=<the frame from Step
2>)`. It lays out the export directory (video, metadata JSON, description
text, chapter markers, thumbnail) and returns a schema-valid `publish_log` in
`data["publish_log"]` — persist that directly rather than hand-building one.
`youtube_upload` requires the user's explicit approval for THIS run before
you call it — publishing live is not a default action.

Confirmed live (a full paid end-to-end run, a different pipeline): a publish
stage wrote a `publish_log` claiming exports that didn't exist on disk — the
anti-fabrication guard failed the job; it will fail yours too. Only describe
a file `export_bundle` (or another tool call) actually produced.

### Step 4: Build Publish Log

Persist the `publish_log` `export_bundle` returned (Step 3) — do not
hand-build a separate one. It already documents platform, status, and export
path correctly.

### Step 5: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Metadata quality** | Is the title compelling and description informative? |
| **Completeness** | Is the export package complete, and is every file real? |

### Step 6: Submit

Validate the publish_log against the schema and persist via checkpoint.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
