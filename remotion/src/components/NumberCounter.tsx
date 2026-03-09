import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import type { NumberCounterContent, EnhancementSpec } from "../lib/types";
import { getAnimationStyle } from "../lib/animations";
import { positionStyle } from "../lib/positions";

interface Props {
  content: NumberCounterContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [
    parseInt(h.substring(0, 2), 16),
    parseInt(h.substring(2, 4), 16),
    parseInt(h.substring(4, 6), 16),
  ];
}

function rgbToHex(r: number, g: number, b: number): string {
  return `#${[r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")}`;
}

function lerpColor(from: string, to: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(from);
  const [r2, g2, b2] = hexToRgb(to);
  return rgbToHex(
    r1 + (r2 - r1) * t,
    g1 + (g2 - g1) * t,
    b1 + (b2 - b1) * t,
  );
}

export const NumberCounter: React.FC<Props> = ({ content, spec, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const countDuration = durationFrames * 0.7;
  const progress = interpolate(frame, [0, countDuration], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateRight: "clamp",
  });

  const currentValue = Math.round(
    content.from + (content.to - content.from) * progress
  );

  const formatted = currentValue.toLocaleString();
  const display = `${content.prefix ?? ""}${formatted}${content.suffix ?? ""}`;

  const animStyle = getAnimationStyle(
    content.animation_in ?? "fade",
    content.animation_out ?? "fade",
    frame,
    fps,
    durationFrames
  );

  const pos = positionStyle(content.position);
  const fontSize = content.font_size ?? 72;
  const fontFamily = spec.global_style.font_family ?? "Inter, system-ui, sans-serif";

  const numberColor =
    content.from_color && content.to_color
      ? lerpColor(content.from_color, content.to_color, progress)
      : content.color ?? spec.global_style.accent_color ?? "#FF6B35";

  const hasLabels = content.title || content.subtitle;

  return (
    <div
      style={{
        ...pos,
        ...animStyle,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: hasLabels ? 12 : 0,
          ...(hasLabels
            ? {
                backgroundColor: "rgba(0, 0, 0, 0.75)",
                backdropFilter: "blur(16px)",
                borderRadius: 16,
                padding: "28px 48px",
                border: "1px solid rgba(255,255,255,0.1)",
              }
            : {}),
        }}
      >
        {content.title && (
          <div
            style={{
              fontSize: Math.round(fontSize * 0.32),
              fontWeight: 700,
              color: "#FFFFFF",
              fontFamily,
              textTransform: "uppercase",
              letterSpacing: 3,
              textAlign: "center",
            }}
          >
            {content.title}
          </div>
        )}
        <div
          style={{
            fontSize,
            fontWeight: 800,
            color: numberColor,
            fontFamily,
            textShadow: hasLabels ? "none" : "0 4px 12px rgba(0,0,0,0.5)",
            fontVariantNumeric: "tabular-nums",
            lineHeight: 1,
          }}
        >
          {display}
        </div>
        {content.subtitle && (
          <div
            style={{
              fontSize: Math.round(fontSize * 0.24),
              fontWeight: 500,
              color: "#AAAAAA",
              fontFamily,
              textAlign: "center",
            }}
          >
            {content.subtitle}
          </div>
        )}
      </div>
    </div>
  );
};
