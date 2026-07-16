import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { themeFont } from "../fonts";
import { useTheme } from "../lib/theme";

interface HeroTitleProps {
  // Index signature required by Remotion's <Composition> prop typing —
  // same pattern as TalkingHeadProps.
  [key: string]: unknown;
  title: string;
  subtitle?: string;
}

/** Indices of the characters that carry the accent color: the first WORD
 *  (space-delimited), or the first two characters for space-less CJK
 *  titles. The old rule was `i < 8` — the first 8 CHARACTERS in hardcoded
 *  cyan regardless of word boundaries or theme (audit 2026-07-16, item 10). */
function accentCharCount(title: string): number {
  const firstSpace = title.indexOf(" ");
  if (firstSpace > 0) return firstSpace;
  // No spaces: CJK (or one-word Latin) — accent a short leading run.
  return Math.min(2, title.length);
}

export const HeroTitle: React.FC<HeroTitleProps> = ({ title, subtitle }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const theme = useTheme();

  const titleChars = title.split("");
  const accentCount = accentCharCount(title);
  const heroFont = themeFont(theme.headingFont, "Space Grotesk, Inter, system-ui, sans-serif");

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background:
          "radial-gradient(ellipse at center, rgba(15,23,42,0.35) 0%, rgba(15,23,42,0.55) 100%)",
      }}
    >
      <div style={{ textAlign: "center", maxWidth: "85%" }}>
        {/* Main title with per-character spring */}
        <div
          style={{
            fontSize: 72,
            fontWeight: 800,
            fontFamily: heroFont,
            lineHeight: 1.2,
            display: "flex",
            justifyContent: "center",
            flexWrap: "wrap",
            gap: 0,
          }}
        >
          {titleChars.map((char, i) => {
            const delay = i * 1.2;
            const charSpring = spring({
              frame: frame - delay,
              fps,
              config: { damping: 12, stiffness: 150 },
            });

            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  opacity: charSpring,
                  transform: `translateY(${interpolate(charSpring, [0, 1], [30, 0])}px)`,
                  color: i < accentCount ? theme.accentColor : "#F8FAFC",
                  whiteSpace: char === " " ? "pre" : undefined,
                  minWidth: char === " " ? "0.3em" : undefined,
                }}
              >
                {char}
              </span>
            );
          })}
        </div>

        {/* Subtitle */}
        {subtitle && (
          <div
            style={{
              marginTop: 20,
              opacity: spring({
                frame: frame - titleChars.length * 1.2 - 5,
                fps,
                config: { damping: 20 },
              }),
              fontSize: 28,
              fontWeight: 400,
              color: theme.mutedTextColor,
              fontFamily: heroFont,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
            }}
          >
            {subtitle}
          </div>
        )}

        {/* Animated underline — themed, sized to the title instead of a
            hardcoded 400px */}
        <div
          style={{
            margin: "24px auto 0",
            height: 3,
            backgroundColor: theme.accentColor,
            borderRadius: 2,
            width: interpolate(
              spring({
                frame: frame - 15,
                fps,
                config: { damping: 15, stiffness: 60 },
              }),
              [0, 1],
              [0, Math.min(640, Math.max(240, title.length * 26))]
            ),
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
