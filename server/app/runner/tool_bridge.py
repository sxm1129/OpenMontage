"""Tool Bridge: exposes OpenMontage BaseTool registry to the headless agent.

The agent is given three capabilities:
  read_file         — read any file under the OpenMontage root
  write_artifact    — persist an artifact JSON to the project dir
  run_openmontage_tool — call any registered BaseTool by name

Tool schemas are returned in OpenAI function-call format so they work with
both the OpenAI SDK (pointing at MaaS) and Anthropic SDK.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

# Add OpenMontage root to path so we can import tools/lib
OM_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(OM_ROOT))

# Artifact names are meant to be flat identifiers (e.g. "research_brief"), not
# paths — reject anything else outright rather than trying to reason about
# path-containment edge cases for a field that should never contain a
# separator at all.
_SAFE_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_relative_path(base: Path, relative: str) -> Path | None:
    """Resolve `relative` under `base`, returning it only if it actually stays
    within `base`. Guards against pathlib's absolute-path-override footgun
    (`base / "/etc/passwd"` silently discards `base`) and `..` traversal —
    confirmed live: read_file(path=".env") alone discloses MAAS_API_KEY since
    OM_ROOT is the repo root, and read_file(path="/etc/passwd") escapes
    entirely with no code anywhere stopping it. Returns None on any escape."""
    try:
        candidate = (base / relative).resolve()
        candidate.relative_to(base.resolve())
    except (ValueError, OSError):
        return None
    return candidate

# Authoritative budget-exceeded type shared with the runner (fall back to a
# local class if the cost_tracker module isn't importable).
try:
    from tools.cost_tracker import BudgetExceededError
except Exception:  # pragma: no cover
    class BudgetExceededError(Exception):
        pass

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file from the OpenMontage filesystem. "
                "Use for skills (skills/), pipeline manifests (pipeline_defs/), "
                "schemas (schemas/), and project artifacts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to OpenMontage root"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_artifact",
            "description": (
                "Write a pipeline artifact JSON to the project artifacts directory. "
                "IMPORTANT: Keep 'content' compact — each field value under 300 chars, "
                "use arrays of short strings rather than long prose. "
                "Large content causes token truncation and will fail."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "artifact_name": {
                        "type": "string",
                        "description": (
                            "Use the exact name given under '## Expected Artifact Name' "
                            "in your stage instructions — it varies per pipeline/stage "
                            "(e.g. a stage named 'idea' may produce 'brief', not 'idea')."
                        )
                    },
                    "content": {
                        "type": "object",
                        "description": "Compact JSON artifact. Keep each string value under 300 chars."
                    }
                },
                "required": ["artifact_name", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_openmontage_tool",
            "description": (
                "Run a tool from the OpenMontage tool registry. "
                "Available capabilities: video_generation, image_generation, tts, "
                "music_search, subtitle, enhancement, analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Registered tool name, e.g. 'maas_video', 'maas_image', 'maas_tts'"
                    },
                    "inputs": {
                        "type": "object",
                        "description": "Tool inputs per the tool's input_schema"
                    }
                },
                "required": ["tool_name", "inputs"]
            }
        }
    }
]


# Maps the job-level "which capability does this option name constrain"
# relationship: options[<key>] / options[<variants_key>] binds tool_name's
# `inputs["model"]`. Extend this if another capability gets a wizard-level
# model choice (e.g. music) — everything else about the enforcement below is
# generic over this table.
_MODEL_ENFORCED_TOOLS: dict[str, dict[str, str]] = {
    "maas_video": {"default_key": "video_model", "variants_key": "video_model_variants"},
    "maas_image": {"default_key": "image_model", "variants_key": "image_model_variants"},
    "maas_tts":   {"default_key": "tts_model",   "variants_key": "tts_model_variants"},
}


def variant_slug(model_or_variant: str) -> str:
    """Turn a model ID ("leapfast/ltx-2.3") or an already-short variant tag
    ("ltx") into a filesystem-safe slug ("ltx2-3" / "ltx"). Used to keep
    per-variant output files distinguishable (final_ltx.mp4 vs
    final_wan.mp4) instead of an opaque random suffix that tells a human
    nothing about which A/B branch produced which file."""
    tail = model_or_variant.rsplit("/", 1)[-1]
    slug = "".join(c if c.isalnum() else "-" for c in tail.lower()).strip("-")
    return slug or "default"


def _enforce_model_choice(tool_name: str, inputs: dict[str, Any], options: dict[str, Any] | None) -> str | None:
    """Fill in or validate inputs["model"] against the job's options.

    Returns None if the call may proceed (inputs mutated in place when a
    default was filled in), or an error string if the agent must be told to
    retry with a different model — before any paid API call is made.

    Without this, the wizard's model choice (or an A/B variants list) was
    purely descriptive text in the prompt (`## Options: {...}`) — the agent
    was free to call any model regardless of what the user selected. That
    made "pick a model in the UI" cosmetic: the dropdown could say
    leapfast/wan2.2 while the agent quietly kept generating with whatever it
    defaulted to.
    """
    if not options:
        return None
    cfg = _MODEL_ENFORCED_TOOLS.get(tool_name)
    if not cfg:
        return None

    variants = options.get(cfg["variants_key"])
    allowed = [m for m in variants if m] if isinstance(variants, list) and variants else None
    default = options.get(cfg["default_key"]) or None

    if not allowed and not default:
        return None  # job didn't constrain this capability at all

    requested = inputs.get("model")
    if not requested:
        # Fill in rather than reject — the common case (no variants) should
        # just work without the agent having to echo the option back.
        inputs["model"] = (allowed[0] if allowed else default)
        return None

    permitted = allowed or [default]
    if requested in permitted:
        return None

    return (
        f"ERROR: model {requested!r} is not permitted for this job's {cfg['default_key']} "
        f"setting. This job is constrained to: {permitted}. "
        f"Retry {tool_name} with model set to one of those — do not substitute a different "
        f"one even if you believe it fits the prompt better; the user chose this in the wizard."
    )


_TTS_EMOTION_KEYS = ("emo_alpha", "use_emo_text", "emo_text", "interval_silence")


def _apply_tts_emotion_defaults(inputs: dict[str, Any], options: dict[str, Any] | None) -> None:
    """Fill in maas_tts's IndexTTS V3 emotion params (options["tts_emotion"])
    when the agent's call didn't set them explicitly.

    Without this, the wizard's emotion controls were purely descriptive —
    nothing read them, so picking an emotion in the UI had zero effect unless
    the agent happened to independently choose the same values. Unlike
    _enforce_model_choice, this only fills gaps rather than rejecting a
    mismatch: there's no "wrong" emotion value to block, only a default that
    should apply when the agent didn't think to set one, while still letting
    it deliberately vary emotion per line/scene if it wants to.

    emo_alpha=0.0 is a valid, meaningful value (flat delivery) — checked via
    `key in defaults`, not truthiness, so it isn't mistaken for "unset".
    """
    if not options:
        return
    defaults = options.get("tts_emotion")
    if not isinstance(defaults, dict):
        return
    for key in _TTS_EMOTION_KEYS:
        if key in defaults and key not in inputs:
            inputs[key] = defaults[key]


def execute_tool(
    name: str,
    args: dict[str, Any],
    project_dir: Path,
    emit_event: Any = None,   # callable(event_dict) for SSE
    cost_accumulator: list | None = None,  # mutable list[float] for cost accumulation
    cost_tracker: Any = None,  # optional tools.cost_tracker.CostTracker ledger
    budget_cny: float | None = None,  # per-job CNY ceiling (None = no gate)
    base_cost: float = 0.0,           # cost already spent before this run (retries)
    options: dict[str, Any] | None = None,  # job-level options (model choices, variants)
) -> str:
    """Execute a tool call and return a string result for the agent."""

    if name == "read_file":
        path = _safe_relative_path(OM_ROOT, args["path"])
        if path is None:
            return f"ERROR: path {args['path']!r} is outside the OpenMontage root — not allowed"
        # read_file exists for skills/, pipeline_defs/, schemas/, and project
        # artifacts (per its own tool description) — never dotfiles. Without
        # this, staying within OM_ROOT isn't enough: .env sits directly at
        # OM_ROOT, so a plain in-bounds read_file(path=".env") would still
        # disclose MAAS_API_KEY.
        if any(part.startswith(".") for part in path.relative_to(OM_ROOT.resolve()).parts):
            return f"ERROR: refusing to read a dotfile/dotdir path: {args['path']!r}"
        if not path.exists():
            return f"ERROR: File not found: {args['path']}"
        content = path.read_text(encoding="utf-8")
        if len(content) > 12000:
            content = content[:12000] + f"\n\n[truncated — {len(content)} total chars]"
        return content

    elif name == "write_artifact":
        artifact_name = args.get("artifact_name")
        content = args.get("content")
        if not artifact_name:
            return "ERROR: write_artifact requires 'artifact_name' parameter"
        if content is None:
            return "ERROR: write_artifact requires 'content' parameter"
        if not _SAFE_ARTIFACT_NAME.match(artifact_name):
            return (
                f"ERROR: invalid artifact_name {artifact_name!r} — must contain only "
                "letters, numbers, underscores, and hyphens (no path separators or '..')"
            )
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        out = artifacts_dir / f"{artifact_name}.json"
        out.write_text(json.dumps(content, ensure_ascii=False, indent=2))
        if emit_event:
            emit_event({
                "type": "artifact_written",
                "artifact": artifact_name,
                "path": str(out.relative_to(OM_ROOT)),
            })
        return f"Written to {out}"

    elif name == "run_openmontage_tool":
        tool_name = args["tool_name"]
        inputs = args.get("inputs", {})

        if emit_event:
            emit_event({
                "type": "tool_call",
                "tool": tool_name,
                "summary": f"调用工具 {tool_name}",
                "inputs_preview": {k: str(v)[:80] for k, v in inputs.items()},
            })

        from tools.tool_registry import registry
        registry.discover()
        tool = registry.get(tool_name)
        if not tool:
            return f"ERROR: Tool '{tool_name}' not found in registry"

        enforcement_error = _enforce_model_choice(tool_name, inputs, options)
        if enforcement_error:
            return enforcement_error

        if tool_name == "maas_tts":
            _apply_tts_emotion_defaults(inputs, options)

        # A caller doing an A/B variants run (options[...variants_key] set)
        # tags which branch a call belongs to — either explicitly via
        # inputs["variant"] (the only way compose/video_post calls can say
        # this, since they have no "model" of their own) or implicitly via
        # inputs["model"] for generation calls. Popped before the tool sees
        # `inputs` — it's a routing hint, not a tool parameter.
        variant = inputs.pop("variant", None) or inputs.get("model")
        variant_tag = f"_{variant_slug(variant)}" if variant else ""

        # Set output path if not specified.
        if "output_path" not in inputs:
            ext_map = {
                "video_generation": "mp4",
                "image_generation": "png",
                "tts": "mp3",
                "music_generation": "mp3",
                "audio_processing": "mp3",
                "video_post": "mp4",
            }
            ext = ext_map.get(tool.capability, "bin")

            # The final composed video is the pipeline deliverable — it must land
            # in renders/ so the runner and /media serving can find and play it.
            # Any other video_post op (trim, stitch) stays in assets/.
            is_final_compose = (
                tool.capability == "video_post"
                and inputs.get("operation", "compose") == "compose"
            )
            if is_final_compose:
                renders_dir = project_dir / "renders"
                renders_dir.mkdir(parents=True, exist_ok=True)
                # Plain "final.mp4" for the common single-render case (kept
                # byte-for-byte compatible with every existing job/URL that
                # already assumes this name). An A/B run doing N independent
                # compose calls needs the variant folded into the filename —
                # otherwise the second call's "final.mp4" silently clobbers
                # the first's, and only one variant would ever be watchable.
                filename = f"final{variant_tag}.mp4" if variant_tag else "final.mp4"
                inputs = {**inputs, "output_path": str(renders_dir / filename)}
            else:
                out_dir = project_dir / "assets" / tool.capability
                out_dir.mkdir(parents=True, exist_ok=True)
                # A fixed "{tool_name}_output.{ext}" filename meant every call
                # to the same tool within a job silently overwrote the
                # previous one's file — confirmed live: an assets-stage run
                # that generated 6 distinct video clips (without the agent
                # overriding output_path) left exactly ONE file on disk,
                # since each call clobbered the last. A short random suffix
                # gives every call — with or without a distinguishing
                # prompt/parameter — its own file. The variant tag (when
                # present) makes the filename tell a human which A/B branch
                # it belongs to, instead of being opaque.
                unique = uuid.uuid4().hex[:8]
                inputs = {**inputs, "output_path": str(out_dir / f"{tool_name}{variant_tag}_{unique}.{ext}")}

        # Hard budget ceiling — pre-call check. Bounds total spend to <= budget
        # by refusing a paid call that would cross it, instead of letting a
        # single stage (e.g. assets) generate many clips past the ceiling before
        # the between-stages gate ever fires. Raises so _run_agent_stage unwinds
        # and the runner's event loop can own the human pause.
        est_cost = float(tool.estimate_cost(inputs) or 0.0)
        if budget_cny is not None and est_cost > 0:
            projected = base_cost + (sum(cost_accumulator) if cost_accumulator else 0.0) + est_cost
            if projected > budget_cny:
                if emit_event:
                    emit_event({
                        "type": "budget_precall_block",
                        "tool": tool_name,
                        "projected_cny": round(projected, 4),
                        "budget_cny": budget_cny,
                    })
                raise BudgetExceededError(
                    f"Paid call to {tool_name} (est ¥{est_cost:.2f}) would bring spend to "
                    f"¥{projected:.2f}, over budget ¥{budget_cny:.2f}"
                )

        # Ledger: estimate before, reconcile after (real CostTracker usage →
        # persists an itemized cost_log.json for budget governance/audit).
        entry_id = None
        if cost_tracker is not None:
            try:
                entry_id = cost_tracker.estimate(
                    tool_name,
                    inputs.get("operation", "run"),
                    float(tool.estimate_cost(inputs) or 0.0),
                )
                cost_tracker.approve_tool(tool_name)
                cost_tracker.reserve(entry_id)   # OBSERVE mode never raises
            except Exception:
                entry_id = None

        result = tool.execute(inputs)

        if cost_tracker is not None and entry_id is not None:
            try:
                cost_tracker.reconcile(
                    entry_id, float(result.cost_usd or 0.0), success=result.success
                )
            except Exception:
                pass

        if result.success:
            # Record every completed paid call (append even 0.0 so the tally
            # reflects call count; the sum is what drives the CNY display).
            if cost_accumulator is not None and result.cost_usd is not None:
                cost_accumulator.append(float(result.cost_usd))
            if emit_event and result.artifacts:
                for artifact_path in result.artifacts:
                    emit_event({
                        "type": "asset_ready",
                        "tool": tool_name,
                        "path": artifact_path,
                        "kind": tool.capability,
                    })
            return json.dumps({
                "success": True,
                "data": result.data,
                "artifacts": result.artifacts,
                "cost_usd": result.cost_usd,
            })
        else:
            return json.dumps({"success": False, "error": result.error})

    return f"ERROR: Unknown tool: {name}"
