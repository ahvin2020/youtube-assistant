import React from "react";
import { useSpec } from "./SpecProvider";
import type { EnhancementType } from "../lib/types";
import { formatTimestamp } from "../lib/timing";

const TYPE_COLORS: Record<EnhancementType, string> = {
  text_overlay: "#3b82f6",
  lower_third: "#8b5cf6",
  source_overlay: "#06b6d4",
  zoom_effect: "#f59e0b",
  sound_effect: "#ef4444",
  section_divider: "#6366f1",
  data_viz: "#10b981",
  icon_accent: "#f97316",
  callout_box: "#ec4899",
  animated_list: "#14b8a6",
  number_counter: "#a855f7",
  split_screen: "#0ea5e9",
  progress_tracker: "#84cc16",
  map_highlight: "#e11d48",
  transition: "#64748b",
  image_overlay: "#d97706",
};

function displayName(enh: { type: string; content: any }): string {
  const c = enh.content;
  switch (enh.type) {
    case "text_overlay": return c.text?.slice(0, 25) ?? "Text";
    case "lower_third": return c.name ?? "Lower Third";
    case "source_overlay": return c.headline ?? "Source";
    case "zoom_effect": return c.zoom_type ?? "Zoom";
    case "sound_effect": return c.sfx_id ?? "SFX";
    case "section_divider": return c.label ?? "Divider";
    case "data_viz": return c.title ?? c.chart_type ?? "Chart";
    case "icon_accent": return c.icon ?? "Icon";
    case "callout_box": return c.text?.slice(0, 25) ?? "Callout";
    case "animated_list": return `List (${c.items?.length ?? 0})`;
    case "number_counter": return `${c.prefix ?? ""}${c.from}→${c.to}`;
    case "split_screen": return `${c.left?.label} vs ${c.right?.label}`;
    case "progress_tracker": return `Step ${c.current_step}/${c.steps?.length}`;
    case "map_highlight": return "Map";
    case "transition": return c.transition_type ?? "Transition";
    case "image_overlay": return "Image";
    default: return enh.type;
  }
}

export const EnhancementList: React.FC = () => {
  const { spec, selectedId, setSelectedId, removeEnhancement } = useSpec();

  const grouped = spec.sections.map((section) => ({
    section,
    enhancements: spec.enhancements
      .filter((e) => e.section_id === section.id)
      .sort((a, b) => a.start_seconds - b.start_seconds),
  }));

  return (
    <div style={{ padding: 12 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: "#fff", marginBottom: 12, padding: "0 4px" }}>
        Enhancements
      </div>

      {grouped.map(({ section, enhancements }) => (
        <div key={section.id} style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "#888", textTransform: "uppercase", letterSpacing: 1, padding: "4px 4px 6px" }}>
            {section.label}
          </div>

          {enhancements.map((enh) => {
            const isSelected = enh.id === selectedId;
            const color = TYPE_COLORS[enh.type as EnhancementType] ?? "#666";

            return (
              <div
                key={enh.id}
                onClick={() => setSelectedId(enh.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 8px",
                  borderRadius: 6,
                  cursor: "pointer",
                  backgroundColor: isSelected ? "rgba(255,255,255,0.08)" : "transparent",
                  borderLeft: `3px solid ${isSelected ? color : "transparent"}`,
                  marginBottom: 2,
                }}
              >
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    color,
                    backgroundColor: `${color}22`,
                    padding: "2px 6px",
                    borderRadius: 3,
                    textTransform: "uppercase",
                    whiteSpace: "nowrap",
                  }}
                >
                  {enh.type.replace(/_/g, " ")}
                </span>
                <span style={{ flex: 1, fontSize: 12, color: "#ccc", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {displayName(enh)}
                </span>
                <span style={{ fontSize: 10, color: "#666", whiteSpace: "nowrap" }}>
                  {formatTimestamp(enh.start_seconds)}
                </span>
                <button
                  onClick={(e) => { e.stopPropagation(); removeEnhancement(enh.id); }}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#555",
                    cursor: "pointer",
                    fontSize: 14,
                    padding: "0 2px",
                    lineHeight: 1,
                  }}
                >
                  ×
                </button>
              </div>
            );
          })}

          {enhancements.length === 0 && (
            <div style={{ fontSize: 11, color: "#555", padding: "4px 8px", fontStyle: "italic" }}>
              No enhancements
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
