import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import type { ZoomEffectContent } from "../lib/types";

interface Props {
  content: ZoomEffectContent;
  startFrame: number;
  durationFrames: number;
  children: React.ReactNode;
}

const EASING_MAP = {
  ease_in: Easing.in(Easing.cubic),
  ease_out: Easing.out(Easing.cubic),
  ease_in_out: Easing.inOut(Easing.cubic),
  linear: Easing.linear,
  spring: Easing.out(Easing.back(1.2)),
};

export const ZoomEffect: React.FC<Props> = ({ content, startFrame, durationFrames, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const localFrame = frame - startFrame;
  const isActive = localFrame >= 0 && localFrame < durationFrames;

  if (!isActive) return <>{children}</>;

  const easing = EASING_MAP[content.easing ?? "ease_out"] ?? EASING_MAP.ease_out;
  const progress = interpolate(localFrame, [0, durationFrames], [0, 1], {
    easing,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const fromScale = content.from_scale ?? 1.0;
  const toScale = content.to_scale ?? 1.15;

  let scale: number;
  let translateX = 0;
  let translateY = 0;

  switch (content.zoom_type) {
    case "push_in":
      scale = interpolate(progress, [0, 1], [fromScale, toScale]);
      break;
    case "push_out":
      scale = interpolate(progress, [0, 1], [toScale, fromScale]);
      break;
    case "pan_left":
      scale = toScale;
      translateX = interpolate(progress, [0, 1], [0, -60]);
      break;
    case "pan_right":
      scale = toScale;
      translateX = interpolate(progress, [0, 1], [0, 60]);
      break;
    case "ken_burns":
      scale = interpolate(progress, [0, 1], [fromScale, toScale]);
      translateX = interpolate(progress, [0, 1], [0, 30]);
      translateY = interpolate(progress, [0, 1], [0, -15]);
      break;
    default:
      scale = interpolate(progress, [0, 1], [fromScale, toScale]);
  }

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)`,
        transformOrigin: "center center",
      }}
    >
      {children}
    </div>
  );
};
