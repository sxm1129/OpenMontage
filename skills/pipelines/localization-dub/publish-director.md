# Publish Director - Localization Dub Pipeline

## When To Use

Package the completed localization outputs so downstream teams can find the right video, subtitle, and metadata bundle for each language without manual cleanup.

## Process

### 1. Package By Locale

Each language package should clearly separate:

- video output,
- subtitle files,
- transcript or approved script copy,
- review notes,
- metadata.

### 2. Keep Naming Precise

Recommended metadata keys:

- `locale`
- `language_name`
- `deliverable_mode`
- `subtitle_included`
- `review_owner`

### 3. Preserve Review Context

If a language output has pronunciation caveats, timing warnings, or missing lip sync, keep that note in the published package.

### 4. Produce The Real Package Before Claiming It

Confirmed live (a full paid end-to-end run, a different pipeline): a publish
stage wrote a `publish_log` claiming exports that didn't exist on disk — the
anti-fabrication guard failed the job; it will fail yours too. Every
video/subtitle/transcript path in a locale package must already be a real
file from an earlier stage — don't invent a path for a locale that was never
actually dubbed or subtitled. To package a locale's files for hand-off, call
`export_bundle(video_path=<that locale's real output path>, title=...,
description=..., subtitles_path=<real .srt path if present>, ...)` per
locale; it copies the files into `exports/<project>/` and returns a
schema-valid `publish_log` entry — merge those rather than hand-writing
paths. `youtube_upload` requires the user's explicit approval for THIS run
before you call it — publishing live is not a default action.

### 5. Quality Gate

- locale packages are clearly labeled,
- metadata matches the actual treatment,
- every file referenced is a real, produced file — no file, no entry,
- supporting text assets are present,
- warnings and review notes are not lost.

## Common Pitfalls

- Shipping localized videos without the matching subtitle or transcript files.
- Mixing audio-dub and subtitle-only variants under the same generic filename.
- Removing the QA notes that explain known issues.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
