import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate, Img } from "remotion";
import type { MapHighlightContent, EnhancementSpec } from "../lib/types";
import { positionStyle } from "../lib/positions";
import { getAnimationStyle } from "../lib/animations";

interface Props {
  content: MapHighlightContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

export const MapHighlight: React.FC<Props> = ({ content, spec, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const animStyle = getAnimationStyle(
    content.animation_in ?? "fade",
    content.animation_out ?? "fade",
    frame,
    fps,
    durationFrames
  );

  const pos = positionStyle(content.position);
  const scale = content.scale ?? 0.7;

  return (
    <div style={{ ...pos, ...animStyle, transform: `translate(-50%, -50%) scale(${scale})` }}>
      <div style={{ position: "relative" }}>
        {content.image_path ? (
          <Img src={content.image_path} style={{ borderRadius: 8, display: "block" }} />
        ) : (
          <div style={{ width: 600, height: 400, backgroundColor: "#2d3748", borderRadius: 8 }} />
        )}

        {content.highlights?.map((hl, i) => {
          const hlEnter = spring({
            frame: Math.max(frame - i * 10 - fps * 0.2, 0),
            fps,
            config: { damping: 10, stiffness: 100 },
          });

          return (
            <React.Fragment key={i}>
              <div
                style={{
                  position: "absolute",
                  left: hl.x,
                  top: hl.y,
                  width: hl.width,
                  height: hl.height,
                  border: `3px solid ${hl.color ?? spec.global_style.accent_color ?? "#FF6B35"}`,
                  borderRadius: 6,
                  backgroundColor: `${hl.color ?? spec.global_style.accent_color ?? "#FF6B35"}33`,
                  opacity: hlEnter,
                  transform: `scale(${interpolate(hlEnter, [0, 1], [1.2, 1])})`,
                }}
              />
              {hl.label && (
                <div
                  style={{
                    position: "absolute",
                    left: hl.x,
                    top: hl.y - 28,
                    fontSize: 14,
                    fontWeight: 600,
                    color: "#FFFFFF",
                    backgroundColor: hl.color ?? spec.global_style.accent_color ?? "#FF6B35",
                    padding: "2px 8px",
                    borderRadius: 4,
                    opacity: hlEnter,
                  }}
                >
                  {hl.label}
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};
