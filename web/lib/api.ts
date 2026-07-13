// Shared API plumbing for the dashboard pages. Before this existed, every
// page declared its own copy of the base-URL fallback and ~20 fetch sites
// hand-rolled the same error triad:
//   res.json().catch(() => ({}))  →  body.detail ?? `HTTP ${status}`
//   →  catch { "网络错误，请检查后端是否可访问" }
// This module is the single source for both. Deliberately minimal: no
// per-endpoint typed schemas, no retries, no caching — call sites that need
// bespoke control flow (Promise.allSettled batches, the wizard's submit flow)
// keep using raw fetch with the shared SERVER constant.

/** Base URL of the FastAPI backend (single source of the fallback). */
export const SERVER = process.env.NEXT_PUBLIC_SERVER_URL ?? "http://localhost:8000";

export type ApiResult =
  // Response payloads are intentionally untyped — per-endpoint schemas are
  // out of scope for this helper (see module comment).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  | { ok: true; data: any }
  | { ok: false; status: number; detail: string };

/**
 * fetch() against the backend with normalized error handling:
 * - OK response       → { ok: true, data } (body parsed as JSON; a non-JSON
 *                        body degrades to {} rather than throwing, matching
 *                        the `.catch(() => ({}))` idiom this replaces)
 * - non-OK response   → { ok: false, status, detail: body.detail ?? `HTTP ${status}` }
 * - network-level throw (backend unreachable) →
 *                       { ok: false, status: 0, detail: "网络错误，请检查后端是否可访问" }
 *
 * Never throws — call sites branch on `ok` instead of wrapping in try/catch.
 */
export async function apiRequest(path: string, init?: RequestInit): Promise<ApiResult> {
  let res: Response;
  try {
    res = await fetch(`${SERVER}${path}`, init);
  } catch {
    return { ok: false, status: 0, detail: "网络错误，请检查后端是否可访问" };
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    return { ok: false, status: res.status, detail: body.detail ?? `HTTP ${res.status}` };
  }
  return { ok: true, data: body };
}
