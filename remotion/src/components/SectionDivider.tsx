import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import type { SectionDividerContent, EnhancementSpec } from "../lib/types";

interface Props {
  content: SectionDividerContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

export const SectionDivider: React.FC<Props> = ({ content, spec, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = spring({ frame, fps, config: { damping: 15, stiffness: 120 } });
  const exitFrame = Math.max(frame - (durationFrames - fps * 0.4), 0);
  const exit = exitFrame > 0 ? spring({ frame: exitFrame, fps }) : 0;
  const opacity = enter * (1 - exit);

  const accentColor = spec.global_style.accent_color ?? "#FF6B35";
  const fontFamily = spec.global_style.font_family ?? "Inter, system-ui, sans-serif";

  if (content.style === "full_card") {
    return (
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundColor: `rgba(0, 0, 0, ${(spec.global_style.background_opacity ?? 0.85) * opacity})`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily,
        }}
      >
        {content.number && (
          <div
            style={{
              fontSize: 120,
              fontWeight: 800,
              color: accentColor,
              opacity: enter,
              transform: `scale(${interpolate(enter, [0, 1], [0.5, 1])})`,
            }}
          >
            {content.number}
          </div>
        )}
        <div
          style={{
            fontSize: 42,
            fontWeight: 700,
            color: "#FFFFFF",
            opacity: enter,
            transform: `translateY(${interpolate(enter, [0, 1], [20, 0])}px)`,
            marginTop: 10,
          }}
        >
          {content.label}
        </div>
      </div>
    );
  }

  // minimal_bar style
  return (
    <div
      style={{
        position: "absolute",
        left: "50%",
        top: "50%",
        transform: "translate(-50%, -50%)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 16,
        opacity,
        fontFamily,
      }}
    >
      <div
        style={{
          width: interpolate(enter, [0, 1], [0, 200]),
          height: 3,
          backgroundColor: accentColor,
          borderRadius: 2,
        }}
      />
      <div style={{ fontSize: 28, fontWeight: 600, color: "#FFFFFF", textTransform: "uppercase", letterSpacing: 4 }}>
        {content.label}
      </div>
      {content.total_sections && content.number && (
        <div style={{ display: "flex", gap: 8 }}>
          {Array.from({ length: content.total_sections }).map((_, i) => (
            <div
              key={i}
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                backgroundColor: i < content.number! ? accentColor : "rgba(255,255,255,0.3)",
              }}
            />
          ))}
        </div>
      )}
      <div
        style={{
          width: interpolate(enter, [0, 1], [0, 200]),
          height: 3,
          backgroundColor: accentColor,
          borderRadius: 2,
        }}
      />
    </div>
  );
};
