import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate, Img } from "remotion";
import type { SourceOverlayContent, EnhancementSpec } from "../lib/types";
import { positionStyle } from "../lib/positions";

interface Props {
  content: SourceOverlayContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

export const SourceOverlay: React.FC<Props> = ({ content, spec, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = spring({ frame, fps, config: { damping: 15, stiffness: 100 } });
  const exitFrame = Math.max(frame - (durationFrames - fps * 0.3), 0);
  const exit = exitFrame > 0 ? spring({ frame: exitFrame, fps }) : 0;
  const opacity = enter * (1 - exit);
  const scale = (content.scale ?? 0.6) * interpolate(enter, [0, 1], [0.9, 1]);

  const pos = positionStyle(content.position);
  const accentColor = spec.global_style.accent_color ?? "#FF6B35";

  return (
    <div style={{ ...pos, opacity, transform: `translate(-50%, -50%) scale(${scale})` }}>
      {/* Browser chrome mockup */}
      <div
        style={{
          backgroundColor: "#2d2d2d",
          borderRadius: "8px 8px 0 0",
          padding: "8px 12px",
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <div style={{ width: 10, height: 10, borderRadius: "50%", backgroundColor: "#ff5f57" }} />
        <div style={{ width: 10, height: 10, borderRadius: "50%", backgroundColor: "#febc2e" }} />
        <div style={{ width: 10, height: 10, borderRadius: "50%", backgroundColor: "#28c840" }} />
        {content.headline && (
          <div style={{ color: "#999", fontSize: 11, marginLeft: 8, fontFamily: "monospace" }}>
            {content.headline}
          </div>
        )}
      </div>

      {/* Screenshot */}
      <div style={{ position: "relative", backgroundColor: "#fff", borderRadius: "0 0 8px 8px", overflow: "hidden" }}>
        {content.screenshot_path ? (
          <Img src={content.screenshot_path} style={{ width: 800, display: "block" }} />
        ) : (
          <div style={{ width: 800, height: 450, backgroundColor: "#f0f0f0", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ color: "#999", fontSize: 24 }}>Screenshot</span>
          </div>
        )}

        {/* Highlight regions */}
        {content.highlight_regions?.map((region, i) => {
          const regionEnter = spring({
            frame: Math.max(frame - i * 5 - fps * 0.3, 0),
            fps,
            config: { damping: 12 },
          });
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: region.x,
                top: region.y,
                width: region.width,
                height: region.height,
                border: `3px solid ${accentColor}`,
                borderRadius: 4,
                backgroundColor: `${accentColor}22`,
                opacity: regionEnter,
                transform: `scale(${interpolate(regionEnter, [0, 1], [1.1, 1])})`,
              }}
            />
          );
        })}
      </div>
    </div>
  );
};
