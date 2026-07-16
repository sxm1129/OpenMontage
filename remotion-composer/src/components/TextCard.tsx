import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { themeFont } from "../fonts";
import { useTheme } from "../lib/theme";

interface TextCardProps {
  text: string;
  fontSize?: number;
  color?: string;
  backgroundColor?: string;
}

export const TextCard: React.FC<TextCardProps> = ({
  text,
  fontSize = 64,
  color,
  backgroundColor,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Theme-driven type + motion (Wave 2, item 10): this card previously
  // hardcoded Inter and its own spring — themes changed the background but
  // never the most common text scene.
  const theme = useTheme();

  const opacity = spring({ frame, fps, config: { damping: 20 } });
  const scale = spring({
    frame,
    fps,
    config: theme.springConfig,
    from: 0.95,
    to: 1,
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: backgroundColor ?? theme.surfaceColor,
      }}
    >
      <div
        style={{
          opacity,
          transform: `scale(${scale})`,
          fontSize,
          color: color ?? theme.textColor,
          fontFamily: themeFont(theme.headingFont, "Inter, system-ui, sans-serif"),
          fontWeight: 700,
          textAlign: "center",
          maxWidth: "80%",
          lineHeight: 1.3,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
