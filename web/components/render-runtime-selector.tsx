"use client";

// Proposal-gate render_runtime / composition_mode picker.
//
// AGENT_GUIDE.md's "Present Both Composition Runtimes" is a HARD RULE: when
// Remotion and HyperFrames are both available, the agent must present both
// and wait for explicit approval before locking render_runtime — silently
// picking a default is forbidden. There was previously no web-UI surface for
// this decision at all (`grep -rin "render_runtime" web/` returned zero
// hits) — confirmed live across multiple real, paid end-to-end runs: the
// proposal artifact routinely reached the approval gate with
// render_runtime="PENDING_USER_APPROVAL" (a value the schema's closed enum
// explicitly forbids), and the only way to unblock the pipeline was to
// hand-edit the artifact JSON on disk before retrying. This component closes
// that gap: it renders every runtime's availability and tradeoff, blocks
// approval until a real choice is made, and the approval-panel PATCHes the
// selection into production_plan before calling /approve.

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export type RuntimeKey = "remotion" | "hyperframes" | "ffmpeg";
export type ModeKey = "templated" | "atelier";

const RUNTIME_INFO: Record<RuntimeKey, { label: string; bestFor: string; tradeoff: string }> = {
  remotion: {
    label: "Remotion",
    bestFor: "React 组件化渲染：图文卡片、图表、弹性动画、字级字幕烧录。",
    tradeoff: "渲染较慢，依赖 Node.js + remotion-composer/node_modules；适合数据驱动/解说类内容。",
  },
  hyperframes: {
    label: "HyperFrames",
    bestFor: "HTML/CSS/GSAP 合成：动态排版、产品发布、网页转视频、注册表驱动场景。",
    tradeoff: "适合设计感强的短片；依赖 Node ≥22 + npx，首次渲染前建议跑一次环境自检。",
  },
  ffmpeg: {
    label: "FFmpeg",
    bestFor: "始终可用的兜底方案：直接拼接、裁剪、Ken Burns 平移缩放。",
    tradeoff: "没有真正的组件动画，纯静态图/视频拼接，视觉表现力最弱。",
  },
};

const MODE_INFO: Record<ModeKey, { label: string; desc: string }> = {
  templated: {
    label: "模板化 Templated",
    desc: "复用现成场景类型（文字卡/图表/对比卡），快速可靠，适合批量产出、低风险内容。",
  },
  atelier: {
    label: "手工定制 Atelier",
    desc: "从零手写专属合成，视觉不与任何其他作品重复，适合品牌发布类重点作品；成本与迭代更高。",
  },
};

function isRuntimeKey(v: string | null | undefined): v is RuntimeKey {
  return v === "remotion" || v === "hyperframes" || v === "ffmpeg";
}
function isModeKey(v: string | null | undefined): v is ModeKey {
  return v === "templated" || v === "atelier";
}

export function RenderRuntimeSelector({
  currentRuntime,
  currentMode,
  onChange,
}: {
  currentRuntime: string | null | undefined;
  currentMode: string | null | undefined;
  /** Fires on every pick with the FULL current selection (both fields —
   * not just the one that changed), so the parent can always merge a
   * complete, valid pair into production_plan before approving. */
  onChange: (runtime: RuntimeKey | null, mode: ModeKey | null) => void;
}) {
  // null (not yet fetched) means "assume available" — a picker that fails
  // open to "everything enabled" is safer than one that fails closed and
  // silently blocks the only actually-installed runtime because the
  // capabilities call hasn't resolved yet.
  const [engines, setEngines] = useState<Record<string, boolean> | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiRequest("/system/capabilities").then((r) => {
      if (!cancelled && r.ok && r.data?.composition_runtimes?.engines) {
        setEngines(r.data.composition_runtimes.engines);
      }
    });
    return () => { cancelled = true; };
  }, []);

  const initialRuntime = isRuntimeKey(currentRuntime) ? currentRuntime : null;
  const initialMode = isModeKey(currentMode) ? currentMode : null;
  const [runtime, setRuntime] = useState<RuntimeKey | null>(initialRuntime);
  const [mode, setMode] = useState<ModeKey | null>(initialMode);

  function pickRuntime(r: RuntimeKey) {
    setRuntime(r);
    onChange(r, mode);
  }
  function pickMode(m: ModeKey) {
    setMode(m);
    onChange(runtime, m);
  }

  const needsRuntimeChoice = !isRuntimeKey(currentRuntime);

  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-3" data-testid="render-runtime-selector">
      <div>
        <p className="text-sm font-medium">合成引擎 render_runtime</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          决定成片的渲染方式，锁定后不能静默更改。
          {needsRuntimeChoice && (
            <span className="text-yellow-400"> AI 未能确定，需要你明确选择才能批准。</span>
          )}
        </p>
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
        {(Object.keys(RUNTIME_INFO) as RuntimeKey[]).map((key) => {
          const info = RUNTIME_INFO[key];
          const available = engines ? engines[key] !== false : true;
          const selected = runtime === key;
          return (
            <button
              key={key}
              type="button"
              disabled={!available}
              aria-pressed={selected}
              onClick={() => pickRuntime(key)}
              className={`text-left rounded-md border p-2.5 transition-colors ${
                selected ? "border-primary bg-primary/10" : "border-border hover:border-primary/50"
              } ${!available ? "opacity-40 cursor-not-allowed" : ""}`}
            >
              <div className="flex items-center justify-between gap-1">
                <span className="text-sm font-medium">{info.label}</span>
                {selected && <span className="text-[10px] text-primary shrink-0">已选</span>}
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">{info.bestFor}</p>
              <p className="text-[11px] text-muted-foreground/70 mt-1">⚠ {info.tradeoff}</p>
              {engines && !available && (
                <p className="text-[10px] text-red-400 mt-1">此机器未安装 / 不可用</p>
              )}
            </button>
          );
        })}
      </div>

      <div>
        <p className="text-sm font-medium">创作模式 composition_mode</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          与引擎正交：模板化复用现成场景，手工定制从零编写专属视觉语言。
        </p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {(Object.keys(MODE_INFO) as ModeKey[]).map((key) => {
          const info = MODE_INFO[key];
          const selected = mode === key;
          return (
            <button
              key={key}
              type="button"
              aria-pressed={selected}
              onClick={() => pickMode(key)}
              className={`text-left rounded-md border p-2.5 transition-colors ${
                selected ? "border-primary bg-primary/10" : "border-border hover:border-primary/50"
              }`}
            >
              <div className="flex items-center justify-between gap-1">
                <span className="text-sm font-medium">{info.label}</span>
                {selected && <span className="text-[10px] text-primary shrink-0">已选</span>}
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">{info.desc}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
