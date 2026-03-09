import React from "react";
import { useCurrentFrame, useVideoConfig, spring } from "remotion";
import type { ProgressTrackerContent, EnhancementSpec } from "../lib/types";
import { positionStyle } from "../lib/positions";
import { getAnimationStyle } from "../lib/animations";

interface Props {
  content: ProgressTrackerContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

export const ProgressTracker: React.FC<Props> = ({ content, spec, durationFrames }) => {
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
  const accentColor = spec.global_style.accent_color ?? "#FF6B35";
  const fontFamily = spec.global_style.font_family ?? "Inter, system-ui, sans-serif";
  const style = content.style ?? "dots";

  return (
    <div style={{ ...pos, ...animStyle, fontFamily }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: style === "bar" ? 0 : 24,
          backgroundColor: "rgba(0,0,0,0.6)",
          backdropFilter: "blur(8px)",
          borderRadius: 30,
          padding: "12px 24px",
        }}
      >
        {content.steps.map((step, i) => {
          const isActive = i + 1 === content.current_step;
          const isCompleted = step.completed || i + 1 < content.current_step;
          const stepEnter = spring({
            frame: Math.max(frame - i * 8, 0),
            fps,
            config: { damping: 12 },
          });

          return (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                opacity: stepEnter,
              }}
            >
              {/* Step indicator */}
              {style === "dots" && (
                <div
                  style={{
                    width: isActive ? 14 : 10,
                    height: isActive ? 14 : 10,
                    borderRadius: "50%",
                    backgroundColor: isCompleted || isActive ? accentColor : "rgba(255,255,255,0.3)",
                    transition: "all 0.3s",
                  }}
                />
              )}
              {style === "numbered" && (
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    backgroundColor: isCompleted || isActive ? accentColor : "rgba(255,255,255,0.2)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 14,
                    fontWeight: 700,
                    color: "#FFFFFF",
                  }}
                >
                  {i + 1}
                </div>
              )}
              {style === "checkmarks" && (
                <span style={{ fontSize: 18 }}>
                  {isCompleted ? "✅" : isActive ? "🔵" : "⬜"}
                </span>
              )}

              {/* Label */}
              <span
                style={{
                  fontSize: 14,
                  fontWeight: isActive ? 700 : 400,
                  color: isActive ? "#FFFFFF" : "rgba(255,255,255,0.6)",
                }}
              >
                {step.label}
              </span>

              {/* Connector */}
              {i < content.steps.length - 1 && style !== "bar" && (
                <div
                  style={{
                    width: 20,
                    height: 2,
                    backgroundColor: isCompleted ? accentColor : "rgba(255,255,255,0.2)",
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
