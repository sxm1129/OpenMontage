import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge, EventRow, eventLabel, stageLabel, type SseEvent } from "@/components/job-status";

function ev(partial: Partial<SseEvent>): SseEvent {
  return { seq: 0, type: "stage_started", ts: 0, ...partial };
}

describe("StatusBadge", () => {
  it("renders the Chinese label for each known status", () => {
    const cases: [string, string][] = [
      ["queued", "排队中"],
      ["running", "生成中"],
      ["awaiting_approval", "待审批"],
      ["completed", "已完成"],
      ["failed", "失败"],
    ];
    for (const [status, label] of cases) {
      const { unmount } = render(<StatusBadge status={status} />);
      expect(screen.getByTestId("status-badge")).toHaveTextContent(label);
      unmount();
    }
  });

  it("falls back to the queued style for an unknown status", () => {
    render(<StatusBadge status="who_knows" />);
    expect(screen.getByTestId("status-badge")).toHaveTextContent("排队中");
  });

  it("applies the status-specific colour class", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByTestId("status-badge").className).toContain("text-red-400");
  });
});

describe("eventLabel precedence", () => {
  it("prefers summary over everything else", () => {
    expect(eventLabel(ev({ summary: "S", text: "T", artifact: "A", message: "M" }))).toBe("S");
  });
  it("falls through summary → text → artifact → message → type", () => {
    expect(eventLabel(ev({ text: "T", artifact: "A", message: "M" }))).toBe("T");
    expect(eventLabel(ev({ artifact: "A", message: "M" }))).toBe("A");
    expect(eventLabel(ev({ message: "M" }))).toBe("M");
    expect(eventLabel(ev({ type: "job_failed" }))).toBe("job_failed");
  });
});

describe("stageLabel", () => {
  it("maps every stage name used across all pipeline_defs manifests", () => {
    // The union of top-level stage names across all 13 engine pipelines, plus
    // the synthetic "budget" gate — see server/app/pipeline_catalog.py.
    const known = [
      "research", "proposal", "idea", "script", "scene_plan",
      "character_design", "rig_plan", "assets", "edit", "compose",
      "publish", "budget",
    ];
    for (const s of known) {
      const label = stageLabel(s);
      expect(label).not.toBe("");
      expect(label).not.toBe("undefined");
    }
  });

  it("falls back to the raw name for an unmapped stage — never the literal 'undefined'", () => {
    // Regression: STAGE_LABELS[awaitingStage] with no fallback used to render
    // the JS string "undefined" for any pipeline stage outside the hardcoded map.
    expect(stageLabel("some_future_stage")).toBe("some_future_stage");
  });

  it("returns an empty string for null/undefined input", () => {
    expect(stageLabel(null)).toBe("");
    expect(stageLabel(undefined)).toBe("");
  });
});

describe("EventRow", () => {
  it("shows the [stage] tag and the chosen label", () => {
    render(<EventRow ev={ev({ stage: "research", summary: "调研完成" })} />);
    expect(screen.getByText("[research]")).toBeInTheDocument();
    expect(screen.getByText("调研完成")).toBeInTheDocument();
  });

  it("falls back to type for the tag when no stage is present", () => {
    render(<EventRow ev={ev({ type: "job_completed", stage: undefined, message: "done" })} />);
    expect(screen.getByText("[job_completed]")).toBeInTheDocument();
  });
});
