import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { withCjkFallback } from "../fonts";
import { useTheme } from "../lib/theme";

interface SectionTitleProps {
  title: string;
  subtitle?: string;
  accentColor?: string;
  position?: "top-left" | "bottom-left" | "center";
}

export const SectionTitle: React.FC<SectionTitleProps> = ({
  title,
  subtitle,
  accentColor,
  position = "top-left",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const theme = useTheme();
  // Themed accent default — explicit prop wins (Wave 2, item 10).
  const accent = accentColor ?? theme.accentColor;

  // Entrance spring
  const slideIn = spring({
    frame,
    fps,
    config: { damping: 15, stiffness: 80 },
  });

  // Exit fade
  const exitStart = durationInFrames - 15;
  const fadeOut = interpolate(frame, [exitStart, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const opacity = Math.min(slideIn, fadeOut);

  const positionStyles: React.CSSProperties =
    position === "center"
      ? { justifyContent: "center", alignItems: "center" }
      : position === "bottom-left"
      ? { justifyContent: "flex-end", alignItems: "flex-start", padding: 60 }
      : { justifyContent: "flex-start", alignItems: "flex-start", padding: 60 };

  return (
    <AbsoluteFill style={positionStyles}>
      <div
        style={{
          opacity,
          transform: `translateX(${interpolate(slideIn, [0, 1], [-40, 0])}px)`,
        }}
      >
        {/* Accent bar */}
        <div
          style={{
            width: interpolate(slideIn, [0, 1], [0, 60]),
            height: 4,
            backgroundColor: accent,
            marginBottom: 12,
            borderRadius: 2,
          }}
        />
        <div
          style={{
            fontSize: 28,
            fontWeight: 700,
            color: "#F8FAFC",
            fontFamily: withCjkFallback("Space Grotesk, Inter, system-ui, sans-serif"),
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            textShadow: "0 2px 8px rgba(0,0,0,0.6)",
          }}
        >
          {title}
        </div>
        {subtitle && (
          <div
            style={{
              fontSize: 18,
              fontWeight: 400,
              color: accent,
              fontFamily: withCjkFallback("Space Grotesk, Inter, system-ui, sans-serif"),
              marginTop: 4,
              opacity: spring({
                frame: frame - 8,
                fps,
                config: { damping: 20 },
              }),
              textShadow: "0 2px 8px rgba(0,0,0,0.6)",
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
