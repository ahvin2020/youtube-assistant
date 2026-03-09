import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { IconAccentContent, EnhancementSpec } from "../lib/types";
import { getAnimationStyle } from "../lib/animations";
import { positionStyle } from "../lib/positions";

const ICON_MAP: Record<string, string> = {
  chart_up: "📈", chart_down: "📉", money: "💰", dollar: "💵",
  warning: "⚠️", check: "✅", cross: "❌", star: "⭐",
  fire: "🔥", rocket: "🚀", lightbulb: "💡", target: "🎯",
  clock: "⏰", calendar: "📅", lock: "🔒", unlock: "🔓",
  heart: "❤️", thumbs_up: "👍", thumbs_down: "👎", trophy: "🏆",
  gift: "🎁", flag: "🚩", pin: "📌", megaphone: "📢",
  book: "📖", calculator: "🧮", bank: "🏦", house: "🏠",
  car: "🚗", plane: "✈️", globe: "🌍", sparkles: "✨",
};

interface Props {
  content: IconAccentContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

export const IconAccent: React.FC<Props> = ({ content, spec, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const animStyle = getAnimationStyle(
    content.animation ?? "bounce_in",
    "fade",
    frame,
    fps,
    durationFrames
  );

  const pos = positionStyle(content.position);
  const icon = ICON_MAP[content.icon] ?? content.icon ?? "✨";
  const size = content.size ?? 48;

  return (
    <div style={{ ...pos, ...animStyle, fontSize: size, lineHeight: 1 }}>
      {icon}
    </div>
  );
};
