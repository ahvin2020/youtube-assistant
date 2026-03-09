import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import type { DataVizContent, EnhancementSpec } from "../lib/types";
import { positionStyle } from "../lib/positions";
import { getAnimationStyle } from "../lib/animations";

interface Props {
  content: DataVizContent;
  spec: EnhancementSpec;
  durationFrames: number;
}

export const DataVisualization: React.FC<Props> = ({ content, spec, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const animStyle = getAnimationStyle(
    content.animation_in ?? "build_up",
    content.animation_out ?? "fade",
    frame,
    fps,
    durationFrames
  );

  const pos = positionStyle(content.position);
  const scale = content.scale ?? 1;
  const fontFamily = spec.global_style.font_family ?? "Inter, system-ui, sans-serif";
  const accentColor = spec.global_style.accent_color ?? "#FF6B35";

  const ChartComponent = CHART_MAP[content.chart_type] ?? BarChart;

  return (
    <div style={{ ...pos, ...animStyle, transform: `translate(-50%, -50%) scale(${scale})`, fontFamily }}>
      <div
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.8)",
          backdropFilter: "blur(12px)",
          borderRadius: 12,
          padding: 28,
          minWidth: 400,
        }}
      >
        {content.title && (
          <div style={{ color: "#FFFFFF", fontSize: 22, fontWeight: 700, marginBottom: 20, textAlign: "center" }}>
            {content.title}
          </div>
        )}
        <ChartComponent data={content.data} frame={frame} fps={fps} accentColor={accentColor} />
      </div>
    </div>
  );
};

type DataItem = DataVizContent["data"][number];
interface ChartProps {
  data: DataItem[];
  frame: number;
  fps: number;
  accentColor: string;
}

const BarChart: React.FC<ChartProps> = ({ data, frame, fps }) => {
  const maxVal = Math.max(...data.map((d) => d.value), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {data.map((item, i) => {
        const barProgress = spring({
          frame: Math.max(frame - i * 8, 0),
          fps,
          config: { damping: 15, stiffness: 80 },
        });
        const width = (item.value / maxVal) * 300 * barProgress;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 80, textAlign: "right", color: "#ccc", fontSize: 14, fontWeight: 500 }}>
              {item.label}
            </div>
            <div style={{ flex: 1, height: 28, backgroundColor: "rgba(255,255,255,0.1)", borderRadius: 4, overflow: "hidden" }}>
              <div
                style={{
                  width,
                  height: "100%",
                  backgroundColor: item.color ?? "#FF6B35",
                  borderRadius: 4,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "flex-end",
                  paddingRight: 8,
                }}
              >
                <span style={{ color: "#fff", fontSize: 12, fontWeight: 600 }}>
                  {Math.round(item.value * barProgress)}
                  {item.description ?? ""}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

const ComparisonChart: React.FC<ChartProps> = ({ data, frame, fps }) => (
  <div style={{ display: "flex", justifyContent: "center", gap: 40 }}>
    {data.map((item, i) => {
      const enter = spring({
        frame: Math.max(frame - i * 10, 0),
        fps,
        config: { damping: 12, stiffness: 100 },
      });
      return (
        <div key={i} style={{ textAlign: "center", opacity: enter, transform: `scale(${interpolate(enter, [0, 1], [0.8, 1])})` }}>
          <div style={{ fontSize: 48, fontWeight: 800, color: item.color ?? "#FF6B35" }}>
            {item.value}{item.description ?? ""}
          </div>
          <div style={{ fontSize: 18, color: "#ccc", marginTop: 8 }}>{item.label}</div>
        </div>
      );
    })}
  </div>
);

const PieChart: React.FC<ChartProps> = ({ data, frame, fps }) => {
  const total = data.reduce((s, d) => s + d.value, 0);
  const drawProgress = spring({ frame, fps, config: { damping: 20, stiffness: 60 } });
  let cumAngle = 0;
  const size = 200;
  const cx = size / 2;
  const cy = size / 2;
  const r = 80;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 30 }}>
      <svg width={size} height={size}>
        {data.map((item, i) => {
          const angle = (item.value / total) * 360 * drawProgress;
          const startAngle = cumAngle;
          cumAngle += angle;
          const endAngle = cumAngle;
          const start = polarToCartesian(cx, cy, r, startAngle);
          const end = polarToCartesian(cx, cy, r, endAngle);
          const largeArc = angle > 180 ? 1 : 0;
          const d = `M ${cx} ${cy} L ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y} Z`;
          return <path key={i} d={d} fill={item.color ?? `hsl(${i * 60}, 70%, 50%)`} />;
        })}
      </svg>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {data.map((item, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 12, height: 12, borderRadius: 2, backgroundColor: item.color ?? `hsl(${i * 60}, 70%, 50%)` }} />
            <span style={{ color: "#ccc", fontSize: 14 }}>{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

const GaugeChart: React.FC<ChartProps> = ({ data, frame, fps, accentColor }) => {
  const item = data[0];
  if (!item) return null;
  const maxVal = data[1]?.value ?? 100;
  const progress = spring({ frame, fps, config: { damping: 20, stiffness: 60 } });
  const angle = (item.value / maxVal) * 180 * progress;

  return (
    <div style={{ textAlign: "center" }}>
      <svg width={220} height={130} viewBox="0 0 220 130">
        <path d="M 20 120 A 90 90 0 0 1 200 120" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth={16} strokeLinecap="round" />
        <path
          d="M 20 120 A 90 90 0 0 1 200 120"
          fill="none"
          stroke={item.color ?? accentColor}
          strokeWidth={16}
          strokeLinecap="round"
          strokeDasharray={`${(angle / 180) * 283} 283`}
        />
      </svg>
      <div style={{ fontSize: 36, fontWeight: 800, color: item.color ?? accentColor, marginTop: -20 }}>
        {Math.round(item.value * progress)}{item.description ?? ""}
      </div>
      <div style={{ fontSize: 14, color: "#ccc", marginTop: 4 }}>{item.label}</div>
    </div>
  );
};

const TimelineChart: React.FC<ChartProps> = ({ data, frame, fps }) => (
  <div style={{ display: "flex", alignItems: "flex-start", gap: 0, position: "relative", padding: "20px 0" }}>
    <div style={{ position: "absolute", top: 30, left: 20, right: 20, height: 3, backgroundColor: "rgba(255,255,255,0.2)" }} />
    {data.map((item, i) => {
      const enter = spring({ frame: Math.max(frame - i * 12, 0), fps, config: { damping: 12 } });
      return (
        <div key={i} style={{ flex: 1, textAlign: "center", opacity: enter, transform: `translateY(${interpolate(enter, [0, 1], [20, 0])}px)` }}>
          <div style={{ width: 12, height: 12, borderRadius: "50%", backgroundColor: item.color ?? "#FF6B35", margin: "0 auto 8px" }} />
          <div style={{ fontSize: 13, color: "#ccc", fontWeight: 500 }}>{item.label}</div>
          {item.description && <div style={{ fontSize: 11, color: "#999", marginTop: 2 }}>{item.description}</div>}
        </div>
      );
    })}
  </div>
);

const TableChart: React.FC<ChartProps> = ({ data, frame, fps }) => (
  <div>
    {data.map((item, i) => {
      const enter = spring({ frame: Math.max(frame - i * 6, 0), fps, config: { damping: 12 } });
      return (
        <div
          key={i}
          style={{
            display: "flex",
            justifyContent: "space-between",
            padding: "10px 16px",
            backgroundColor: i % 2 === 0 ? "rgba(255,255,255,0.05)" : "transparent",
            borderRadius: 4,
            opacity: enter,
          }}
        >
          <span style={{ color: "#ccc", fontSize: 16 }}>{item.label}</span>
          <span style={{ color: item.color ?? "#FFFFFF", fontSize: 16, fontWeight: 700 }}>
            {item.value}{item.description ?? ""}
          </span>
        </div>
      );
    })}
  </div>
);

const FunnelChart: React.FC<ChartProps> = ({ data, frame, fps }) => {
  const maxVal = Math.max(...data.map((d) => d.value), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      {data.map((item, i) => {
        const enter = spring({ frame: Math.max(frame - i * 10, 0), fps, config: { damping: 15 } });
        const width = (item.value / maxVal) * 350 * enter;
        return (
          <div
            key={i}
            style={{
              width,
              padding: "10px 16px",
              backgroundColor: item.color ?? `hsl(${200 + i * 30}, 60%, 50%)`,
              borderRadius: 4,
              textAlign: "center",
              opacity: enter,
            }}
          >
            <span style={{ color: "#fff", fontSize: 14, fontWeight: 600 }}>{item.label} ({item.value})</span>
          </div>
        );
      })}
    </div>
  );
};

const FlowChart: React.FC<ChartProps> = ({ data, frame, fps, accentColor }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
    {data.map((item, i) => {
      const enter = spring({ frame: Math.max(frame - i * 12, 0), fps, config: { damping: 12 } });
      return (
        <React.Fragment key={i}>
          <div
            style={{
              backgroundColor: item.color ?? "rgba(255,255,255,0.1)",
              border: `2px solid ${item.color ?? accentColor}`,
              borderRadius: 8,
              padding: "12px 16px",
              opacity: enter,
              transform: `scale(${interpolate(enter, [0, 1], [0.8, 1])})`,
              textAlign: "center",
            }}
          >
            {item.icon && <div style={{ fontSize: 20, marginBottom: 4 }}>{item.icon}</div>}
            <div style={{ color: "#fff", fontSize: 13, fontWeight: 600 }}>{item.label}</div>
          </div>
          {i < data.length - 1 && (
            <div style={{ color: accentColor, fontSize: 20, opacity: enter }}>→</div>
          )}
        </React.Fragment>
      );
    })}
  </div>
);

const CHART_MAP: Record<string, React.FC<ChartProps>> = {
  bar: BarChart,
  comparison: ComparisonChart,
  pie: PieChart,
  gauge: GaugeChart,
  timeline: TimelineChart,
  table: TableChart,
  funnel: FunnelChart,
  flowchart: FlowChart,
};
