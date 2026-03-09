import { interpolate, spring } from "remotion";
import type { AnimationPreset } from "./types";

interface AnimationConfig {
  opacity: number;
  transform: string;
  filter?: string;
}

export function getEntranceAnimation(
  preset: AnimationPreset | undefined,
  frame: number,
  fps: number,
  durationFrames: number
): AnimationConfig {
  const progress = spring({ frame, fps, config: { damping: 15, stiffness: 120 } });
  const linearProgress = Math.min(frame / Math.max(durationFrames * 0.3, 1), 1);

  switch (preset) {
    case "fade":
      return { opacity: linearProgress, transform: "none" };
    case "slide_up":
      return { opacity: progress, transform: `translateY(${interpolate(progress, [0, 1], [60, 0])}px)` };
    case "slide_down":
      return { opacity: progress, transform: `translateY(${interpolate(progress, [0, 1], [-60, 0])}px)` };
    case "slide_left":
      return { opacity: progress, transform: `translateX(${interpolate(progress, [0, 1], [80, 0])}px)` };
    case "slide_right":
      return { opacity: progress, transform: `translateX(${interpolate(progress, [0, 1], [-80, 0])}px)` };
    case "scale_bounce": {
      const s = spring({ frame, fps, config: { damping: 8, stiffness: 200 } });
      return { opacity: Math.min(progress * 2, 1), transform: `scale(${interpolate(s, [0, 1], [0.3, 1])})` };
    }
    case "pop": {
      const s = spring({ frame, fps, config: { damping: 10, stiffness: 300 } });
      return { opacity: Math.min(s * 3, 1), transform: `scale(${interpolate(s, [0, 1], [0, 1])})` };
    }
    case "bounce_in": {
      const s = spring({ frame, fps, config: { damping: 6, stiffness: 150 } });
      return { opacity: Math.min(s * 2, 1), transform: `scale(${interpolate(s, [0, 1], [0.5, 1])})` };
    }
    case "spring_in":
      return { opacity: progress, transform: `scale(${interpolate(progress, [0, 1], [0.8, 1])})` };
    case "blur_in":
      return {
        opacity: linearProgress,
        transform: "none",
        filter: `blur(${interpolate(linearProgress, [0, 1], [10, 0])}px)`,
      };
    case "rotate_in":
      return {
        opacity: progress,
        transform: `rotate(${interpolate(progress, [0, 1], [-15, 0])}deg) scale(${interpolate(progress, [0, 1], [0.8, 1])})`,
      };
    case "build_up": {
      const s = spring({ frame, fps, config: { damping: 20, stiffness: 80 } });
      return { opacity: s, transform: `scaleY(${interpolate(s, [0, 1], [0, 1])})` };
    }
    case "wipe":
      return {
        opacity: 1,
        transform: "none",
        filter: `inset(0 ${interpolate(linearProgress, [0, 1], [100, 0])}% 0 0)`,
      };
    case "none":
      return { opacity: 1, transform: "none" };
    default:
      return { opacity: progress, transform: `translateY(${interpolate(progress, [0, 1], [30, 0])}px)` };
  }
}

export function getExitAnimation(
  preset: AnimationPreset | undefined,
  frame: number,
  fps: number,
  durationFrames: number
): AnimationConfig {
  const exitDuration = Math.max(durationFrames * 0.2, 1);
  const framesFromEnd = durationFrames - frame;
  const progress = Math.min(framesFromEnd / exitDuration, 1);

  if (framesFromEnd > exitDuration) return { opacity: 1, transform: "none" };

  switch (preset) {
    case "fade":
      return { opacity: progress, transform: "none" };
    case "slide_up":
      return { opacity: progress, transform: `translateY(${interpolate(progress, [0, 1], [-40, 0])}px)` };
    case "slide_down":
      return { opacity: progress, transform: `translateY(${interpolate(progress, [0, 1], [40, 0])}px)` };
    case "slide_left":
      return { opacity: progress, transform: `translateX(${interpolate(progress, [0, 1], [-60, 0])}px)` };
    case "slide_right":
      return { opacity: progress, transform: `translateX(${interpolate(progress, [0, 1], [60, 0])}px)` };
    case "scale_bounce":
    case "pop":
      return { opacity: progress, transform: `scale(${interpolate(progress, [0, 1], [0.5, 1])})` };
    case "none":
      return { opacity: 1, transform: "none" };
    default:
      return { opacity: progress, transform: "none" };
  }
}

export function getAnimationStyle(
  animIn: AnimationPreset | undefined,
  animOut: AnimationPreset | undefined,
  frame: number,
  fps: number,
  durationFrames: number
): React.CSSProperties {
  const entrance = getEntranceAnimation(animIn, frame, fps, durationFrames);
  const exit = getExitAnimation(animOut, frame, fps, durationFrames);

  const isExiting = frame > durationFrames * 0.8;
  const active = isExiting && animOut && animOut !== "none" ? exit : entrance;

  return {
    opacity: isExiting ? exit.opacity : entrance.opacity,
    transform: active.transform === "none" ? undefined : active.transform,
    ...(active.filter ? { filter: active.filter } : {}),
  };
}
