import type { Position, NamedX, NamedY } from "./types";

const X_MAP: Record<NamedX, number> = {
  left: 200,
  center: 960,
  right: 1440,
};

const Y_MAP: Record<NamedY, number> = {
  top: 80,
  top_third: 300,
  center: 540,
  bottom_third: 750,
  bottom: 980,
};

export function resolvePosition(
  pos: Position | undefined,
  width: number = 1920,
  height: number = 1080
): { x: number; y: number } {
  if (!pos) return { x: width / 2, y: height / 2 };
  const x = typeof pos.x === "string" ? X_MAP[pos.x] ?? width / 2 : pos.x;
  const y = typeof pos.y === "string" ? Y_MAP[pos.y] ?? height / 2 : pos.y;
  return { x, y };
}

export function positionStyle(pos: Position | undefined): React.CSSProperties {
  const { x, y } = resolvePosition(pos);
  return {
    position: "absolute",
    left: x,
    top: y,
    transform: "translate(-50%, -50%)",
  };
}
