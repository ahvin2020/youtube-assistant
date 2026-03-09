import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { CalloutBoxContent, EnhancementSpec } from "../lib/types";
import { getAnimationStyle } from "../lib/animations";
import { positionStyle } from "../lib/positions";

const STYLE_CONFIG = {
  quote: { icon: "💬", borderColor: "#9b59b6" },
  insight: { icon: "💡", borderColor: "#f39c12" },
  warning: { icon: "⚠️", borderColor: "#e74c3c" },
  tip: { icon: "✅", borderColor: "#2ecc71" },
};

interface Props {
  content: CalloutBoxContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

export const CalloutBox: React.FC<Props> = ({ content, spec, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const animStyle = getAnimationStyle(
    content.animation_in ?? "slide_up",
    content.animation_out ?? "fade",
    frame,
    fps,
    durationFrames
  );

  const pos = positionStyle(content.position);
  const config = STYLE_CONFIG[content.style ?? "insight"];
  const fontFamily = spec.global_style.font_family ?? "Inter, system-ui, sans-serif";

  return (
    <div style={{ ...pos, ...animStyle, maxWidth: 700 }}>
      <div
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.8)",
          backdropFilter: "blur(12px)",
          borderLeft: `4px solid ${config.borderColor}`,
          borderRadius: "0 8px 8px 0",
          padding: "20px 28px",
          display: "flex",
          gap: 16,
          alignItems: "flex-start",
          fontFamily,
        }}
      >
        <span style={{ fontSize: 28, flexShrink: 0 }}>{config.icon}</span>
        <div style={{ color: "#FFFFFF", fontSize: 22, lineHeight: 1.5, fontWeight: 500 }}>
          {content.text}
        </div>
      </div>
    </div>
  );
};
