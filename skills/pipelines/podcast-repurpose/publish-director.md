# Publish Director - Podcast Repurpose Pipeline

## When To Use

Package podcast-derived clips and companion assets so that every short-form piece points back to the episode instead of drifting as an isolated fragment.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["compose"]["render_report"]`, `state.artifacts["idea"]["brief"]`, `state.artifacts["script"]["script"]` | Outputs, source truth, chapters |
| Playbook | Active style playbook | Brand voice |

## Process

### 1. Link Every Clip Back To The Episode

Each short-form asset should reference:

- show name,
- episode title or number,
- guest name where relevant,
- full episode destination.

### 2. Tailor The Copy

- Shorts / Reels / TikTok: hook-led and concise
- LinkedIn: insight-led and more contextual
- YouTube companion: chapter-rich and search-friendly

### 3. Sequence The Release

Recommended order:

1. strongest announcement clip
2. next-best insight clip
3. quote-led or guest-led follow-ups
4. remaining supporting clips

### 4. Store Cross-Linking Truth In Metadata

Recommended metadata keys:

- `episode_reference`
- `guest_tags`
- `posting_schedule`
- `clip_to_episode_map`

### 5. Produce The Real Package Before Claiming It

Confirmed live (a full paid end-to-end run, a different pipeline): a publish
stage wrote a `publish_log` claiming exports that didn't exist on disk — the
anti-fabrication guard failed the job; it will fail yours too. Every clip in
`clip_to_episode_map` must already be a real, rendered file from
`render_report` — don't invent a path for a clip that was never composed. To
package each clip for hand-off, call `export_bundle(video_path=<that clip's
real output path>, title=..., description=..., tags=..., hashtags=...)` once
per clip you're publishing; it copies the file into `exports/<project>/` and
returns a schema-valid `publish_log` entry — merge those rather than
hand-writing paths. If a platform-specific reframe is promised, call
`auto_reframe` to actually produce it first. `youtube_upload` requires the
user's explicit approval for THIS run before you call it — publishing live
is not a default action.

### 6. Quality Gate

- every clip points back to the episode,
- guest attribution is correct,
- copy matches the platform,
- every file referenced in `clip_to_episode_map`/`publish_log` is a real,
  produced file — no file, no entry,
- the release order reflects actual clip strength.

## Common Pitfalls

- Publishing clips without clear episode references.
- Forgetting to tag or mention the guest when that audience matters.
- Reusing one caption style across every platform.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
