import React, { useRef, useCallback } from "react";
import { useSpec } from "./SpecProvider";
import type { EnhancementType } from "../lib/types";
import { formatTimestamp } from "../lib/timing";

const TYPE_COLORS: Record<string, string> = {
  text_overlay: "#4CAF50",
  lower_third: "#2196F3",
  source_overlay: "#FF9800",
  zoom_effect: "#9C27B0",
  sound_effect: "#E91E63",
  section_divider: "#607D8B",
  data_viz: "#00BCD4",
  icon_accent: "#FFEB3B",
  callout_box: "#8BC34A",
  animated_list: "#3F51B5",
  number_counter: "#FF5722",
  split_screen: "#795548",
  progress_tracker: "#009688",
  map_highlight: "#CDDC39",
  transition: "#F44336",
};

const TRACK_HEIGHT = 28;
const HEADER_WIDTH = 80;
const PIXELS_PER_SECOND = 40;

export const Timeline: React.FC = () => {
  const { spec, selectedId, setSelectedId, updateEnhancement } = useSpec();
  const containerRef = useRef<HTMLDivElement>(null);

  const totalWidth = spec.duration_seconds * PIXELS_PER_SECOND;

  // Group enhancements into tracks (non-overlapping per track)
  const tracks = assignTracks(spec.enhancements);

  // Drag state
  const dragRef = useRef<{
    id: string;
    edge: "start" | "end" | "move";
    initialX: number;
    initialStart: number;
    initialEnd: number;
  } | null>(null);

  const handleMouseDown = useCallback(
    (
      e: React.MouseEvent,
      id: string,
      edge: "start" | "end" | "move"
    ) => {
      e.preventDefault();
      const enh = spec.enhancements.find((en) => en.id === id);
      if (!enh) return;

      dragRef.current = {
        id,
        edge,
        initialX: e.clientX,
        initialStart: enh.start_seconds,
        initialEnd: enh.end_seconds,
      };
      setSelectedId(id);

      const handleMouseMove = (me: MouseEvent) => {
        if (!dragRef.current) return;
        const dx = me.clientX - dragRef.current.initialX;
        const dSeconds = dx / PIXELS_PER_SECOND;

        if (dragRef.current.edge === "move") {
          const newStart = Math.max(0, dragRef.current.initialStart + dSeconds);
          const duration = dragRef.current.initialEnd - dragRef.current.initialStart;
          updateEnhancement(dragRef.current.id, {
            start_seconds: newStart,
            end_seconds: newStart + duration,
          });
        } else if (dragRef.current.edge === "start") {
          const newStart = Math.max(
            0,
            Math.min(dragRef.current.initialEnd - 0.1, dragRef.current.initialStart + dSeconds)
          );
          updateEnhancement(dragRef.current.id, { start_seconds: newStart });
        } else {
          const newEnd = Math.max(
            dragRef.current.initialStart + 0.1,
            dragRef.current.initialEnd + dSeconds
          );
          updateEnhancement(dragRef.current.id, { end_seconds: newEnd });
        }
      };

      const handleMouseUp = () => {
        dragRef.current = null;
        window.removeEventListener("mousemove", handleMouseMove);
        window.removeEventListener("mouseup", handleMouseUp);
      };

      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
    },
    [spec.enhancements, updateEnhancement, setSelectedId]
  );

  // Time markers
  const markers: number[] = [];
  for (let t = 0; t <= spec.duration_seconds; t += 5) {
    markers.push(t);
  }

  return (
    <div style={{ height: "100%", overflow: "auto" }} ref={containerRef}>
      {/* Time ruler */}
      <div
        style={{
          display: "flex",
          height: 24,
          borderBottom: "1px solid #2a2a2a",
          position: "sticky",
          top: 0,
          backgroundColor: "#131313",
          zIndex: 1,
        }}
      >
        <div style={{ width: HEADER_WIDTH, flexShrink: 0 }} />
        <div style={{ position: "relative", width: totalWidth }}>
          {markers.map((t) => (
            <div
              key={t}
              style={{
                position: "absolute",
                left: t * PIXELS_PER_SECOND,
                fontSize: 10,
                color: "#555",
                top: 6,
              }}
            >
              {formatTimestamp(t)}
            </div>
          ))}
        </div>
      </div>

      {/* Tracks */}
      {tracks.map((track, trackIdx) => (
        <div
          key={trackIdx}
          style={{
            display: "flex",
            height: TRACK_HEIGHT + 4,
            borderBottom: "1px solid #1a1a1a",
          }}
        >
          <div
            style={{
              width: HEADER_WIDTH,
              flexShrink: 0,
              fontSize: 10,
              color: "#555",
              display: "flex",
              alignItems: "center",
              paddingLeft: 8,
            }}
          >
            Track {trackIdx + 1}
          </div>
          <div style={{ position: "relative", width: totalWidth }}>
            {track.map((enh) => {
              const left = enh.start_seconds * PIXELS_PER_SECOND;
              const width =
                (enh.end_seconds - enh.start_seconds) * PIXELS_PER_SECOND;
              const color = TYPE_COLORS[enh.type] || "#888";
              const isSelected = selectedId === enh.id;

              return (
                <div
                  key={enh.id}
                  style={{
                    position: "absolute",
                    left,
                    top: 2,
                    width: Math.max(width, 4),
                    height: TRACK_HEIGHT,
                    backgroundColor: `${color}${isSelected ? "cc" : "66"}`,
                    border: isSelected
                      ? `2px solid ${color}`
                      : `1px solid ${color}44`,
                    borderRadius: 4,
                    cursor: "move",
                    display: "flex",
                    alignItems: "center",
                    overflow: "hidden",
                    fontSize: 10,
                    color: "#fff",
                    paddingLeft: 4,
                    userSelect: "none",
                  }}
                  onMouseDown={(e) => handleMouseDown(e, enh.id, "move")}
                  onClick={() => setSelectedId(enh.id)}
                >
                  {/* Left resize handle */}
                  <div
                    style={{
                      position: "absolute",
                      left: 0,
                      top: 0,
                      bottom: 0,
                      width: 6,
                      cursor: "ew-resize",
                    }}
                    onMouseDown={(e) => {
                      e.stopPropagation();
                      handleMouseDown(e, enh.id, "start");
                    }}
                  />
                  {/* Label */}
                  <span
                    style={{
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      padding: "0 8px",
                    }}
                  >
                    {enh.type.replace(/_/g, " ")}
                  </span>
                  {/* Right resize handle */}
                  <div
                    style={{
                      position: "absolute",
                      right: 0,
                      top: 0,
                      bottom: 0,
                      width: 6,
                      cursor: "ew-resize",
                    }}
                    onMouseDown={(e) => {
                      e.stopPropagation();
                      handleMouseDown(e, enh.id, "end");
                    }}
                  />
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};

// Assign enhancements to non-overlapping tracks
function assignTracks(
  enhancements: Array<{ id: string; type: EnhancementType; start_seconds: number; end_seconds: number }>
): typeof enhancements[] {
  const sorted = [...enhancements].sort(
    (a, b) => a.start_seconds - b.start_seconds
  );
  const tracks: typeof enhancements[] = [];

  for (const enh of sorted) {
    let placed = false;
    for (const track of tracks) {
      const lastInTrack = track[track.length - 1];
      if (lastInTrack.end_seconds <= enh.start_seconds) {
        track.push(enh);
        placed = true;
        break;
      }
    }
    if (!placed) {
      tracks.push([enh]);
    }
  }

  return tracks;
}
