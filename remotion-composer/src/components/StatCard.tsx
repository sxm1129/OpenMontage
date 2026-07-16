import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { themeFont } from "../fonts";
import { useTheme } from "../lib/theme";

interface StatCardProps {
  stat: string;
  subtitle?: string;
  statFontSize?: number;
  subtitleFontSize?: number;
  color?: string;
  accentColor?: string;
  backgroundColor?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  stat,
  subtitle,
  statFontSize = 128,
  subtitleFontSize = 36,
  color,
  accentColor,
  backgroundColor,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Theme-driven defaults + motion (Wave 2, item 10) — explicit props win.
  const theme = useTheme();

  const scale = spring({
    frame,
    fps,
    config: theme.springConfig,
    from: 0.8,
    to: 1,
  });

  const subtitleOpacity = spring({
    frame: frame - 8,
    fps,
    config: { damping: 20 },
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: backgroundColor ?? theme.surfaceColor,
      }}
    >
      <div style={{ textAlign: "center" }}>
        <div
          style={{
            transform: `scale(${scale})`,
            fontSize: statFontSize,
            color: accentColor ?? theme.accentColor,
            fontFamily: themeFont(theme.headingFont, "Inter, system-ui, sans-serif"),
            fontWeight: 800,
            lineHeight: 1.1,
          }}
        >
          {stat}
        </div>
        {subtitle && (
          <div
            style={{
              opacity: subtitleOpacity,
              fontSize: subtitleFontSize,
              color: color ?? theme.textColor,
              fontFamily: themeFont(theme.bodyFont, "Inter, system-ui, sans-serif"),
              fontWeight: 400,
              marginTop: 16,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
