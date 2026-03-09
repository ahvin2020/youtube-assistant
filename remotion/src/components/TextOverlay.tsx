import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { TextOverlayContent, EnhancementSpec } from "../lib/types";
import { getAnimationStyle } from "../lib/animations";
import { positionStyle } from "../lib/positions";

interface Props {
  content: TextOverlayContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

export const TextOverlay: React.FC<Props> = ({ content, spec, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const styleToAnim: Record<string, string> = { kinetic_pop: "scale_bounce", slide_in: "slide_right" };
  const inAnim = content.animation_in ?? (styleToAnim[content.style ?? ""] as any) ?? "fade";
  const animStyle = getAnimationStyle(
    inAnim,
    content.animation_out ?? "fade",
    frame,
    fps,
    durationFrames
  );

  const pos = positionStyle(content.position);
  const fontSize = content.font_size ?? 48;
  const color = content.color ?? spec.global_style.text_color ?? "#FFFFFF";
  const fontFamily = spec.global_style.font_family ?? "Inter, system-ui, sans-serif";

  // Typewriter effect
  if (content.style === "typewriter") {
    const totalChars = content.text.length;
    const charsVisible = Math.floor((frame / durationFrames) * totalChars * 1.5);
    const visibleText = content.text.slice(0, Math.min(charsVisible, totalChars));
    const showCursor = frame % 16 < 10;

    return (
      <div style={{ ...pos, ...animStyle, fontFamily, fontSize, color, fontWeight: 700, textShadow: "0 2px 8px rgba(0,0,0,0.7)" }}>
        {visibleText}
        {showCursor && <span style={{ opacity: 0.8 }}>|</span>}
      </div>
    );
  }

  // Highlight style
  if (content.style === "highlight") {
    const highlightProgress = Math.min(frame / (durationFrames * 0.3), 1);
    return (
      <div style={{ ...pos, ...animStyle, fontFamily, fontSize, color, fontWeight: 700 }}>
        <span
          style={{
            background: `linear-gradient(90deg, ${spec.global_style.accent_color ?? "#FF6B35"} ${highlightProgress * 100}%, transparent ${highlightProgress * 100}%)`,
            padding: "4px 12px",
            borderRadius: 4,
          }}
        >
          {content.text}
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        ...pos,
        ...animStyle,
        textAlign: "center",
      }}
    >
      <span
        style={{
          fontFamily,
          fontSize,
          color,
          fontWeight: 700,
          backgroundColor: "rgba(0, 0, 0, 0.7)",
          backdropFilter: "blur(8px)",
          padding: "12px 28px",
          borderRadius: 8,
          display: "inline-block",
          maxWidth: "80vw",
        }}
      >
        {content.text}
      </span>
    </div>
  );
};
