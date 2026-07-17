"""Capability-level video selector that routes between generation and stock providers.

Provider discovery is automatic — any BaseTool with capability="video_generation"
is picked up from the registry.  Adding a new video provider requires only creating
the tool file in tools/video/; no changes to this selector are needed.
"""

from __future__ import annotations

import os

from tools.base_tool import BaseTool, ToolRuntime, ToolStability, ToolTier
from tools.selector_base import CustomWorkflowSelectorMixin, SelectorBase


class VideoSelector(CustomWorkflowSelectorMixin, SelectorBase):
    name = "video_selector"
    version = "0.3.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "selector"
    stability = ToolStability.BETA
    runtime = ToolRuntime.HYBRID
    agent_skills = ["ai-video-gen", "create-video", "ltx2"]

    capabilities = [
        "text_to_video", "image_to_video", "stock_video",
        "provider_selection", "search_video", "download_video",
    ]
    supports = {
        "user_preference_routing": True,
        "offline_fallback": True,
        "reference_image": True,
        "stock_fallback": True,
    }
    best_for = [
        "preflight routing",
        "user-facing recommendation flows",
        "switching between cloud, local, and stock video tools",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "preferred_provider": {
                "type": "string",
                "description": "Provider name or 'auto'. Valid values are discovered at runtime from the registry.",
                "default": "auto",
            },
            "allowed_providers": {"type": "array", "items": {"type": "string"}},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video", "rank"],
                "default": "text_to_video",
            },
            "target_operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video"],
                "description": "Operation to score when operation='rank'.",
                "default": "text_to_video",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1"],
                "default": "16:9",
                "description": "Video aspect ratio. Passed through to the selected provider.",
            },
            "duration": {
                "type": "string",
                "description": "Duration hint (e.g., '5', '10'). Passed through to the selected provider.",
            },
            "reference_image_path": {
                "type": "string",
                "description": "Local path to a reference image for image_to_video. Auto-uploaded if the provider requires a URL.",
            },
            "reference_image_url": {
                "type": "string",
                "description": "URL of a reference image for image_to_video.",
            },
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Reference image URLs for providers that support reference-conditioned video.",
            },
            "reference_image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local reference image paths for providers that support reference-conditioned video.",
            },
            "image_url": {
                "type": "string",
                "description": "Alias for reference_image_url (used by some providers like Kling via fal.ai).",
            },
            "resolution": {
                "type": "string",
                "description": "Resolution hint for providers that support named output resolutions.",
            },
            "workflow_json": {
                "type": "string",
                "description": (
                    "Optional full ComfyUI workflow JSON. Routes to a custom-workflow-capable "
                    "provider (e.g. comfyui_video) based on server availability, not bundled "
                    "model readiness. Requires output_node."
                ),
            },
            "workflow_path": {
                "type": "string",
                "description": (
                    "Optional path to a ComfyUI workflow JSON file. Routes to a custom-workflow-"
                    "capable provider based on server availability. Requires output_node."
                ),
            },
            "output_node": {
                "type": "string",
                "description": "ComfyUI output node ID for a custom workflow_json/workflow_path.",
            },
            "workflow_name": {
                "type": "string",
                "description": "Optional human-readable provenance label for a custom workflow.",
            },
            "workflow_model": {
                "type": "string",
                "description": "Optional model/provenance label for a custom workflow.",
            },
            "workflow_model_stack": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Optional provenance metadata for custom workflow dependencies.",
            },
            "output_path": {"type": "string"},
        },
    }

    # ── Discovery, scoring, rank mode and result decoration live in
    # SelectorBase. video customizes the env-hint preference mapping, rank
    # inputs, operation-readiness filtering and the reference-image upload —
    # and never overrides execute() (see the base's docstring on double
    # instrumentation).
    _prompt_key = "prompt"
    _default_operation = "text_to_video"

    @property
    def fallback_tools(self) -> list[str]:
        """Discovered providers, plus image_selector as a cross-capability
        last resort (a still + Ken Burns beats no visual at all)."""
        return super().fallback_tools + ["image_selector"]

    def _no_provider_error(self) -> str:
        return "No video generation provider available."

    def _resolve_preferred(self, inputs: dict[str, object]) -> str:
        preferred = str(inputs.get("preferred_provider", "auto"))
        env_hint = os.environ.get("VIDEO_GEN_LOCAL_MODEL", "").lower()
        env_map = {
            "wan2.1-1.3b": "wan",
            "wan2.1-14b": "wan",
            "hunyuan-1.5": "hunyuan",
            "ltx2-local": "ltx",
            "cogvideo-5b": "cogvideo",
            "cogvideo-2b": "cogvideo",
        }
        if preferred == "auto" and env_hint in env_map:
            return env_map[env_hint]
        return preferred

    def _rank_inputs(self, inputs: dict[str, object]) -> dict[str, object]:
        rank_inputs = dict(inputs)
        rank_inputs["operation"] = inputs.get("target_operation", "text_to_video")
        return rank_inputs

    def _adapt_inputs(self, inputs: dict[str, object], tool: BaseTool) -> dict[str, object]:
        """Add `query` for stock providers and resolve a local reference image
        to a URL for providers that take one.

        Note this still forwards preferred_provider/allowed_providers to the
        provider (unlike image_selector, which strips them) — preserved
        deliberately; see SelectorBase._adapt_inputs.
        """
        adapted = dict(inputs)
        if hasattr(tool, "input_schema"):
            props = tool.input_schema.get("properties", {})
            if "query" in props and "query" not in adapted:
                adapted["query"] = adapted.get("prompt", "")

        if adapted.get("operation") == "image_to_video" and adapted.get("reference_image_path"):
            tool_props = getattr(tool, "input_schema", {}).get("properties", {})
            if "image_url" in tool_props and "image_url" not in adapted:
                from tools.video._shared import upload_image_fal
                adapted["image_url"] = upload_image_fal(adapted["reference_image_path"])
        return adapted

    def _filter_candidates(
        self,
        inputs: dict[str, object],
        candidates: list[BaseTool],
    ) -> list[BaseTool]:
        # A caller-supplied custom workflow is provider-specific (ComfyUI graph
        # JSON). Route it only to custom-workflow-capable providers whose server
        # is reachable — bundled-model readiness is irrelevant in that case.
        if self._has_custom_workflow(inputs):
            return [t for t in candidates if self._custom_workflow_eligible(t, inputs)]

        operation = inputs.get("operation", "text_to_video")
        if operation == "rank":
            operation = inputs.get("target_operation", "text_to_video")

        filtered: list[BaseTool] = []
        matched_operation = False
        for tool in candidates:
            supports = getattr(tool, "supports", {})
            props = getattr(tool, "input_schema", {}).get("properties", {})

            if operation == "image_to_video":
                if supports.get("image_to_video") or "image_url" in props or "reference_image_url" in props:
                    matched_operation = True
                    if self._operation_ready(tool, "image_to_video"):
                        filtered.append(tool)
                continue

            if operation == "reference_to_video":
                if supports.get("reference_to_video") or "reference_image_urls" in props:
                    matched_operation = True
                    filtered.append(tool)
                continue

            matched_operation = True
            if self._operation_ready(tool, str(operation)):
                filtered.append(tool)

        return filtered if matched_operation else candidates

    @staticmethod
    def _operation_ready(tool: BaseTool, operation: str) -> bool:
        checker = getattr(tool, "is_operation_available", None)
        if not callable(checker):
            return True
        return bool(checker(operation))
