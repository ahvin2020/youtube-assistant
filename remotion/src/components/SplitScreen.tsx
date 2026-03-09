import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import type { SplitScreenContent, EnhancementSpec } from "../lib/types";

interface Props {
  content: SplitScreenContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

export const SplitScreen: React.FC<Props> = ({ content, spec, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const leftEnter = spring({ frame, fps, config: { damping: 15, stiffness: 100 } });
  const rightEnter = spring({ frame: Math.max(frame - 5, 0), fps, config: { damping: 15, stiffness: 100 } });

  const exitFrame = Math.max(frame - (durationFrames - fps * 0.4), 0);
  const exit = exitFrame > 0 ? spring({ frame: exitFrame, fps }) : 0;
  const opacity = 1 - exit;

  const fontFamily = spec.global_style.font_family ?? "Inter, system-ui, sans-serif";

  const Panel: React.FC<{
    data: { label: string; value: string; color?: string };
    enter: number;
    fromX: number;
  }> = ({ data, enter, fromX }) => (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: data.color ?? "rgba(0,0,0,0.6)",
        padding: 40,
        opacity: enter,
        transform: `translateX(${interpolate(enter, [0, 1], [fromX, 0])}px)`,
      }}
    >
      <div style={{ fontSize: 28, fontWeight: 600, color: "#FFFFFF", marginBottom: 12 }}>
        {data.label}
      </div>
      <div style={{ fontSize: 56, fontWeight: 800, color: "#FFFFFF" }}>
        {data.value}
      </div>
    </div>
  );

  const divider = content.divider_style ?? "vs";

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        opacity,
        fontFamily,
      }}
    >
      <Panel data={content.left} enter={leftEnter} fromX={-100} />

      {/* Divider */}
      <div
        style={{
          width: divider === "vs" ? 80 : 4,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: divider === "vs" ? "rgba(0,0,0,0.8)" : spec.global_style.accent_color ?? "#FF6B35",
          zIndex: 1,
        }}
      >
        {divider === "vs" && (
          <span style={{ color: "#FFFFFF", fontSize: 32, fontWeight: 800 }}>VS</span>
        )}
      </div>

      <Panel data={content.right} enter={rightEnter} fromX={100} />
    </div>
  );
};
