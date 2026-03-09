import React from "react";
import { PreviewPlayer } from "./PreviewPlayer";
import { EnhancementList } from "./EnhancementList";
import { PropertyPanel } from "./PropertyPanel";
import { Timeline } from "./Timeline";
import { useSpec } from "./SpecProvider";

export const App: React.FC = () => {
  const { selectedId } = useSpec();

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "280px 1fr 300px",
        gridTemplateRows: "1fr 200px",
        height: "100vh",
        gap: 1,
        backgroundColor: "#1a1a2e",
      }}
    >
      {/* Left sidebar */}
      <div style={{ gridRow: "1 / 2", overflow: "auto", backgroundColor: "#12121e", borderRight: "1px solid #2a2a3e" }}>
        <EnhancementList />
      </div>

      {/* Center player */}
      <div style={{ gridRow: "1 / 2", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
        <PreviewPlayer />
      </div>

      {/* Right sidebar */}
      <div style={{ gridRow: "1 / 2", overflow: "auto", backgroundColor: "#12121e", borderLeft: "1px solid #2a2a3e" }}>
        {selectedId ? <PropertyPanel /> : (
          <div style={{ padding: 20, color: "#666", textAlign: "center", marginTop: 40 }}>
            Select an enhancement to edit its properties
          </div>
        )}
      </div>

      {/* Bottom timeline */}
      <div style={{ gridColumn: "1 / -1", backgroundColor: "#0d0d18", borderTop: "1px solid #2a2a3e", overflow: "auto" }}>
        <Timeline />
      </div>
    </div>
  );
};
