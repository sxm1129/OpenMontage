import {
  AbsoluteFill,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { withCjkFallback } from "../fonts";
import { EASE_OUT } from "../lib/motion";

// Word-level caption for TikTok-style highlight display
export interface WordCaption {
  word: string;
  startMs: number;
  endMs: number;
}

/** Visual treatments (Wave 2, item 9 — modeled on the style enums shipped by
 *  JSON2Video/CapCut caption presets):
 *  - "pill":        whole page in one rounded box (the previous look)
 *  - "boxed-word":  every word carries its own box; the ACTIVE word's box
 *                   flips to the highlight color with dark text
 *  - "clean":       no background — heavy stroke/shadow carries legibility
 */
export type CaptionStyle = "pill" | "boxed-word" | "clean";

/** Keeps captions out of platform UI. "douyin"/"tiktok": the bottom ~25% is
 *  the description/music zone and the right ~13% is the action rail — the
 *  caption block anchors above the bottom zone and narrows clear of the
 *  rail. Values from published creator safe-zone guides (1080×1920 basis:
 *  bottom 484px, right 140px), applied proportionally. */
export type CaptionSafeArea = "douyin" | "tiktok" | "none";

interface CaptionOverlayProps {
  // Index signature required by Remotion's <Composition> prop typing —
  // same pattern as TalkingHeadProps.
  [key: string]: unknown;
  words: WordCaption[];
  // How many words to show at once in a "page"
  wordsPerPage?: number;
  fontSize?: number;
  color?: string;
  highlightColor?: string;
  backgroundColor?: string;
  fontFamily?: string;
  captionStyle?: CaptionStyle;
  safeArea?: CaptionSafeArea;
  /** Max per-line width in "cells" (CJK chars count 2, Latin 1). Default 32
   *  ≈ 16 CJK chars — the Netflix Simplified-Chinese line limit. Pagination
   *  breaks a page when adding a word would exceed this. */
  maxLineCells?: number;
}

interface CaptionPage {
  words: WordCaption[];
  startMs: number;
  endMs: number;
}

/** Width cost of a word in "cells": CJK chars are double-width. */
function wordCells(word: string): number {
  let cells = 0;
  for (const ch of word) {
    cells += /[　-鿿豈-﫿＀-￯぀-ヿ가-힯]/.test(ch) ? 2 : 1;
  }
  return cells + 1; // trailing space / inter-word gap
}

function buildPages(
  words: WordCaption[],
  wordsPerPage: number,
  maxLineCells: number,
): CaptionPage[] {
  // Break a page at whichever limit hits first: word count (Latin pacing)
  // or line cells (CJK — whisper emits per-character "words", so six of
  // them is two hanzi short of a line while six English words overflow it).
  const pages: CaptionPage[] = [];
  let current: WordCaption[] = [];
  let cells = 0;
  const flush = () => {
    if (current.length > 0) {
      pages.push({
        words: current,
        startMs: current[0].startMs,
        endMs: current[current.length - 1].endMs,
      });
      current = [];
      cells = 0;
    }
  };
  for (const w of words) {
    const c = wordCells(w.word);
    if (current.length > 0 && (current.length >= wordsPerPage || cells + c > maxLineCells)) {
      flush();
    }
    current.push(w);
    cells += c;
  }
  flush();
  return pages;
}

const PageRenderer: React.FC<{
  page: CaptionPage;
  fontSize: number;
  color: string;
  highlightColor: string;
  backgroundColor: string;
  fontFamily: string;
  captionStyle: CaptionStyle;
  paddingBottomPx: number;
  maxWidthPct: number;
}> = ({
  page,
  fontSize,
  color,
  highlightColor,
  backgroundColor,
  fontFamily,
  captionStyle,
  paddingBottomPx,
  maxWidthPct,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const currentMs = page.startMs + (frame / fps) * 1000;

  // Spring entrance
  const entrance = spring({
    frame,
    fps,
    config: { damping: 18, stiffness: 120 },
  });

  const renderWord = (w: WordCaption, i: number) => {
    const isActive = w.startMs <= currentMs && w.endMs > currentMs;
    const isPast = w.endMs <= currentMs;
    // Micro-pop on the active word: 1.0 → 1.08 over its first ~120 ms.
    // Product caption systems (CapCut/Submagic) all do this — it's what
    // makes the highlight read as RHYTHM rather than a color change.
    const pop = isActive
      ? interpolate(currentMs, [w.startMs, w.startMs + 120], [0, 1], {
          easing: EASE_OUT,
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 0;
    const scale = 1 + 0.08 * pop;

    if (captionStyle === "boxed-word") {
      return (
        <span
          key={`${w.startMs}-${i}`}
          style={{
            display: "inline-block",
            transform: `scale(${scale})`,
            backgroundColor: isActive ? highlightColor : backgroundColor,
            color: isActive ? "#0F172A" : isPast ? color : `${color}B3`,
            borderRadius: 8,
            padding: "2px 10px",
            margin: "3px 4px",
          }}
        >
          {w.word}
        </span>
      );
    }
    return (
      <span
        key={`${w.startMs}-${i}`}
        style={{
          display: "inline-block",
          transform: `scale(${scale})`,
          color: isActive ? highlightColor : isPast ? color : `${color}99`,
          textShadow: isActive
            ? `0 0 20px ${highlightColor}66, 0 2px 4px rgba(0,0,0,0.5)`
            : "0 2px 4px rgba(0,0,0,0.5)",
        }}
      >
        {w.word}
        {i < page.words.length - 1 ? " " : ""}
      </span>
    );
  };

  const blockStyle: React.CSSProperties =
    captionStyle === "pill"
      ? {
          backgroundColor,
          borderRadius: 12,
          padding: "14px 28px",
        }
      : captionStyle === "clean"
        ? {
            WebkitTextStroke: "1.5px rgba(0,0,0,0.85)",
            filter: "drop-shadow(0 2px 6px rgba(0,0,0,0.7))",
          }
        : {};

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: paddingBottomPx,
      }}
    >
      <div
        style={{
          opacity: entrance,
          transform: `translateY(${interpolate(entrance, [0, 1], [20, 0])}px)`,
          maxWidth: `${maxWidthPct}%`,
          textAlign: "center",
          ...blockStyle,
        }}
      >
        <span
          style={{
            fontSize,
            fontWeight: 700,
            fontFamily,
            lineHeight: 1.4,
            whiteSpace: "pre-wrap",
          }}
        >
          {page.words.map(renderWord)}
        </span>
      </div>
    </AbsoluteFill>
  );
};

export const CaptionOverlay: React.FC<CaptionOverlayProps> = ({
  words,
  wordsPerPage = 6,
  fontSize = 42,
  color = "#F8FAFC",
  highlightColor = "#22D3EE",
  backgroundColor = "rgba(15, 23, 42, 0.75)",
  fontFamily = withCjkFallback("Space Grotesk, Inter, system-ui, sans-serif"),
  captionStyle = "pill",
  safeArea = "none",
  maxLineCells = 32,
}) => {
  const { fps, height } = useVideoConfig();
  const pages = buildPages(words, wordsPerPage, maxLineCells);

  // Safe-area anchoring: 484/1920 ≈ 25.2% bottom exclusion on Douyin/TikTok
  // → anchor the caption block at 27% so it clears the description zone
  // with breathing room; the right action rail (140/1080 ≈ 13%) is cleared
  // by narrowing the block. 16:9 desktop keeps the classic 80px inset.
  const platformSafe = safeArea === "douyin" || safeArea === "tiktok";
  const paddingBottomPx = platformSafe ? Math.round(height * 0.27) : 80;
  const maxWidthPct = platformSafe ? 72 : 80;

  return (
    <AbsoluteFill>
      {pages.map((page, i) => {
        const fromFrame = Math.round((page.startMs / 1000) * fps);
        const nextStart = pages[i + 1]?.startMs ?? page.endMs + 500;
        const duration = Math.max(
          1,
          Math.round(((nextStart - page.startMs) / 1000) * fps)
        );

        return (
          <Sequence key={i} from={fromFrame} durationInFrames={duration}>
            <PageRenderer
              page={page}
              fontSize={fontSize}
              color={color}
              highlightColor={highlightColor}
              backgroundColor={backgroundColor}
              fontFamily={fontFamily}
              captionStyle={captionStyle}
              paddingBottomPx={paddingBottomPx}
              maxWidthPct={maxWidthPct}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
