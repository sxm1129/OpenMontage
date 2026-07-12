import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import JobDetailPage from "@/app/dashboard/jobs/[jobId]/page";

const SERVER = "http://localhost:8000";
const JOB_ID = "job123";

vi.mock("next/navigation", () => ({
  useParams: () => ({ jobId: JOB_ID }),
}));

// jsdom has no native EventSource — stand in a minimal, fully-controllable
// fake so tests can trigger onopen/onerror/onmessage deterministically.
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
}

function seqEvent(seq: number, partial: Record<string, unknown>) {
  return { seq, ts: 0, ...partial };
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);
  // jsdom doesn't implement scrollIntoView; the page calls it on every
  // events update, so stub it out rather than let it throw.
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("JobDetailPage SSE reconnect backoff", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === `${SERVER}/jobs/${JOB_ID}`) {
          return { ok: true, json: async () => ({}) } as Response;
        }
        return { ok: true, json: async () => ({}) } as Response;
      })
    );
  });

  it("doubles the reconnect delay on each consecutive failure, capped at 30s", async () => {
    render(<JobDetailPage />);

    expect(FakeEventSource.instances).toHaveLength(1);

    // 1st failure -> waits the base 2s before reconnecting.
    act(() => { FakeEventSource.instances[0].onerror?.(); });
    act(() => { vi.advanceTimersByTime(1999); });
    expect(FakeEventSource.instances).toHaveLength(1);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(2);

    // 2nd consecutive failure (no success in between) -> waits 4s.
    act(() => { FakeEventSource.instances[1].onerror?.(); });
    act(() => { vi.advanceTimersByTime(3999); });
    expect(FakeEventSource.instances).toHaveLength(2);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(3);

    // 3rd consecutive failure -> waits 8s.
    act(() => { FakeEventSource.instances[2].onerror?.(); });
    act(() => { vi.advanceTimersByTime(7999); });
    expect(FakeEventSource.instances).toHaveLength(3);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(4);

    // 4th consecutive failure -> waits 16s.
    act(() => { FakeEventSource.instances[3].onerror?.(); });
    act(() => { vi.advanceTimersByTime(15999); });
    expect(FakeEventSource.instances).toHaveLength(4);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(5);

    // 5th consecutive failure -> would be 32s uncapped, but caps at 30s.
    act(() => { FakeEventSource.instances[4].onerror?.(); });
    act(() => { vi.advanceTimersByTime(29999); });
    expect(FakeEventSource.instances).toHaveLength(5);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(6);

    // 6th consecutive failure -> stays capped at 30s, never grows further.
    act(() => { FakeEventSource.instances[5].onerror?.(); });
    act(() => { vi.advanceTimersByTime(29999); });
    expect(FakeEventSource.instances).toHaveLength(6);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(7);
  });

  it("resets the backoff to the base interval once a connection succeeds", async () => {
    render(<JobDetailPage />);

    // Grow the delay to 4s (one failure).
    act(() => { FakeEventSource.instances[0].onerror?.(); });
    act(() => { vi.advanceTimersByTime(2000); });
    expect(FakeEventSource.instances).toHaveLength(2);

    // This connection succeeds -> backoff resets to the 2s base.
    act(() => { FakeEventSource.instances[1].onopen?.(); });

    // Fails again — if the reset didn't happen this would need 4s; confirm
    // 2s (the base) is now sufficient.
    act(() => { FakeEventSource.instances[1].onerror?.(); });
    act(() => { vi.advanceTimersByTime(1999); });
    expect(FakeEventSource.instances).toHaveLength(2);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(3);
  });

  it("stops reconnecting once the stream ends on a genuine terminal event", async () => {
    render(<JobDetailPage />);

    act(() => {
      FakeEventSource.instances[0].onmessage?.({
        data: JSON.stringify(seqEvent(1, { type: "job_completed", render_url: "/media/x.mp4" })),
      } as MessageEvent);
    });
    act(() => { FakeEventSource.instances[0].onerror?.(); });
    act(() => { vi.advanceTimersByTime(60000); });

    // No reconnect attempt was scheduled — the stream ended on a terminal event.
    expect(FakeEventSource.instances).toHaveLength(1);
  });
});

describe("JobDetailPage inline artifact edit error handling", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (method === "GET" && url === `${SERVER}/jobs/${JOB_ID}`) {
          return { ok: true, json: async () => ({}) } as Response;
        }
        if (method === "POST" && url === `${SERVER}/jobs/${JOB_ID}/artifact`) {
          return {
            ok: false,
            status: 400,
            json: async () => ({ detail: "invalid stage: nope" }),
          } as Response;
        }
        return { ok: true, json: async () => ({}) } as Response;
      })
    );
  });

  async function openEditor() {
    render(<JobDetailPage />);

    act(() => {
      FakeEventSource.instances[0].onmessage?.({
        data: JSON.stringify(
          seqEvent(1, {
            type: "awaiting_approval",
            stage: "idea",
            preview: { title: "draft idea" },
          })
        ),
      } as MessageEvent);
    });

    const editButton = await screen.findByRole("button", { name: /直接编辑/ });
    fireEvent.click(editButton);
  }

  it("surfaces the backend's 400 detail instead of silently doing nothing", async () => {
    await openEditor();

    const saveButton = screen.getByRole("button", { name: "保存修改" });
    fireEvent.click(saveButton);

    // Regression: a non-200 save response must not be swallowed — the user
    // needs to see the save didn't take effect, and why (e.g. the backend
    // rejected the stage name against the job's real pipeline stages).
    const errorNode = await screen.findByText("invalid stage: nope");
    expect(errorNode).toBeInTheDocument();
    // Same red border/bg treatment as the approve/retry actionError card.
    expect(errorNode.className).toContain("text-red-400");
    expect(errorNode.className).toContain("border-red-500/40");
  });
});
