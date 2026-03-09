import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import type { TransitionContent } from "../lib/types";

interface Props {
  content: TransitionContent;
  durationFrames: number;
}

const SPEED_MAP = { slow: 0.6, normal: 1, fast: 1.5 };

export const TransitionEffect: React.FC<Props> = ({ content, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const speed = SPEED_MAP[content.speed ?? "normal"];
  const progress = interpolate(frame, [0, durationFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  switch (content.transition_type) {
    case "whip":
    case "swish": {
      const bandWidth = 300;
      const dir = content.direction ?? "right";
      const isHorizontal = dir === "left" || dir === "right";
      const pos = interpolate(progress, [0, 1], [-bandWidth, isHorizontal ? 1920 + bandWidth : 1080 + bandWidth], {
        easing: Easing.inOut(Easing.cubic),
      });

      return (
        <div
          style={{
            position: "absolute",
            inset: 0,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              position: "absolute",
              ...(isHorizontal
                ? { top: 0, bottom: 0, left: pos, width: bandWidth }
                : { left: 0, right: 0, top: pos, height: bandWidth }),
              background: `linear-gradient(${isHorizontal ? "90deg" : "180deg"}, transparent, rgba(0,0,0,0.8), transparent)`,
              filter: "blur(20px)",
            }}
          />
        </div>
      );
    }

    case "wipe": {
      const dir = content.direction ?? "right";
      const clipMap: Record<string, string> = {
        right: `inset(0 ${(1 - progress) * 100}% 0 0)`,
        left: `inset(0 0 0 ${(1 - progress) * 100}%)`,
        down: `inset(0 0 ${(1 - progress) * 100}% 0)`,
        up: `inset(${(1 - progress) * 100}% 0 0 0)`,
      };
      return (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundColor: "#000",
            clipPath: clipMap[dir],
          }}
        />
      );
    }

    case "dissolve": {
      const opacity = progress < 0.5
        ? interpolate(progress, [0, 0.5], [0, 1])
        : interpolate(progress, [0.5, 1], [1, 0]);
      return (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundColor: "#000",
            opacity,
          }}
        />
      );
    }

    case "zoom_through": {
      const scale = interpolate(progress, [0, 0.5, 1], [1, 8, 1], {
        easing: Easing.inOut(Easing.cubic),
      });
      const opacity = progress < 0.5
        ? interpolate(progress, [0.3, 0.5], [0, 1], { extrapolateLeft: "clamp" })
        : interpolate(progress, [0.5, 0.7], [1, 0], { extrapolateRight: "clamp" });
      return (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundColor: "#000",
            opacity,
            transform: `scale(${scale})`,
          }}
        />
      );
    }

    default:
      return null;
  }
};
