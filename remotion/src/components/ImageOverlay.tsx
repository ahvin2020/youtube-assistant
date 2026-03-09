import React from "react";
import { useCurrentFrame, useVideoConfig, Img, staticFile } from "remotion";
import type { ImageOverlayContent, EnhancementSpec } from "../lib/types";
import { getAnimationStyle } from "../lib/animations";
import { positionStyle } from "../lib/positions";

interface Props {
  content: ImageOverlayContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

export const ImageOverlay: React.FC<Props> = ({ content, spec, durationFrames }) => {
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
  const src = content.image_path.startsWith("/")
    ? content.image_path
    : staticFile(content.image_path);

  return (
    <div style={{ ...pos, ...animStyle }}>
      <div
        style={{
          backgroundColor: "rgba(255, 255, 255, 0.95)",
          borderRadius: 16,
          padding: "20px 32px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
        }}
      >
        <Img
          src={src}
          style={{
            width: content.width ?? 300,
            height: content.height ?? "auto",
            objectFit: "contain",
            display: "block",
          }}
        />
      </div>
    </div>
  );
};
