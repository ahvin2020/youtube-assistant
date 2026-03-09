import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import type { LowerThirdContent, EnhancementSpec } from "../lib/types";

interface Props {
  content: LowerThirdContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

export const LowerThird: React.FC<Props> = ({ content, spec, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enterProgress = spring({ frame, fps, config: { damping: 15, stiffness: 120 } });
  const exitFrame = Math.max(frame - (durationFrames - fps * 0.5), 0);
  const exitProgress = exitFrame > 0 ? spring({ frame: exitFrame, fps, config: { damping: 15 } }) : 0;

  const translateY = interpolate(enterProgress, [0, 1], [80, 0]) + interpolate(exitProgress, [0, 1], [0, 80]);
  const opacity = enterProgress * (1 - exitProgress);

  const accentColor = spec.global_style.accent_color ?? "#FF6B35";
  const fontFamily = spec.global_style.font_family ?? "Inter, system-ui, sans-serif";

  const isRight = content.position === "bottom_right";
  const posStyle: React.CSSProperties = {
    position: "absolute",
    bottom: 80,
    ...(isRight ? { right: 60 } : { left: 60 }),
  };

  return (
    <div
      style={{
        ...posStyle,
        transform: `translateY(${translateY}px)`,
        opacity,
        display: "flex",
        alignItems: "stretch",
        fontFamily,
      }}
    >
      <div style={{ width: 4, backgroundColor: accentColor, borderRadius: 2 }} />
      <div
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.75)",
          backdropFilter: "blur(8px)",
          padding: "12px 24px",
          borderRadius: "0 6px 6px 0",
        }}
      >
        <div style={{ color: "#FFFFFF", fontSize: 24, fontWeight: 700, lineHeight: 1.3 }}>
          {content.name}
        </div>
        <div style={{ color: accentColor, fontSize: 16, fontWeight: 500, marginTop: 2 }}>
          {content.title}
        </div>
      </div>
    </div>
  );
};
