// Proposal-gate render_runtime/composition_mode picker (see
// render-runtime-selector.tsx). Confirmed live across real end-to-end runs:
// render_runtime routinely reached this gate as the forbidden placeholder
// "PENDING_USER_APPROVAL" with no web-UI way to resolve it. These tests pin
// the three behaviors that close that gap: the picker blocks approval until
// a real choice is made, an unavailable engine can't be selected, and the
// selection is PATCHed into production_plan before /approve is called.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ApprovalPanel } from "@/components/approval-panel";

const JOB_ID = "job-proposal";

function proposalPreview(renderRuntime: string, compositionMode?: string) {
  return {
    concept_options: [{ id: "c1" }],
    selected_concept: { id: "c1" },
    production_plan: {
      pipeline: "cinematic",
      render_runtime: renderRuntime,
      ...(compositionMode ? { composition_mode: compositionMode } : {}),
    },
    cost_estimate: {},
  };
}

function mockFetch(engines: Record<string, boolean>) {
  const calls: { url: string; body?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(init.body as string) : undefined;
      calls.push({ url: String(url), body });
      if (String(url).includes("/system/capabilities")) {
        return {
          ok: true,
          json: async () => ({ composition_runtimes: { engines } }),
        } as Response;
      }
      if (String(url).includes("/artifact")) {
        return { ok: true, json: async () => ({ ok: true }) } as Response;
      }
      if (String(url).includes("/approve")) {
        return { ok: true, json: async () => ({ ok: true }) } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    })
  );
  return calls;
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("proposal gate render_runtime picker", () => {
  it("renders all three runtimes and both composition modes", async () => {
    mockFetch({ ffmpeg: true, remotion: true, hyperframes: true });
    render(
      <ApprovalPanel
        jobId={JOB_ID}
        stage="proposal"
        gate={null}
        preview={proposalPreview("PENDING_USER_APPROVAL")}
        previewArtifact="proposal_packet"
        onError={() => {}}
        onApproved={() => {}}
      />
    );
    await screen.findByTestId("render-runtime-selector");
    expect(screen.getByText("Remotion")).toBeTruthy();
    expect(screen.getByText("HyperFrames")).toBeTruthy();
    expect(screen.getByText("FFmpeg")).toBeTruthy();
    expect(screen.getByText("模板化 Templated")).toBeTruthy();
    expect(screen.getByText("手工定制 Atelier")).toBeTruthy();
  });

  it("blocks approval when render_runtime is the forbidden placeholder and nothing was picked", async () => {
    mockFetch({ ffmpeg: true, remotion: true, hyperframes: true });
    render(
      <ApprovalPanel
        jobId={JOB_ID}
        stage="proposal"
        gate={null}
        preview={proposalPreview("PENDING_USER_APPROVAL")}
        previewArtifact="proposal_packet"
        onError={() => {}}
        onApproved={() => {}}
      />
    );
    const approveBtn = screen.getByText("✓ 批准，继续生产").closest("button") as HTMLButtonElement;
    expect(approveBtn.disabled).toBe(true);
    expect(screen.getByText(/请先在上方选择合成引擎/)).toBeTruthy();
  });

  it("does not block approval when the proposal already has a valid render_runtime", async () => {
    mockFetch({ ffmpeg: true, remotion: true, hyperframes: true });
    render(
      <ApprovalPanel
        jobId={JOB_ID}
        stage="proposal"
        gate={null}
        preview={proposalPreview("remotion", "atelier")}
        previewArtifact="proposal_packet"
        onError={() => {}}
        onApproved={() => {}}
      />
    );
    const approveBtn = screen.getByText("✓ 批准，继续生产").closest("button") as HTMLButtonElement;
    expect(approveBtn.disabled).toBe(false);
  });

  it("disables a runtime card the machine doesn't have installed", async () => {
    mockFetch({ ffmpeg: true, remotion: false, hyperframes: false });
    render(
      <ApprovalPanel
        jobId={JOB_ID}
        stage="proposal"
        gate={null}
        preview={proposalPreview("PENDING_USER_APPROVAL")}
        previewArtifact="proposal_packet"
        onError={() => {}}
        onApproved={() => {}}
      />
    );
    await screen.findByTestId("render-runtime-selector");
    const remotionCard = screen.getByText("Remotion").closest("button") as HTMLButtonElement;
    await waitFor(() => expect(remotionCard.disabled).toBe(true));
    const ffmpegCard = screen.getByText("FFmpeg").closest("button") as HTMLButtonElement;
    expect(ffmpegCard.disabled).toBe(false);
  });

  it("picking a runtime enables approve, and approving PATCHes it into production_plan before /approve", async () => {
    const calls = mockFetch({ ffmpeg: true, remotion: true, hyperframes: true });
    const onApproved = vi.fn();
    render(
      <ApprovalPanel
        jobId={JOB_ID}
        stage="proposal"
        gate={null}
        preview={proposalPreview("PENDING_USER_APPROVAL")}
        previewArtifact="proposal_packet"
        onError={() => {}}
        onApproved={onApproved}
      />
    );
    await screen.findByTestId("render-runtime-selector");
    fireEvent.click(screen.getByText("HyperFrames").closest("button") as HTMLButtonElement);
    fireEvent.click(screen.getByText("手工定制 Atelier").closest("button") as HTMLButtonElement);

    const approveBtn = screen.getByText("✓ 批准，继续生产").closest("button") as HTMLButtonElement;
    expect(approveBtn.disabled).toBe(false);
    fireEvent.click(approveBtn);

    await waitFor(() => expect(onApproved).toHaveBeenCalled());

    const artifactCall = calls.find((c) => c.url.includes("/artifact"));
    expect(artifactCall).toBeTruthy();
    const patchedPlan = (artifactCall!.body as { content: { production_plan: Record<string, unknown> } })
      .content.production_plan;
    expect(patchedPlan.render_runtime).toBe("hyperframes");
    expect(patchedPlan.composition_mode).toBe("atelier");

    // The artifact PATCH must happen before /approve, not after.
    const artifactIdx = calls.findIndex((c) => c.url.includes("/artifact"));
    const approveIdx = calls.findIndex((c) => c.url.includes("/approve"));
    expect(artifactIdx).toBeGreaterThanOrEqual(0);
    expect(approveIdx).toBeGreaterThan(artifactIdx);
  });
});
