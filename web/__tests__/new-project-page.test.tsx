import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import NewProjectPage from "@/app/dashboard/new/page";

const SERVER = "http://localhost:8000";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe("NewProjectPage handleSubmit network failure", () => {
  let alertSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (method === "GET" && url === `${SERVER}/brands`) {
          return { ok: true, json: async () => ({ brand_kits: [] }) } as Response;
        }
        if (method === "GET" && url === `${SERVER}/pipelines`) {
          return { ok: true, json: async () => ({ pipelines: [] }) } as Response;
        }
        if (method === "POST" && url === `${SERVER}/jobs`) {
          // Simulates a network failure / unreachable backend — the fetch
          // promise itself rejects, rather than resolving with a non-ok
          // response.
          return Promise.reject(new Error("network down"));
        }
        return { ok: true, json: async () => ({}) } as Response;
      })
    );
  });

  afterEach(() => {
    alertSpy.mockRestore();
    vi.unstubAllGlobals();
  });

  it("surfaces an error and resets the loading flag instead of getting stuck on '提交中…'", async () => {
    render(<NewProjectPage />);

    const marketingCard = await screen.findByText("营销宣传片");
    fireEvent.click(marketingCard);

    const brandNameInput = await screen.findByPlaceholderText("例：小狗牌咖啡机");
    fireEvent.change(brandNameInput, { target: { value: "我的品牌" } });

    const submitButton = screen.getByRole("button", { name: /开始 AI 生产/ });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalled();
    });

    // Regression: without a try/catch around the rejected fetch, `loading`
    // was never reset and the button stayed stuck on "提交中…" forever.
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /开始 AI 生产/ })).toBeEnabled();
    });
  });
});
