# Edit Director - Character Animation Pipeline

## Goal

Produce `edit_decisions` and `action_timeline`.

## Process

1. Carry `render_runtime` forward from the approved proposal as the plain
   string it is — `"remotion"`, `"hyperframes"`, or `"ffmpeg"`. Do NOT
   restructure it into an object (e.g. `{engine, fps, resolution, ...}`) —
   that fabricates data the schema rejects and trips the render-runtime
   consistency guard, failing the job outright. Delivery specs like
   resolution/fps/aspect_ratio belong to the compose stage's `profile`
   selection (`lib/media_profiles.py`), not to this field. Changing the
   runtime requires a logged `render_runtime_selection` decision — never
   silently. If the render_runtime path routes through `video_compose`'s
   templated Remotion dispatch, `renderer_family` and `composition_mode`
   need the same carry-forward treatment — confirmed live elsewhere:
   omitting `renderer_family` forces the compose agent to guess it
   mid-render, and dropping `composition_mode` silently downgrades an
   intended atelier render to the templated path instead.
2. Convert scene beats into timed character actions.
3. Add anticipation, hold, action, and follow-through where appropriate.
4. Align mouth/gesture beats to dialogue or music.
5. Keep action density readable.

## Timing Pattern

Most acting beats need:

```text
anticipation -> action -> hold/reaction -> settle
```

Do not animate everything continuously. Holds are part of acting.

## Tool Use

Use `action_timeline_compiler` for a first pass, then revise the timeline if the
acting or rhythm is weak.

## Quality Bar

Every scene has timed actions. Every action maps to a pose, action cycle, or
procedural effect that the renderer can understand.
