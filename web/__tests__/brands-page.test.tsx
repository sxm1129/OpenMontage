import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import BrandsPage from "@/app/dashboard/brands/page";

const SERVER = "http://localhost:8000";

const KIT = {
  kit_id: "kit-1",
  brand_name: "Test Brand",
  slogan: "",
  industry: "",
  tone_keywords: [],
  color_palette: [],
  target_audience: "",
  logo_url: "",
  style_notes: "",
  reference_image_path: "reference.png",
  updated_at: 0,
};

describe("BrandsPage reference image re-upload", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (method === "GET" && url === `${SERVER}/brands`) {
          return { ok: true, json: async () => ({ brand_kits: [KIT] }) } as Response;
        }
        // The backend always writes a re-uploaded reference image to the
        // same fixed relative path — the response URL is identical every
        // time, regardless of how many times this is called.
        if (method === "POST" && url === `${SERVER}/brands/${KIT.kit_id}/reference-image`) {
          return {
            ok: true,
            json: async () => ({ reference_image_url: `/brand-media/${KIT.kit_id}/reference.png` }),
          } as Response;
        }
        return { ok: true, json: async () => ({}) } as Response;
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("changes the preview <img> src on every successful re-upload, even though the backend URL never changes", async () => {
    render(<BrandsPage />);

    const editButton = await screen.findByRole("button", { name: "编辑" });
    fireEvent.click(editButton);

    const initialSrc = (await screen.findByAltText("参考图预览") as HTMLImageElement).src;

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const uploadButton = screen.getByRole("button", { name: "上传参考图" });

    fireEvent.change(fileInput, { target: { files: [new File(["a"], "a.png", { type: "image/png" })] } });
    fireEvent.click(uploadButton);

    await waitFor(() => {
      expect((screen.getByAltText("参考图预览") as HTMLImageElement).src).not.toBe(initialSrc);
    });
    const srcAfterFirstUpload = (screen.getByAltText("参考图预览") as HTMLImageElement).src;

    // Re-upload a second time — the mocked backend returns the exact same
    // reference_image_url both times, so only client-side cache-busting can
    // make the <img> pick up the new file.
    fireEvent.change(fileInput, { target: { files: [new File(["b"], "b.png", { type: "image/png" })] } });
    fireEvent.click(screen.getByRole("button", { name: "上传参考图" }));

    await waitFor(() => {
      expect((screen.getByAltText("参考图预览") as HTMLImageElement).src).not.toBe(srcAfterFirstUpload);
    });
  });
});
