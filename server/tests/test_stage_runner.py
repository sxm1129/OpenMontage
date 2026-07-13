"""Stage runner: render discovery, artifact loading, and the finish=stop fix."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.runner import stage_runner
from app.runner.stage_runner import (
    _discover_render_url, _discover_render_urls, _load_artifacts, _load_brand_kit,
    _brand_reference_image_data_uri, _MAX_REFERENCE_DATA_URI_CHARS,
    _truncate_json_for_prompt, _last_failure_message, _missing_variants,
    _url_for_render, _discover_render_path, _render_report_path_diverges,
    _validate_publish_log_exports, _check_render_runtime_consistency,
    _build_prior_artifacts_text,
)


# ── _discover_render_url ──────────────────────────────────────────────────────

def test_discover_prefers_renders(tmp_path):
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "renders" / "final.mp4").write_bytes(b"x")
    assert _discover_render_url(proj, "p") == "/media/p/renders/final.mp4"


def test_discover_falls_back_to_assets_video_post_mp4(tmp_path):
    # The realistic filename a compose-family tool call actually produces
    # here (tool_bridge.py names non-final-compose outputs
    # "{tool_name}{variant_tag}_{unique}.{ext}") — not an arbitrary "clip.mp4"
    # a real run would never write.
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "assets" / "video_post").mkdir(parents=True)
    (proj / "assets" / "video_post" / "video_compose_abc123.mp4").write_bytes(b"x")
    assert _discover_render_url(proj, "p") == "/media/p/assets/video_post/video_compose_abc123.mp4"


def test_discover_falls_back_to_hyperframes_compose_output(tmp_path):
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "assets" / "video_post").mkdir(parents=True)
    (proj / "assets" / "video_post" / "hyperframes_compose_xyz.mp4").write_bytes(b"x")
    assert _discover_render_url(proj, "p") == "/media/p/assets/video_post/hyperframes_compose_xyz.mp4"


def test_discover_ignores_non_final_trim_stitch_clips(tmp_path):
    # Regression: the assets/video_post/ fallback used to accept ANY .mp4 in
    # that folder — broad enough to pick up an INTERMEDIATE trim/stitch clip
    # (tool_bridge.py writes video_trimmer_*/video_stitch_* outputs to this
    # same folder for any non-final video_post call) if one ran earlier in
    # the same stage's conversation, before a final compose call that then
    # failed. Only a compose-family tool's own output is a legitimate
    # stand-in for the finished render — trim/stitch clips must not be
    # picked up, even when they're the newest file in the folder.
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "assets" / "video_post").mkdir(parents=True)
    (proj / "assets" / "video_post" / "video_trimmer_abc123.mp4").write_bytes(b"x")
    (proj / "assets" / "video_post" / "video_stitch_def456.mp4").write_bytes(b"y")
    assert _discover_render_url(proj, "p") is None


def test_discover_ignores_raw_generation_clips(tmp_path):
    # Regression: the fallback used to glob assets/**/*.mp4 — broad enough to
    # match assets/video_generation/*.mp4, the RAW per-scene clips from
    # maas_video. Confirmed live: a compose stage that never actually
    # composed anything (all generation blocked, render_report honestly
    # documented the failure) still left a raw scene clip sitting in
    # assets/video_generation/ from an earlier stage — the broad glob picked
    # it and presented a random few-second clip as if it were the finished
    # film. Only assets/video_post/ (the compose-family tools' own capability
    # folder) is a legitimate fallback location.
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "assets" / "video_generation").mkdir(parents=True)
    (proj / "assets" / "video_generation" / "maas_video_abc123.mp4").write_bytes(b"x")
    assert _discover_render_url(proj, "p") is None


def test_discover_misnamed_compose_bin(tmp_path):
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "assets" / "video_post").mkdir(parents=True)
    (proj / "assets" / "video_post" / "video_compose_output.bin").write_bytes(b"x")
    assert _discover_render_url(proj, "p") == \
        "/media/p/assets/video_post/video_compose_output.bin"


def test_discover_none_when_empty(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    assert _discover_render_url(proj, "p") is None


# ── _discover_render_urls (A/B variant-aware) ────────────────────────────────

def test_discover_render_urls_none_for_single_render(tmp_path):
    # A normal (non-variant) job — only the plain final.mp4 exists. Callers
    # must fall back to the singular render_url in this case, so this needs
    # to return None, not a one-entry dict.
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "renders" / "final.mp4").write_bytes(b"x")
    assert _discover_render_urls(proj, "p") is None


def test_discover_render_urls_none_when_empty(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    assert _discover_render_urls(proj, "p") is None


def test_discover_render_urls_maps_each_variant(tmp_path):
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "renders" / "final_ltx-2-3.mp4").write_bytes(b"x")
    (proj / "renders" / "final_wan2-2.mp4").write_bytes(b"y")
    urls = _discover_render_urls(proj, "p")
    assert urls == {
        "ltx-2-3": "/media/p/renders/final_ltx-2-3.mp4",
        "wan2-2": "/media/p/renders/final_wan2-2.mp4",
    }


def test_discover_render_urls_bare_final_gets_default_slug_alongside_variant(tmp_path):
    # Edge case: a bare final.mp4 sitting next to a variant-tagged one (e.g.
    # a job that only tagged the SECOND compose call). Both must surface.
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "renders" / "final.mp4").write_bytes(b"x")
    (proj / "renders" / "final_wan2-2.mp4").write_bytes(b"y")
    urls = _discover_render_urls(proj, "p")
    assert urls == {
        "default": "/media/p/renders/final.mp4",
        "wan2-2": "/media/p/renders/final_wan2-2.mp4",
    }


# ── _missing_variants (A/B partial-render fabrication guard) ────────────────

def test_missing_variants_none_when_not_a_variant_job(tmp_path):
    assert _missing_variants(tmp_path, {}) is None
    assert _missing_variants(tmp_path, {"video_model_variants": ["only-one"]}) is None


def test_missing_variants_none_when_every_variant_rendered(tmp_path):
    (tmp_path / "renders").mkdir(parents=True)
    (tmp_path / "renders" / "final_ltx2.mp4").write_bytes(b"x")
    (tmp_path / "renders" / "final_wan2-2.mp4").write_bytes(b"y")
    options = {"video_model_variants": ["ltx2", "wan2.2"]}
    assert _missing_variants(tmp_path, options) is None


def test_missing_variants_flags_the_one_that_never_rendered(tmp_path):
    # Regression: the compose anti-fabrication check only required ANY render
    # file to exist — a 3-variant job where 2 of 3 render and the 3rd fails
    # would still "pass" that check and complete silently. Each declared
    # variant must have its own render file.
    (tmp_path / "renders").mkdir(parents=True)
    (tmp_path / "renders" / "final_ltx2.mp4").write_bytes(b"x")
    (tmp_path / "renders" / "final_wan2-2.mp4").write_bytes(b"y")
    # no final_kling-1.mp4 — this variant's generation failed
    options = {"video_model_variants": ["ltx2", "wan2.2", "kling-1"]}
    assert _missing_variants(tmp_path, options) == ["kling-1"]


# ── _url_for_render (storage-backend fallback narrowing) ─────────────────────

def test_url_for_render_uses_local_storage_by_default(tmp_path):
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    candidate = proj / "renders" / "final.mp4"
    candidate.write_bytes(b"x")
    assert _url_for_render(proj, "p", candidate) == "/media/p/renders/final.mp4"


def test_url_for_render_logs_and_falls_back_when_backend_raises(tmp_path, monkeypatch, caplog):
    # Regression: a bare `except Exception` around get_storage().url_for(...)
    # silently masked ANY failure, including a genuine bug in a real
    # (non-local) configured backend — the returned URL would just 404 with
    # no diagnostic anywhere. A broken backend must still fall back (so
    # render discovery doesn't hard-fail the job), but it must log the real
    # exception instead of swallowing it.
    import app.interfaces as interfaces_module

    class BrokenStorage:
        def url_for(self, project, rel):
            raise RuntimeError("bucket unreachable")

    monkeypatch.setattr(interfaces_module, "get_storage", lambda: BrokenStorage())
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    candidate = proj / "renders" / "final.mp4"
    candidate.write_bytes(b"x")

    import logging
    with caplog.at_level(logging.WARNING):
        url = _url_for_render(proj, "p", candidate)

    assert url == "/media/p/renders/final.mp4"
    assert any("bucket unreachable" in r.getMessage() for r in caplog.records)


# ── _brand_reference_image_data_uri ──────────────────────────────────────────

def test_brand_reference_image_data_uri_absent_without_path(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_runner, "OM_ROOT", tmp_path)
    assert _brand_reference_image_data_uri("some-kit", {}) is None
    assert _brand_reference_image_data_uri(None, {"reference_image_path": "reference.png"}) is None


def test_brand_reference_image_data_uri_reads_and_encodes(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_runner, "OM_ROOT", tmp_path)
    kit_dir = tmp_path / "brand_kits" / "acme-123"
    kit_dir.mkdir(parents=True)
    (kit_dir / "reference.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-but-nonempty")
    uri = _brand_reference_image_data_uri("acme-123", {"reference_image_path": "reference.png"})
    assert uri is not None
    assert uri.startswith("data:image/png;base64,")


def test_brand_reference_image_data_uri_skips_oversized_file_instead_of_truncating(tmp_path, monkeypatch):
    # A truncated data URI isn't a smaller image, it's corrupt — must be
    # skipped entirely (None) rather than handed to the agent half-cut.
    monkeypatch.setattr(stage_runner, "OM_ROOT", tmp_path)
    kit_dir = tmp_path / "brand_kits" / "acme-123"
    kit_dir.mkdir(parents=True)
    # base64 expands ~4/3x — this comfortably exceeds the char cap.
    (kit_dir / "reference.png").write_bytes(b"x" * (_MAX_REFERENCE_DATA_URI_CHARS))
    uri = _brand_reference_image_data_uri("acme-123", {"reference_image_path": "reference.png"})
    assert uri is None


def test_brand_reference_image_data_uri_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_runner, "OM_ROOT", tmp_path)
    assert _brand_reference_image_data_uri("acme-123", {"reference_image_path": "reference.png"}) is None


# ── artifact / brand-kit loading ─────────────────────────────────────────────

def test_load_artifacts_skips_invalid(tmp_path):
    a = tmp_path / "artifacts"
    a.mkdir()
    (a / "research.json").write_text('{"k": 1}')
    (a / "bad.json").write_text("{ not valid json")
    arts = _load_artifacts(tmp_path)
    assert arts["research"] == {"k": 1}
    assert "bad" not in arts


def test_load_brand_kit_absent():
    assert _load_brand_kit(None) == {}
    assert _load_brand_kit("definitely-not-a-real-kit-xyz") == {}


# ── O-1 regression: finish_reason=="stop" must NOT drop tool_calls ───────────

def _msg(content, tool_calls):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _resp(content, tool_calls, finish):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=_msg(content, tool_calls), finish_reason=finish)]
    )


def _tool_call(cid, name, arguments):
    return SimpleNamespace(id=cid, function=SimpleNamespace(name=name, arguments=arguments))


def test_finish_stop_with_tool_calls_still_executes(tmp_path, monkeypatch):
    # Turn 1: gateway returns finish_reason="stop" WHILE carrying a tool_call
    # (the exact shape the aiapbot shim can produce). Turn 2: no tool_calls → end.
    turn1 = _resp(
        "writing",
        [_tool_call("c1", "write_artifact",
                    '{"artifact_name": "research", "content": {"summary": "ok"}}')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    monkeypatch.setattr(
        stage_runner.llm.chat.completions, "create",
        lambda **kw: next(responses),
    )

    ok = stage_runner._run_agent_stage(
        "job-x", "research", "skill", tmp_path, {}, {},
    )
    assert ok is True
    # The artifact was written → the tool_call was executed, not dropped.
    written = tmp_path / "artifacts" / "research.json"
    assert written.exists()
    assert '"summary": "ok"' in written.read_text()


def test_no_tool_calls_ends_stage(tmp_path, monkeypatch):
    resp = _resp("nothing to do", None, "stop")
    monkeypatch.setattr(
        stage_runner.llm.chat.completions, "create",
        lambda **kw: resp,
    )
    ok = stage_runner._run_agent_stage("job-y", "research", "skill", tmp_path, {}, {})
    assert ok is True
    assert not (tmp_path / "artifacts").exists()  # no tool ran


# ── cancellation: checked once per turn, not just between stages ────────────

def test_cancel_requested_stops_mid_turn_without_calling_the_llm(tmp_path, monkeypatch):
    # A single stage can run for many minutes across many turns (confirmed
    # live: compose hit its turn ceiling) — cancellation must be checked
    # every turn, not just at stage boundaries, or a user cancelling a
    # long-running stage would wait for it to finish anyway. The check must
    # also run BEFORE the LLM call so a cancelled job doesn't burn one more
    # (paid, slow) completion request first.
    from app.store import JobStore
    ts = JobStore(persist_dir=tmp_path / "js")
    monkeypatch.setattr(stage_runner, "job_store", ts)
    ts.create("job-cancel", {})
    ts.update("job-cancel", cancel_requested=True)

    llm_called = []
    monkeypatch.setattr(
        stage_runner.llm.chat.completions, "create",
        lambda **kw: llm_called.append(1) or _resp("should never run", None, "stop"),
    )

    with pytest.raises(stage_runner.JobCancelled):
        stage_runner._run_agent_stage("job-cancel", "research", "skill", tmp_path, {}, {})
    assert llm_called == []


def test_no_cancellation_requested_runs_normally(tmp_path, monkeypatch):
    # Sibling of the test above — confirms the cancel_requested check itself
    # doesn't false-positive and block an ordinary run.
    from app.store import JobStore
    ts = JobStore(persist_dir=tmp_path / "js")
    monkeypatch.setattr(stage_runner, "job_store", ts)
    ts.create("job-ok", {})

    resp = _resp("nothing to do", None, "stop")
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", lambda **kw: resp)

    assert stage_runner._run_agent_stage("job-ok", "research", "skill", tmp_path, {}, {}) is True


# ── mid-stage stall nudging (agent stops to ask, artifact not written) ──────

def test_sample_preview_pauses_instead_of_auto_continuing(tmp_path, monkeypatch):
    # Regression: confirmed live — asset-director.md's own "Sample Preview"
    # step tells the agent to generate one sample of each asset type and
    # confirm with the user before batch-generating the rest. This used to
    # be silently overridden with a "no human is available, proceed
    # autonomously" nudge, which defeated the skill's own wasted-spend
    # safeguard. It must now pause for a REAL approval instead.
    turn1 = _resp(
        "Here are samples of each asset — please confirm before I continue.",
        None, "stop",
    )
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", lambda **kw: turn1)

    with pytest.raises(stage_runner.SamplePreviewNeeded) as exc_info:
        stage_runner._run_agent_stage(
            "job-nudge1", "assets", "skill", tmp_path, {}, {}, produces=["asset_manifest"],
        )
    spn = exc_info.value
    assert spn.sample_iteration == 0
    assert "please confirm" in spn.preview_text.lower()
    # The paused conversation carries the agent's own message so a resume
    # doesn't have to re-explain itself.
    assert spn.messages[-1]["role"] == "assistant"
    assert not (tmp_path / "artifacts" / "asset_manifest.json").exists()


def test_sample_preview_resume_continues_the_same_conversation(tmp_path, monkeypatch):
    # After approval, _run_agent_stage must pick up with the resumed
    # conversation (not rebuild the initial prompt from scratch) and be able
    # to complete normally from there.
    resume = [
        {"role": "user", "content": "## Director Skill\noriginal prompt"},
        {"role": "assistant", "content": "Here's a sample — please confirm."},
        {"role": "user", "content": "Approved — proceed to complete the stage."},
    ]
    turn = _resp(
        "writing",
        [_tool_call("c1", "write_artifact",
                    '{"artifact_name": "asset_manifest", "content": {"ok": true}}')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn, turn2])
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return next(responses)
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    ok = stage_runner._run_agent_stage(
        "job-resume1", "assets", "skill", tmp_path, {}, {}, produces=["asset_manifest"],
        resume_messages=resume, sample_iteration=1,
    )
    assert ok is True
    assert (tmp_path / "artifacts" / "asset_manifest.json").exists()
    # The original prompt was NOT rebuilt — the resumed history is exactly
    # what was passed in, with the new turn's messages appended after it.
    assert captured["messages"][:3] == resume


def test_no_nudge_when_artifact_already_written(tmp_path, monkeypatch):
    # A text-only turn AFTER the artifact already exists is genuine
    # completion (the prompt itself asks for a brief confirmation once
    # done) — must return immediately, not waste a nudge.
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "asset_manifest.json").write_text('{"ok": true}')
    resp = _resp("All done, produced the asset manifest above.", None, "stop")
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return resp
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    ok = stage_runner._run_agent_stage(
        "job-nudge2", "assets", "skill", tmp_path, {}, {}, produces=["asset_manifest"],
    )
    assert ok is True
    # Only the original prompt — no nudge appended.
    user_msgs = [m for m in captured["messages"] if m.get("role") == "user"]
    assert len(user_msgs) == 1


def test_sample_preview_iteration_budget_exhausted_ends_stage(tmp_path, monkeypatch):
    # A genuinely stuck agent (still hasn't written the artifact after
    # exhausting its pause/resume budget) must stop rather than pause again —
    # the caller's own _missing_produces check catches the still-missing
    # artifact and fails the stage from there.
    stall = _resp("Still need confirmation before I continue.", None, "stop")
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", lambda **kw: stall)

    ok = stage_runner._run_agent_stage(
        "job-nudge3", "assets", "skill", tmp_path, {}, {}, produces=["asset_manifest"],
        sample_iteration=stage_runner.MAX_SAMPLE_ITERATIONS,
    )
    assert ok is True
    assert not (tmp_path / "artifacts").exists()


# ── truncated tool-call arguments: finish_reason-aware diagnosis ────────────

def test_truncated_args_length_limit_gives_shorten_hint(tmp_path, monkeypatch):
    # finish_reason="length" means the shared narration+JSON budget really was
    # exhausted — the agent should be told to write less next time.
    turn1 = _resp(
        "writing",
        [_tool_call("c1", "write_artifact", '{"artifact_name": "scene_pla')],  # cut off mid-string
        "length",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return next(responses)
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    stage_runner._run_agent_stage("job-len", "scene_plan", "skill", tmp_path, {}, {})

    tool_msgs = [m["content"] for m in captured["messages"] if m.get("role") == "tool"]
    assert tool_msgs
    assert "finish_reason=length" in tool_msgs[0]
    assert "more concise" in tool_msgs[0]


def test_truncated_args_non_length_gives_malformed_hint(tmp_path, monkeypatch):
    # A non-"length" finish_reason with unparsable JSON is a different failure
    # (a genuinely malformed call) — telling the agent to "write less" would
    # be misleading advice when the visible content wasn't actually large.
    turn1 = _resp(
        "writing",
        [_tool_call("c1", "write_artifact", '{"artifact_name": "scene_pla')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return next(responses)
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    stage_runner._run_agent_stage("job-malformed", "scene_plan", "skill", tmp_path, {}, {})

    tool_msgs = [m["content"] for m in captured["messages"] if m.get("role") == "tool"]
    assert tool_msgs
    assert "finish_reason=stop" in tool_msgs[0]
    assert "wasn't a length limit" in tool_msgs[0]
    assert "more concise" not in tool_msgs[0]


def test_llm_call_uses_generous_max_tokens(tmp_path, monkeypatch):
    # Regression: 8192 shared between narration and a large write_artifact
    # payload (e.g. a multi-clip scene_plan) could exhaust the budget before
    # the JSON finished, truncating arguments to just a few characters.
    resp = _resp("done", None, "stop")
    captured = {}
    def fake_create(**kw):
        captured.update(kw)
        return resp
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    stage_runner._run_agent_stage("job-budget", "scene_plan", "skill", tmp_path, {}, {})
    assert captured["max_tokens"] >= 16384


def test_llm_client_has_an_explicit_request_timeout():
    # Regression: the OpenAI client had no explicit timeout — a hung gateway
    # blocked the asyncio.to_thread worker running a stage indefinitely, with
    # no error event and no user-visible failure. Must be an explicit,
    # positive, finite value, not the SDK's own NOT_GIVEN default.
    assert stage_runner.llm.timeout == stage_runner.LLM_REQUEST_TIMEOUT_SECONDS
    assert 0 < stage_runner.LLM_REQUEST_TIMEOUT_SECONDS < float("inf")


def test_tool_keyerror_reports_missing_parameter_not_bare_repr(tmp_path, monkeypatch):
    # Regression: a tool indexing inputs["some_field"] with no fallback raises
    # a bare KeyError, which str()s to just "'some_field'" — cryptic enough
    # that the agent can't tell what to fix and repeats the same broken call
    # until the stage burns through MAX_TURNS (this exact pattern hit
    # video_compose's "operation" key live). The message fed back to the
    # agent must name the parameter explicitly so it can self-correct.
    turn1 = _resp(
        "composing",
        [_tool_call("c1", "run_openmontage_tool",
                    '{"tool_name": "video_compose", "inputs": {}}')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    monkeypatch.setattr(
        stage_runner, "execute_tool",
        lambda *a, **k: (_ for _ in ()).throw(KeyError("operation")),
    )

    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return next(responses)
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    stage_runner._run_agent_stage("job-w", "compose", "skill", tmp_path, {}, {})

    tool_result_msgs = [m["content"] for m in captured["messages"] if m.get("role") == "tool"]
    assert tool_result_msgs, "expected a tool-role message with the error"
    assert "missing required parameter" in tool_result_msgs[0].lower()
    assert "operation" in tool_result_msgs[0]
    # The bare, uninterpretable KeyError repr must NOT be the whole message.
    assert tool_result_msgs[0] != "ERROR: Tool execution failed: 'operation'"


# ── tool_call event summary (progress-log clarity) ───────────────────────────

def test_tool_call_summary_shows_path_not_param_names(tmp_path, monkeypatch):
    # Regression: the summary used to be f"{tool_name}({list(tool_args.keys())})"
    # — literally the parameter NAMES, so every read_file call rendered the
    # identical "read_file(['path'])" in the progress log regardless of which
    # file was actually read.
    turn1 = _resp(
        "reading",
        [_tool_call("c1", "read_file", '{"path": "skills/meta/foo.md"}')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    monkeypatch.setattr(
        stage_runner.llm.chat.completions, "create", lambda **kw: next(responses),
    )
    (tmp_path / "skills" / "meta").mkdir(parents=True)
    (tmp_path / "skills" / "meta" / "foo.md").write_text("hi")
    monkeypatch.setattr(stage_runner, "OM_ROOT", tmp_path)

    events = []
    monkeypatch.setattr(stage_runner, "_emit", lambda job_id, ev: events.append(ev))

    stage_runner._run_agent_stage("job-t1", "idea", "skill", tmp_path, {}, {})

    tool_call_events = [e for e in events if e["type"] == "tool_call"]
    assert tool_call_events
    assert tool_call_events[0]["summary"] == "read_file(skills/meta/foo.md)"


def test_tool_call_summary_shows_artifact_name(tmp_path, monkeypatch):
    turn1 = _resp(
        "writing",
        [_tool_call("c1", "write_artifact",
                    '{"artifact_name": "brief", "content": {"a": 1}}')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    monkeypatch.setattr(
        stage_runner.llm.chat.completions, "create", lambda **kw: next(responses),
    )

    events = []
    monkeypatch.setattr(stage_runner, "_emit", lambda job_id, ev: events.append(ev))

    stage_runner._run_agent_stage("job-t2", "idea", "skill", tmp_path, {}, {})

    tool_call_events = [e for e in events if e["type"] == "tool_call"]
    assert tool_call_events
    assert tool_call_events[0]["summary"] == "write_artifact(brief)"


def test_tool_call_summary_shows_target_tool_name(tmp_path, monkeypatch):
    turn1 = _resp(
        "generating",
        [_tool_call("c1", "run_openmontage_tool",
                    '{"tool_name": "maas_video", "inputs": {"prompt": "x"}}')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    monkeypatch.setattr(
        stage_runner.llm.chat.completions, "create", lambda **kw: next(responses),
    )
    monkeypatch.setattr(stage_runner, "execute_tool", lambda *a, **k: '{"success": true}')

    events = []
    monkeypatch.setattr(stage_runner, "_emit", lambda job_id, ev: events.append(ev))

    stage_runner._run_agent_stage("job-t3", "assets", "skill", tmp_path, {}, {})

    tool_call_events = [e for e in events if e["type"] == "tool_call"]
    assert tool_call_events
    assert tool_call_events[0]["summary"] == "run_openmontage_tool(maas_video)"


def test_prompt_tells_agent_the_produces_name(tmp_path, monkeypatch):
    # Regression: stages whose name differs from what they produce (e.g. stage
    # "idea" produces "brief") used to leave the agent guessing artifact_name
    # from the stage name alone. The prompt must state the real name(s)
    # explicitly when the manifest provides a `produces` list.
    resp = _resp("done", None, "stop")
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return resp
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    # A text-only turn with neither artifact written now pauses for a real
    # sample-preview approval (see SamplePreviewNeeded) rather than
    # returning — this test only cares about the prompt content, which is
    # captured before that pause fires.
    with pytest.raises(stage_runner.SamplePreviewNeeded):
        stage_runner._run_agent_stage(
            "job-z", "idea", "skill", tmp_path, {}, {},
            produces=["brief", "decision_log"],
        )
    user_msg = captured["messages"][0]["content"]
    assert "Expected Artifact Name" in user_msg
    assert 'artifact_name="brief"' in user_msg
    assert "decision_log" in user_msg   # secondary artifact mentioned too


def test_prompt_falls_back_to_stage_name_without_produces(tmp_path, monkeypatch):
    resp = _resp("done", None, "stop")
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return resp
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    stage_runner._run_agent_stage("job-z2", "custom_stage", "skill", tmp_path, {}, {})
    user_msg = captured["messages"][0]["content"]
    assert 'artifact_name="custom_stage"' in user_msg or '"custom_stage"' in user_msg


# ── quality-review smell fixes: truncation markers, per-stage tuning ────────

def test_truncate_json_for_prompt_leaves_short_text_untouched():
    assert _truncate_json_for_prompt("short", 100) == "short"


def test_truncate_json_for_prompt_adds_marker_when_cut():
    text = "x" * 50
    out = _truncate_json_for_prompt(text, 10)
    assert out.startswith("x" * 10)
    assert "truncated" in out
    assert "50 total chars" in out


def test_last_failure_message_finds_most_recent_matching_error(tmp_path, monkeypatch):
    ts = __import__("app.store", fromlist=["JobStore"]).JobStore(persist_dir=tmp_path / "js")
    monkeypatch.setattr(stage_runner, "job_store", ts)
    ts.create("job-fail", {})
    ts.push_event("job-fail", {"type": "error", "stage": "assets", "message": "first failure"})
    ts.push_event("job-fail", {"type": "agent_text", "stage": "assets", "text": "unrelated"})
    ts.push_event("job-fail", {"type": "error", "stage": "assets", "message": "second failure"})
    ts.push_event("job-fail", {"type": "error", "stage": "script", "message": "different stage"})
    assert _last_failure_message("job-fail", "assets") == "second failure"


def test_last_failure_message_empty_when_no_error(tmp_path, monkeypatch):
    ts = __import__("app.store", fromlist=["JobStore"]).JobStore(persist_dir=tmp_path / "js")
    monkeypatch.setattr(stage_runner, "job_store", ts)
    ts.create("job-clean", {})
    assert _last_failure_message("job-clean", "assets") == ""


def test_assets_stage_has_higher_max_turns_and_lower_temperature():
    # Regression: MAX_TURNS/temperature used to be single global constants
    # shared by every stage regardless of complexity — assets (many
    # generation calls per scene) needs more turns, and structured/
    # schema-writing stages benefit from lower temperature than the
    # genuinely creative ones.
    assets = next(s for s in stage_runner.CINEMATIC_STAGES if s["name"] == "assets")
    assert assets["max_turns"] > stage_runner.MAX_TURNS
    assert assets["temperature"] < 0.7


def test_run_agent_stage_honors_custom_max_turns_and_temperature(tmp_path, monkeypatch):
    # Keep calling a real tool every turn (never a text-only stall) so the
    # loop can only end by exhausting max_turns, isolating that from the
    # separate sample-preview iteration budget.
    keep_reading = _resp(
        "reading", [_tool_call("c1", "read_file", '{"path": "does-not-exist.xyz"}')], "stop",
    )
    captured = {}
    def fake_create(**kw):
        captured.setdefault("calls", 0)
        captured["calls"] += 1
        captured["temperature"] = kw["temperature"]
        return keep_reading
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    ok = stage_runner._run_agent_stage(
        "job-turns", "assets", "skill", tmp_path, {}, {},
        max_turns=3, temperature=0.3,
    )
    assert ok is False   # exhausted max_turns without completing
    assert captured["calls"] == 3   # bounded by the custom max_turns, not the global default
    assert captured["temperature"] == 0.3


def test_compose_stage_has_higher_max_turns():
    # Regression: compose is at least as tool-call-heavy as "assets" (which
    # already has max_turns=40 with a rationale comment) but stayed at the
    # global default (20) — confirmed live: compose hit the 20-turn ceiling
    # in a real run.
    compose = next(s for s in stage_runner.CINEMATIC_STAGES if s["name"] == "compose")
    assert compose["max_turns"] > stage_runner.MAX_TURNS


# ── prior-artifacts prompt budget: required artifacts must survive bloat ────

def test_build_prior_artifacts_text_required_survives_large_unrelated_ones():
    # Regression: a flat 6000-char cap on the whole concatenated prior-
    # artifacts JSON blob, truncated positionally, meant a stage's own
    # required_artifacts_in artifact routinely never survived into the
    # visible window once the combined dump grew large (confirmed live at
    # "compose": >100,000 combined chars, edit_decisions/asset_manifest
    # crowded out by research_brief). The required artifact's actual content
    # must survive in full even surrounded by several large unrelated ones.
    marker = "UNIQUE_REQUIRED_MARKER_VALUE"
    artifacts = {f"unrelated_{i}": {"blob": "x" * 30000} for i in range(5)}
    artifacts["needed_artifact"] = {"key": marker}

    text = _build_prior_artifacts_text(artifacts, ["needed_artifact"])

    assert marker in text   # actual content, not just a truncation marker
    assert "needed_artifact" in text


def test_build_prior_artifacts_text_caps_non_required_combined():
    artifacts = {f"unrelated_{i}": {"blob": "x" * 30000} for i in range(5)}
    text = _build_prior_artifacts_text(artifacts, [])
    # None of these are required — total non-required budget is small, so the
    # combined output must be much smaller than the raw 150,000 chars of blob.
    assert len(text) < 10000


def test_prior_artifacts_required_survives_via_run_agent_stage(tmp_path, monkeypatch):
    # End-to-end through _run_agent_stage's actual prompt construction (not
    # just the helper in isolation).
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    marker = "UNIQUE_REQUIRED_MARKER_" + "z" * 50
    (artifacts_dir / "needed_artifact.json").write_text(json.dumps({"key": marker}))
    for i in range(5):
        (artifacts_dir / f"unrelated_{i}.json").write_text(json.dumps({"blob": "x" * 30000}))

    resp = _resp("done", None, "stop")
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return resp
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    stage_runner._run_agent_stage(
        "job-req", "compose", "skill", tmp_path, {}, {},
        required_artifacts_in=["needed_artifact"],
    )
    user_msg = captured["messages"][0]["content"]
    assert marker in user_msg


# ── "Your job" section: no re-fetching inlined artifacts via read_file ─────

def test_prompt_tells_agent_not_to_refetch_artifacts_and_gives_skill_path_template(tmp_path, monkeypatch):
    # Confirmed live: agents repeatedly guessed wrong artifact/skill-doc
    # paths via read_file across nearly every stage — wasting turns re-
    # fetching data that's already inlined, and guessing nonexistent
    # skills/core/... paths for pipeline-specific skill docs.
    resp = _resp("done", None, "stop")
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return resp
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    stage_runner._run_agent_stage("job-nofetch", "compose", "skill", tmp_path, {}, {})
    user_msg = captured["messages"][0]["content"]
    assert "do NOT use `read_file`" in user_msg
    assert "fully inlined above" in user_msg
    assert "skills/pipelines/{pipeline}/{stage}-director.md" in user_msg
    assert "skills/core/" in user_msg


# ── BudgetGateNeeded: converted from BudgetExceededError with valid resume ──

def test_budget_gate_needed_backfills_placeholders_for_blocked_and_sibling_calls(tmp_path, monkeypatch):
    # Regression: BudgetExceededError used to propagate straight out of
    # _run_agent_stage, discarding `messages` entirely — on approval the
    # caller had no choice but to restart the whole stage conversation from
    # scratch, orphaning any assets already generated earlier in that same
    # conversation. It must now be converted to BudgetGateNeeded carrying the
    # conversation so far, with a placeholder tool-role response backfilled
    # for the blocked call AND for every sibling tool_call in the same
    # assistant turn that was never reached — every tool_call in an assistant
    # turn needs a matching tool response, or the next completion call would
    # be malformed.
    turn1 = _resp(
        "working",
        [
            _tool_call("c1", "run_openmontage_tool", '{"tool_name": "maas_video", "inputs": {}}'),
            _tool_call("c2", "run_openmontage_tool", '{"tool_name": "maas_video", "inputs": {}}'),
            _tool_call("c3", "run_openmontage_tool", '{"tool_name": "maas_video", "inputs": {}}'),
        ],
        "stop",
    )
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", lambda **kw: turn1)

    call_count = {"n": 0}
    def fake_execute_tool(tool_name, tool_args, project_dir, **kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return '{"success": true}'
        # tool_bridge.py's BudgetExceededError.tool_name carries the actual
        # sub-tool called (e.g. "maas_video"), not the dispatch-level
        # "run_openmontage_tool" name — mirror that here.
        raise stage_runner.BudgetExceededError(
            "over budget", tool_name="maas_video", est_cost=50.0, projected_cny=60.0,
        )
    monkeypatch.setattr(stage_runner, "execute_tool", fake_execute_tool)

    with pytest.raises(stage_runner.BudgetGateNeeded) as exc_info:
        stage_runner._run_agent_stage("job-bgn", "assets", "skill", tmp_path, {}, {})

    bgn = exc_info.value
    tool_msgs = {m["tool_call_id"]: m["content"] for m in bgn.messages if m.get("role") == "tool"}
    assert tool_msgs["c1"] == '{"success": true}'          # already ran, untouched
    assert "BLOCKED" in tool_msgs["c2"]                     # the call that actually blocked
    assert "SKIPPED" in tool_msgs["c3"]                     # sibling never reached
    assert bgn.budget_exc.tool_name == "maas_video"
    assert bgn.budget_exc.projected_cny == 60.0
    # Only 2 tool calls actually executed — the 3rd never ran.
    assert call_count["n"] == 2


# ── render_report path divergence (warn, don't fail) ────────────────────────

def test_render_report_path_diverges_flags_mismatch(tmp_path):
    (tmp_path / "renders").mkdir()
    discovered = tmp_path / "renders" / "final.mp4"
    discovered.write_bytes(b"x")
    render_report = {"outputs": [{"path": "renders/wrong_name.mp4"}]}
    assert _render_report_path_diverges(tmp_path, render_report, discovered) == "renders/wrong_name.mp4"


def test_render_report_path_diverges_none_when_matching(tmp_path):
    (tmp_path / "renders").mkdir()
    discovered = tmp_path / "renders" / "final.mp4"
    discovered.write_bytes(b"x")
    render_report = {"outputs": [{"path": "renders/final.mp4"}]}
    assert _render_report_path_diverges(tmp_path, render_report, discovered) is None


def test_render_report_path_diverges_none_without_outputs_or_discovery():
    assert _render_report_path_diverges(SimpleNamespace(), {}, None) is None
    assert _render_report_path_diverges(SimpleNamespace(), {"outputs": []}, None) is None


# ── publish_log export validation (generalized anti-fabrication) ───────────

def test_validate_publish_log_exports_flags_missing_file(tmp_path):
    publish_log = {"entries": [
        {"platform": "youtube", "status": "exported",
         "export_path": "exports/teaser.mp4", "timestamp": "2026-01-01T00:00:00Z"},
    ]}
    assert _validate_publish_log_exports(tmp_path, publish_log) == ["exports/teaser.mp4"]


def test_validate_publish_log_exports_passes_when_file_exists(tmp_path):
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "teaser.mp4").write_bytes(b"x")
    publish_log = {"entries": [
        {"platform": "youtube", "status": "exported",
         "export_path": "exports/teaser.mp4", "timestamp": "2026-01-01T00:00:00Z"},
    ]}
    assert _validate_publish_log_exports(tmp_path, publish_log) == []


def test_validate_publish_log_exports_ignores_non_completed_statuses(tmp_path):
    # "failed"/"pending_review" entries don't claim a real file was produced
    # — must not be flagged even though no file exists.
    publish_log = {"entries": [
        {"platform": "youtube", "status": "pending_review",
         "export_path": "exports/teaser.mp4", "timestamp": "x"},
        {"platform": "instagram", "status": "failed",
         "export_path": "exports/nope.mp4", "timestamp": "x"},
    ]}
    assert _validate_publish_log_exports(tmp_path, publish_log) == []


# ── render_runtime consistency (edit vs. proposal, unlogged divergence) ─────

def test_render_runtime_consistency_flags_silent_divergence(tmp_path):
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "proposal_packet.json").write_text(
        json.dumps({"production_plan": {"render_runtime": "remotion"}})
    )
    (tmp_path / "artifacts" / "edit_decisions.json").write_text(
        json.dumps({"render_runtime": "ffmpeg"})
    )
    msg = _check_render_runtime_consistency(tmp_path)
    assert msg is not None
    assert "remotion" in msg and "ffmpeg" in msg


def test_render_runtime_consistency_passes_when_matching(tmp_path):
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "proposal_packet.json").write_text(
        json.dumps({"production_plan": {"render_runtime": "remotion"}})
    )
    (tmp_path / "artifacts" / "edit_decisions.json").write_text(
        json.dumps({"render_runtime": "remotion"})
    )
    assert _check_render_runtime_consistency(tmp_path) is None


def test_render_runtime_consistency_passes_when_justified_by_decision_log(tmp_path):
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "proposal_packet.json").write_text(
        json.dumps({"production_plan": {"render_runtime": "remotion"}})
    )
    (tmp_path / "artifacts" / "edit_decisions.json").write_text(
        json.dumps({"render_runtime": "ffmpeg"})
    )
    (tmp_path / "artifacts" / "decision_log.json").write_text(json.dumps({
        "decisions": [{
            "decision_id": "d-002", "stage": "edit", "category": "render_runtime_selection",
            "subject": "runtime override",
            "options_considered": [{"option_id": "o1", "label": "ffmpeg", "score": 1, "reason": "y"}],
            "selected": "o1", "reason": "remotion unavailable",
        }],
    }))
    assert _check_render_runtime_consistency(tmp_path) is None


def test_render_runtime_consistency_ignores_decision_logged_at_a_different_stage(tmp_path):
    # A render_runtime_selection entry logged at "proposal" (the ORIGINAL
    # decision that locked the value) must not by itself excuse a later
    # silent divergence introduced at "edit" — only a NEW entry logged at
    # "edit" specifically justifies the override.
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "proposal_packet.json").write_text(
        json.dumps({"production_plan": {"render_runtime": "remotion"}})
    )
    (tmp_path / "artifacts" / "edit_decisions.json").write_text(
        json.dumps({"render_runtime": "ffmpeg"})
    )
    (tmp_path / "artifacts" / "decision_log.json").write_text(json.dumps({
        "decisions": [{
            "decision_id": "d-001", "stage": "proposal", "category": "render_runtime_selection",
            "subject": "initial runtime choice",
            "options_considered": [{"option_id": "o1", "label": "remotion", "score": 1, "reason": "y"}],
            "selected": "o1", "reason": "best fit",
        }],
    }))
    assert _check_render_runtime_consistency(tmp_path) is not None
