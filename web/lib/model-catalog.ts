// Chinese display labels for the model IDs the backend's /system/capabilities
// endpoint returns as `model_catalog` (server/app/routers/system.py). The IDs
// themselves are fetched live so the wizard and the settings page can't drift
// out of sync with each other or with what tool_bridge.py actually enforces —
// they used to each hardcode an independent copy of the same list. Labels
// stay client-side since they're a pure display concern the backend doesn't
// need to know about.
export const MODEL_LABELS: Record<string, string> = {
  "leapfast/ltx-2.3": "LTX 2.3",
  "leapfast/wan2.2": "Wan2.2 (无音轨)",
  "volcengine/doubao-seedance-2.0": "Seedance 2.0",
  "leapfast/flux2": "Flux2",
  "gemini-3.1-flash-image-preview": "NanoBanana",
  "qwen3-tts-flash": "Qwen3 TTS",
  "leapfast/indextts": "IndexTTS",
};

export function modelLabel(id: string): string {
  return MODEL_LABELS[id] ?? id;
}

export type ModelCatalog = {
  video_models: string[];
  image_models: string[];
  tts_models: string[];
};

// Mirrors server/app/routers/system.py's MODEL_CATALOG — used only until the
// live fetch resolves (or if it fails), so the wizard isn't empty on first
// paint. Matches the pattern already used for pipeline availability
// (isPipelineAvailable in pipeline-picker.ts).
export const FALLBACK_MODEL_CATALOG: ModelCatalog = {
  video_models: ["leapfast/ltx-2.3", "leapfast/wan2.2", "volcengine/doubao-seedance-2.0"],
  image_models: ["leapfast/flux2", "gemini-3.1-flash-image-preview"],
  tts_models: ["qwen3-tts-flash", "leapfast/indextts"],
};
