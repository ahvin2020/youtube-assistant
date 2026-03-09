import React from "react";
import { useSpec } from "./SpecProvider";
import type { Enhancement, AnimationPreset } from "../lib/types";

const ANIMATION_PRESETS: AnimationPreset[] = [
  "none",
  "fade",
  "slide_up",
  "slide_down",
  "slide_left",
  "slide_right",
  "scale_bounce",
  "pop",
  "bounce_in",
  "spring_in",
  "blur_in",
  "rotate_in",
  "build_up",
  "typewriter",
  "wipe",
];

export const PropertyPanel: React.FC = () => {
  const { spec, selectedId, updateEnhancement } = useSpec();

  const selected = spec.enhancements.find((e) => e.id === selectedId);

  if (!selected) {
    return (
      <div style={{ padding: 16, color: "#666", fontSize: 13 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: 1,
            color: "#888",
            marginBottom: 12,
          }}
        >
          Properties
        </div>
        <p>Select an enhancement to edit its properties.</p>
      </div>
    );
  }

  const content = selected.content as Record<string, unknown>;

  const updateContent = (key: string, value: unknown) => {
    updateEnhancement(selected.id, {
      content: { ...selected.content, [key]: value },
    } as Partial<Enhancement>);
  };

  const updateTiming = (key: "start_seconds" | "end_seconds", value: number) => {
    updateEnhancement(selected.id, { [key]: value });
  };

  return (
    <div style={{ padding: 16 }}>
      <div
        style={{
          fontSize: 13,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: 1,
          color: "#888",
          marginBottom: 16,
        }}
      >
        Properties — {selected.type.replace(/_/g, " ")}
      </div>

      {/* Timing */}
      <FieldGroup label="Timing">
        <NumberField
          label="Start (s)"
          value={selected.start_seconds}
          step={0.1}
          onChange={(v) => updateTiming("start_seconds", v)}
        />
        <NumberField
          label="End (s)"
          value={selected.end_seconds}
          step={0.1}
          onChange={(v) => updateTiming("end_seconds", v)}
        />
      </FieldGroup>

      {/* Content-specific fields */}
      {"text" in content && (
        <FieldGroup label="Content">
          <TextField
            label="Text"
            value={String(content.text)}
            onChange={(v) => updateContent("text", v)}
          />
        </FieldGroup>
      )}

      {"name" in content && (
        <FieldGroup label="Content">
          <TextField
            label="Name"
            value={String(content.name)}
            onChange={(v) => updateContent("name", v)}
          />
          {"title" in content && (
            <TextField
              label="Title"
              value={String(content.title)}
              onChange={(v) => updateContent("title", v)}
            />
          )}
        </FieldGroup>
      )}

      {"font_size" in content && (
        <FieldGroup label="Style">
          <NumberField
            label="Font size"
            value={Number(content.font_size)}
            step={2}
            onChange={(v) => updateContent("font_size", v)}
          />
        </FieldGroup>
      )}

      {"label" in content && !("name" in content) && (
        <FieldGroup label="Content">
          <TextField
            label="Label"
            value={String(content.label)}
            onChange={(v) => updateContent("label", v)}
          />
        </FieldGroup>
      )}

      {"sfx_id" in content && (
        <FieldGroup label="Sound">
          <TextField
            label="SFX ID"
            value={String(content.sfx_id)}
            onChange={(v) => updateContent("sfx_id", v)}
          />
          <NumberField
            label="Volume"
            value={Number(content.volume)}
            step={0.1}
            min={0}
            max={1}
            onChange={(v) => updateContent("volume", v)}
          />
        </FieldGroup>
      )}

      {"scale" in content && (
        <FieldGroup label="Transform">
          <NumberField
            label="Scale"
            value={Number(content.scale)}
            step={0.05}
            onChange={(v) => updateContent("scale", v)}
          />
        </FieldGroup>
      )}

      {"animation_in" in content && (
        <FieldGroup label="Animation">
          <SelectField
            label="Enter"
            value={String(content.animation_in)}
            options={ANIMATION_PRESETS}
            onChange={(v) => updateContent("animation_in", v)}
          />
          {"animation_out" in content && (
            <SelectField
              label="Exit"
              value={String(content.animation_out)}
              options={ANIMATION_PRESETS}
              onChange={(v) => updateContent("animation_out", v)}
            />
          )}
        </FieldGroup>
      )}

      {"zoom_type" in content && (
        <FieldGroup label="Zoom">
          <SelectField
            label="Type"
            value={String(content.zoom_type)}
            options={["push_in", "push_out", "pan_left", "pan_right", "ken_burns"]}
            onChange={(v) => updateContent("zoom_type", v)}
          />
          <NumberField
            label="From scale"
            value={Number(content.from_scale)}
            step={0.05}
            onChange={(v) => updateContent("from_scale", v)}
          />
          <NumberField
            label="To scale"
            value={Number(content.to_scale)}
            step={0.05}
            onChange={(v) => updateContent("to_scale", v)}
          />
        </FieldGroup>
      )}

      {/* ID reference */}
      <div style={{ marginTop: 24, fontSize: 11, color: "#444" }}>
        ID: {selected.id}
      </div>
    </div>
  );
};

// --- Field components ---

const FieldGroup: React.FC<{ label: string; children: React.ReactNode }> = ({
  label,
  children,
}) => (
  <div style={{ marginBottom: 16 }}>
    <div
      style={{
        fontSize: 11,
        fontWeight: 600,
        color: "#666",
        textTransform: "uppercase",
        letterSpacing: 0.5,
        marginBottom: 8,
      }}
    >
      {label}
    </div>
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {children}
    </div>
  </div>
);

const TextField: React.FC<{
  label: string;
  value: string;
  onChange: (v: string) => void;
}> = ({ label, value, onChange }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
    <label style={{ fontSize: 12, color: "#999", width: 60, flexShrink: 0 }}>
      {label}
    </label>
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        flex: 1,
        background: "#222",
        border: "1px solid #333",
        borderRadius: 4,
        color: "#e0e0e0",
        padding: "4px 8px",
        fontSize: 12,
      }}
    />
  </div>
);

const NumberField: React.FC<{
  label: string;
  value: number;
  step?: number;
  min?: number;
  max?: number;
  onChange: (v: number) => void;
}> = ({ label, value, step = 1, min, max, onChange }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
    <label style={{ fontSize: 12, color: "#999", width: 60, flexShrink: 0 }}>
      {label}
    </label>
    <input
      type="number"
      value={value}
      step={step}
      min={min}
      max={max}
      onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
      style={{
        flex: 1,
        background: "#222",
        border: "1px solid #333",
        borderRadius: 4,
        color: "#e0e0e0",
        padding: "4px 8px",
        fontSize: 12,
        width: 80,
      }}
    />
  </div>
);

const SelectField: React.FC<{
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}> = ({ label, value, options, onChange }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
    <label style={{ fontSize: 12, color: "#999", width: 60, flexShrink: 0 }}>
      {label}
    </label>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        flex: 1,
        background: "#222",
        border: "1px solid #333",
        borderRadius: 4,
        color: "#e0e0e0",
        padding: "4px 8px",
        fontSize: 12,
      }}
    >
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt.replace(/_/g, " ")}
        </option>
      ))}
    </select>
  </div>
);
