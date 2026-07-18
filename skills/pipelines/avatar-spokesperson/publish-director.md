# Publish Director - Avatar Spokesperson Pipeline

## When To Use

Package the finished spokesperson outputs for delivery. This stage should make it obvious which file is the hero cut, which are derivatives, and what message or audience each version serves.

## Process

### 1. Label Deliverables Clearly

Distinguish:

- hero cut,
- vertical cutdown,
- square cutdown,
- language variants,
- watermark or review versions.

### 2. Keep Metadata Message-Led

Recommended metadata keys:

- `audience_segment`
- `cta_copy`
- `offer_name`
- `locale`
- `thumbnail_concept`

### 3. Package Review Notes

If the avatar path has limitations such as visible lip-sync risk, retain that note in the package instead of hiding it.

### 4. Produce The Real Files Before Claiming Them

Confirmed live (a full paid end-to-end run, a different pipeline): a publish
stage wrote a `publish_log` claiming derivative exports that didn't exist on
disk — the anti-fabrication guard failed the job; it will fail yours too.
`publish_log` may only describe a file a tool call in THIS turn actually
produced:

- **Hero cut export**: call `export_bundle(video_path=<render_report's final
  output path>, title=..., description=..., tags=..., hashtags=...)`. It
  copies the file into `exports/<project>/` and returns a schema-valid
  `publish_log` in `data["publish_log"]` — persist that, don't hand-write one.
- **Vertical / square cutdown**: call `auto_reframe(input_path=<hero path>,
  output_path=..., target_aspect="portrait"/"square")` — the file must exist
  before you mention it.
- **Language variant**: only reference the localized video/audio path that a
  prior stage's tool call actually produced — never describe a language
  variant no file backs.
- **Poster / thumbnail frame**: call `video_compose(operation="extract_poster",
  input_path=<hero path>, output_path=...)`.
- **`youtube_upload`** requires the user's explicit approval for THIS run
  before you call it — publishing live is not a default action.

If you skip a promised variant, say so and drop it from the deliverable list
— never describe it as delivered.

### 5. Quality Gate

- exports are clearly named,
- metadata matches the intended message,
- every export referenced in `publish_log` was actually produced by a tool
  call this turn — no file, no entry,
- poster frame or thumbnail concept features the presenter cleanly,
- review notes stay attached to the package.

## Common Pitfalls

- Mixing hero and derivative exports without clear naming.
- Reusing generic metadata that ignores the spokesperson offer.
- Dropping risk notes that matter for downstream publishing teams.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
