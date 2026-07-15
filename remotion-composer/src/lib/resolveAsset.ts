// THE single asset-path resolver for every composition. This used to exist as
// seven hand-copied variants (Explainer, CinematicRenderer, LyricOverlay,
// TitledVideo, CollageBurst, AnimeScene, ScreenshotScene) that drifted apart:
// five copies produced a malformed 4-slash file:////Users/… URI for POSIX
// absolute paths (Remotion's asset downloader rejects it), and ALL copies —
// including the one that fixed the 4-slash bug — stripped the third slash of
// a well-formed file:///Users/… URI (exactly what video_compose.py sends for
// cuts[].source), demoting the absolute path to a relative one that fell
// through to staticFile() and resolved against public/. Audit 2026-07-15,
// BUG-7. Do not re-inline this into a composition.

import { staticFile } from "remotion";

/**
 * Pure core, exported for reuse/testing: maps a cut/overlay `src` to what
 * Remotion's media components need.
 *
 * - http(s)/data URLs pass through untouched
 * - file:// URIs are normalized (the path keeps its own leading slash)
 * - absolute paths (POSIX `/x` or Windows `C:/x`) become file:// URIs —
 *   staticFile() only accepts paths relative to public/
 * - anything else is treated as a public/ relative path via `toStaticFile`
 */
export function resolveAssetWith(src: string, toStaticFile: (p: string) => string): string {
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) {
    return src;
  }
  // Strip ONLY the scheme+authority ("file://") — a well-formed
  // file:///Users/… URI keeps its third slash, which IS the path's leading
  // slash. The old per-copy regex (/^file:\/\/\/?/) ate it.
  const clean = src.replace(/^file:\/\//, "").replace(/\\/g, "/");
  if (clean.startsWith("/")) {
    // POSIX absolute path already carries its leading slash — "file://" +
    // "/Users/…" is the correct 3-slash URI. Prepending "file:///" here is
    // what produced the invalid 4-slash form.
    return `file://${clean}`;
  }
  if (/^[A-Za-z]:\//.test(clean)) {
    // Windows drive-letter path needs the extra slash: file:///C:/…
    return `file:///${clean}`;
  }
  return toStaticFile(clean);
}

export function resolveAsset(src: string): string {
  return resolveAssetWith(src, staticFile);
}
