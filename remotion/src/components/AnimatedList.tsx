import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import type { AnimatedListContent, EnhancementSpec } from "../lib/types";
import { positionStyle } from "../lib/positions";
import { getExitAnimation } from "../lib/animations";

interface Props {
  content: AnimatedListContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

export const AnimatedList: React.FC<Props> = ({ content, spec, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const pos = positionStyle(content.position);
  const stagger = content.stagger_frames ?? 15;
  const fontFamily = spec.global_style.font_family ?? "Inter, system-ui, sans-serif";
  const accentColor = spec.global_style.accent_color ?? "#FF6B35";

  const exit = getExitAnimation(content.animation_out ?? "fade", frame, fps, durationFrames);

  return (
    <div style={{ ...pos, ...exit, fontFamily }}>
      <div
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.75)",
          backdropFilter: "blur(8px)",
          borderRadius: 12,
          padding: "20px 28px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {content.items.map((item, i) => {
          const delay = content.reveal_style === "all_at_once" ? 0 : i * stagger;
          const itemProgress = spring({
            frame: Math.max(frame - delay, 0),
            fps,
            config: { damping: 12, stiffness: 120 },
          });

          return (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 14,
                opacity: itemProgress,
                transform: `translateX(${interpolate(itemProgress, [0, 1], [40, 0])}px)`,
              }}
            >
              {item.icon && <span style={{ fontSize: 24 }}>{item.icon}</span>}
              <span style={{ color: "#FFFFFF", fontSize: 22, fontWeight: 500 }}>{item.text}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
