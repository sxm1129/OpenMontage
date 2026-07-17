"""Shared plumbing for the capability selectors.

video_selector, tts_selector and image_selector each hand-copied the same
registry lookup, scoring flow, rank mode and result decoration (audit
2026-07-15, structural item 1). The copies had already drifted, so this base
unifies only what the three genuinely agree on and routes every real
difference through a hook. Precedent: MaasBaseTool, extracted for the same
reason.

Deliberately NOT in the family: screen_capture_selector. It shares
get_status() and the word "selector" — no scoring, no rank mode, and its
_providers() returns a dict, not a list.

## execute() lives ONLY here

BaseTool.__init_subclass__ auto-wraps each subclass's own `execute` with
_instrument_execute. A base execute() PLUS a subclass override calling
super() would wrap the same logical call twice: duplicate Backlot events,
and the selector's own event lands at depth 1 — the slot a PROVIDER occupies
— corrupting the depth-0 cost attribution that _instrument_execute
documents. So subclasses MUST NOT define execute(); they customize through
the hooks below.
"""

from __future__ import annotations

from typing import Any

from tools.base_tool import BaseTool, ToolResult, ToolStatus


class SelectorBase(BaseTool):
    """Scored, registry-discovering selector for one capability.

    Subclass contract:
      - set `capability` (drives provider discovery)
      - set `_prompt_key` / `_default_operation` (task-context shaping)
      - override `_no_provider_error()` for the failure message
      - optionally override `_filter_candidates()` (default: no filtering),
        `_adapt_inputs()` (default: identity), `_rank_inputs()`
      - NEVER override `execute()`
    """

    # Input key carrying the user's prompt/text, and the operation assumed
    # when the caller doesn't name one.
    _prompt_key: str = "prompt"
    _default_operation: str = "generate"

    # ---- Discovery ----------------------------------------------------

    def _providers(self) -> list[BaseTool]:
        """Auto-discover providers for this capability from the registry."""
        from tools.tool_registry import registry
        registry.ensure_discovered()
        return [t for t in registry.get_by_capability(self.capability)
                if t.name != self.name]

    @property
    def fallback_tools(self) -> list[str]:
        """Dynamically built from discovered providers."""
        return [t.name for t in self._providers()]

    @property
    def provider_matrix(self) -> dict[str, dict[str, str]]:
        """Built at runtime from each provider's best_for field."""
        matrix: dict[str, dict[str, str]] = {}
        for tool in self._providers():
            strength = ", ".join(tool.best_for) if tool.best_for else tool.name
            matrix[tool.provider] = {"tool": tool.name, "strength": strength}
        return matrix

    def get_status(self) -> ToolStatus:
        if any(tool.get_status() == ToolStatus.AVAILABLE for tool in self._providers()):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    # ---- Hooks --------------------------------------------------------

    def _filter_candidates(
        self, inputs: dict[str, Any], candidates: list[BaseTool]
    ) -> list[BaseTool]:
        """Drop providers that can't serve this request. Default: keep all."""
        return candidates

    def _adapt_inputs(self, inputs: dict[str, Any], tool: BaseTool) -> dict[str, Any]:
        """Shape the payload for the chosen provider. Default: pass through.

        Identity by default because tts and video forward `inputs` (including
        the selector's own preferred_provider/allowed_providers) to the
        provider, while image copies and strips. Hoisting either behavior
        into the base would change what every OTHER provider receives — a
        deliberate convergence, not a dedup. Pinned by
        test_selector_contract's D4 tests.
        """
        return inputs

    def _rank_inputs(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Inputs used for rank mode. Default: unchanged."""
        return inputs

    def _no_provider_error(self) -> str:
        return f"No {self.capability} provider available."

    def _tool_selectable(self, tool: BaseTool, inputs: dict[str, Any]) -> bool:
        """Whether a provider may be chosen. Default: it must be AVAILABLE."""
        return tool.get_status() == ToolStatus.AVAILABLE

    # ---- Scoring flow -------------------------------------------------

    def _prepare_task_context(self, inputs: dict[str, Any]) -> dict[str, Any]:
        from lib.scoring import normalize_task_context

        return normalize_task_context(
            inputs.get("task_context", {}),
            prompt=str(inputs.get(self._prompt_key, "")),
            capability=self.capability,
            operation=str(inputs.get("operation", self._default_operation)),
        )

    def _select_best_tool(
        self,
        inputs: dict[str, Any],
        candidates: list[BaseTool],
        task_context: dict[str, Any],
    ) -> tuple[BaseTool | None, object]:
        """Highest-scored selectable provider, honoring an explicit preference."""
        from lib.scoring import rank_providers

        preferred = self._resolve_preferred(inputs)
        allowed = set(inputs.get("allowed_providers") or [])
        if allowed:
            candidates = [tool for tool in candidates if tool.provider in allowed]
        candidates = self._filter_candidates(inputs, candidates)

        rankings = rank_providers(candidates, task_context)

        # provider → first selectable tool for it
        tool_by_provider: dict[str, BaseTool] = {}
        for tool in candidates:
            if tool.provider not in tool_by_provider and self._tool_selectable(tool, inputs):
                tool_by_provider[tool.provider] = tool

        if preferred != "auto":
            for score in rankings:
                if score.provider == preferred and score.provider in tool_by_provider:
                    return tool_by_provider[score.provider], score

        for score in rankings:
            if score.provider in tool_by_provider:
                return tool_by_provider[score.provider], score

        return None, None

    def _resolve_preferred(self, inputs: dict[str, Any]) -> str:
        """The requested provider, or "auto". Hook for env-hint mapping."""
        return str(inputs.get("preferred_provider", "auto"))

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        candidates = self._filter_candidates(inputs, self._providers())
        if not candidates:
            return 0.0
        tool, _ = self._select_best_tool(
            inputs, candidates, self._prepare_task_context(inputs)
        )
        return tool.estimate_cost(inputs) if tool else 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        candidates = self._providers()
        if not candidates:
            return 0.0
        tool, _ = self._select_best_tool(
            inputs, candidates, self._prepare_task_context(inputs)
        )
        return tool.estimate_runtime(inputs) if tool else 0.0

    # ---- The one execute() --------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        from lib.scoring import rank_providers

        candidates = self._providers()

        # Rank mode — scored rankings, no generation.
        if inputs.get("operation") == "rank":
            rank_inputs = self._rank_inputs(inputs)
            task_context = self._prepare_task_context(rank_inputs)
            ranked_candidates = self._filter_candidates(rank_inputs, candidates)
            rankings = rank_providers(ranked_candidates, task_context)
            return ToolResult(
                success=True,
                data={
                    "rankings": self._serialize_rankings(ranked_candidates, rankings),
                    "explanation": "\n".join(r.explain() for r in rankings[:5]),
                    "normalized_task_context": task_context,
                },
            )

        task_context = self._prepare_task_context(inputs)
        tool, score = self._select_best_tool(inputs, candidates, task_context)
        if tool is None:
            return ToolResult(success=False, error=self._no_provider_error())

        payload = self._adapt_inputs(inputs, tool)
        dropped = self._detect_dropped_params(payload, tool)
        result = tool.execute(payload)
        if result.success and dropped:
            # Audit 2026-07-16, Wave 3 item 18: selectors advertise expressive
            # params (pitch, instructions, voice_performance, input_type=ssml)
            # and forward them wholesale, but providers only read the fields
            # in their OWN input_schema — everything else was silently
            # discarded, so the script stage's carefully-authored voice
            # performance plan never reached the audio and nobody knew. The
            # provider's input_schema IS the machine-checkable support
            # matrix; surface the mismatch instead of eating it.
            result.data["dropped_params"] = dropped
            result.data["dropped_params_note"] = (
                f"{tool.name} does not consume these request params (absent "
                f"from its input_schema); they had NO effect on the output: "
                f"{', '.join(dropped)}. Pick a provider that supports them "
                f"(see each provider's input_schema) or adjust the request."
            )
            import logging
            logging.getLogger("selector").warning(
                "%s dropped unsupported params for %s: %s",
                self.name, tool.name, dropped,
            )
        if result.success:
            result.data.setdefault("selected_tool", tool.name)
            result.data["selected_provider"] = tool.provider
            result.data["selection_reason"] = (
                score.explain() if score else f"Selected {tool.provider} ({tool.name})"
            )
            if score:
                result.data["provider_score"] = score.to_dict()
            result.data.update(self._tool_context_payload(tool))
            result.data["alternatives_considered"] = [
                t.name for t in candidates
                if t.name != tool.name and t.get_status().value == "available"
            ]
        return result

    # ---- Support-matrix check ------------------------------------------

    # Keys that belong to the SELECTOR protocol — providers legitimately
    # never declare these, so they are not "dropped".
    _SELECTOR_CONTROL_KEYS = frozenset({
        "preferred_provider",
        "allowed_providers",
        "task_context",
        "operation",
    })

    def _detect_dropped_params(self, payload: dict[str, Any], tool: BaseTool) -> list[str]:
        """Meaningful request params the chosen provider will silently ignore.

        A param counts as dropped when it carries a real value but does not
        appear in the provider's input_schema properties — the schema is the
        provider's declared support matrix.
        """
        props = (getattr(tool, "input_schema", None) or {}).get("properties")
        if not isinstance(props, dict):
            return []
        return sorted(
            k for k, v in payload.items()
            if k not in props
            and k not in self._SELECTOR_CONTROL_KEYS
            and v not in (None, "", {}, [])
        )

    # ---- Payload shaping ----------------------------------------------

    @staticmethod
    def _tool_context_payload(tool: BaseTool) -> dict[str, Any]:
        info = tool.get_info()
        return {
            "selected_tool_agent_skills": info.get("agent_skills", []),
            "required_agent_skills": info.get("agent_skills", []),
            "selected_tool_usage_location": info.get("usage_location"),
            "selected_tool_best_for": info.get("best_for", []),
        }

    def _serialize_rankings(
        self, candidates: list[BaseTool], rankings: list[object]
    ) -> list[dict[str, Any]]:
        tool_by_name = {tool.name: tool for tool in candidates}
        serialized: list[dict[str, Any]] = []
        for score in rankings:
            item = score.to_dict()
            tool = tool_by_name.get(score.tool_name)
            if tool:
                info = tool.get_info()
                item["agent_skills"] = info.get("agent_skills", [])
                item["usage_location"] = info.get("usage_location")
                item["best_for"] = info.get("best_for", [])
                item["supports"] = info.get("supports", {})
                item["status"] = str(tool.get_status())
            serialized.append(item)
        return serialized

    # ---- Custom-workflow (ComfyUI) support ----------------------------

    @staticmethod
    def _has_custom_workflow(inputs: dict[str, Any]) -> bool:
        return bool(inputs.get("workflow_json") or inputs.get("workflow_path"))

    def _custom_workflow_eligible(self, tool: BaseTool, inputs: dict[str, Any]) -> bool:
        """Whether a tool can run the caller-supplied custom workflow.

        Eligibility is based on server availability, not bundled-model
        readiness: a provider qualifies when it advertises ``custom_workflow``
        support, an ``output_node`` is supplied, and its backend is reachable
        (status is not UNAVAILABLE).
        """
        if not self._has_custom_workflow(inputs):
            return False
        if not inputs.get("output_node"):
            return False
        supports = getattr(tool, "supports", {})
        if not supports.get("custom_workflow"):
            return False
        return tool.get_status() != ToolStatus.UNAVAILABLE


class CustomWorkflowSelectorMixin:
    """Selectable-when-DEGRADED-but-workflow-capable behavior.

    video_selector and image_selector accept a DEGRADED provider when the
    caller supplies a custom ComfyUI workflow (bundled-model readiness is
    irrelevant then). tts_selector requires plain AVAILABLE — and verified
    2026-07-16: no capability="tts" tool advertises custom_workflow, so this
    is a real distinction to preserve rather than a no-op to unify.
    """

    def _tool_selectable(self, tool: BaseTool, inputs: dict[str, Any]) -> bool:
        if tool.get_status() == ToolStatus.AVAILABLE:
            return True
        return self._custom_workflow_eligible(tool, inputs)
