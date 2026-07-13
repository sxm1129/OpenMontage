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

describe("BrandsPage create with reference image", () => {
  const NEW_KIT_ID = "new-brand-abc123";

  function makeFetchMock() {
    return vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (method === "GET" && url === `${SERVER}/brands`) {
        return { ok: true, json: async () => ({ brand_kits: [] }) } as Response;
      }
      if (method === "POST" && url === `${SERVER}/brands`) {
        return {
          ok: true,
          json: async () => ({
            kit_id: NEW_KIT_ID,
            brand_name: "New Brand",
            slogan: "",
            industry: "",
            tone_keywords: [],
            color_palette: [],
            target_audience: "",
            logo_url: "",
            style_notes: "",
            reference_image_path: "",
            updated_at: 0,
          }),
        } as Response;
      }
      if (method === "POST" && url === `${SERVER}/brands/${NEW_KIT_ID}/reference-image`) {
        return {
          ok: true,
          json: async () => ({ reference_image_url: `/brand-media/${NEW_KIT_ID}/reference.png` }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    });
  }

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the reference-image file input in create mode (not just edit mode)", async () => {
    vi.stubGlobal("fetch", makeFetchMock());
    render(<BrandsPage />);

    const createButton = await screen.findByRole("button", { name: "+ 新建品牌 Kit" });
    fireEvent.click(createButton);

    expect(document.querySelector('input[type="file"]')).toBeTruthy();
  });

  it("uploads the selected reference image to the new kit's kit_id right after creating it", async () => {
    const fetchMock = makeFetchMock();
    vi.stubGlobal("fetch", fetchMock);
    render(<BrandsPage />);

    const createButton = await screen.findByRole("button", { name: "+ 新建品牌 Kit" });
    fireEvent.click(createButton);

    fireEvent.change(screen.getByPlaceholderText("小狗牌咖啡机"), { target: { value: "New Brand" } });

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [new File(["a"], "ref.png", { type: "image/png" })] } });

    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      const uploadCall = fetchMock.mock.calls.find(
        ([callUrl, callInit]) =>
          callUrl === `${SERVER}/brands/${NEW_KIT_ID}/reference-image` &&
          (callInit?.method ?? "GET") === "POST"
      );
      expect(uploadCall).toBeTruthy();
    });

    const createCall = fetchMock.mock.calls.find(
      ([callUrl, callInit]) => callUrl === `${SERVER}/brands` && (callInit?.method ?? "GET") === "POST"
    );
    expect(createCall).toBeTruthy();

    const uploadCall = fetchMock.mock.calls.find(
      ([callUrl]) => callUrl === `${SERVER}/brands/${NEW_KIT_ID}/reference-image`
    );
    expect(uploadCall?.[1]?.body).toBeInstanceOf(FormData);

    // Both calls happen before load()'s GET /brands re-fetch that follows a
    // successful create+upload, confirming the upload rides along with
    // creation rather than requiring the kit to be re-opened afterward.
    const createIndex = fetchMock.mock.calls.findIndex(
      ([callUrl, callInit]) => callUrl === `${SERVER}/brands` && (callInit?.method ?? "GET") === "POST"
    );
    const uploadIndex = fetchMock.mock.calls.findIndex(
      ([callUrl, callInit]) =>
        callUrl === `${SERVER}/brands/${NEW_KIT_ID}/reference-image` && (callInit?.method ?? "GET") === "POST"
    );
    expect(createIndex).toBeGreaterThanOrEqual(0);
    expect(uploadIndex).toBeGreaterThan(createIndex);
  });
});
