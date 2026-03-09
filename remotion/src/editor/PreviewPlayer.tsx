import React, { useState, useCallback } from "react";
import { Player } from "@remotion/player";
import { EnhancedVideo } from "../EnhancedVideo";
import { useSpec } from "./SpecProvider";

export const PreviewPlayer: React.FC = () => {
  const { spec } = useSpec();
  const [playing, setPlaying] = useState(false);

  const durationInFrames = Math.ceil(spec.duration_seconds * spec.fps);

  const togglePlay = useCallback(() => setPlaying((p) => !p), []);

  return (
    <div style={{ width: "100%", maxWidth: 960 }}>
      <div style={{ position: "relative", borderRadius: 8, overflow: "hidden", boxShadow: "0 4px 24px rgba(0,0,0,0.5)" }}>
        <Player
          component={EnhancedVideo}
          inputProps={{ spec }}
          durationInFrames={durationInFrames}
          fps={spec.fps}
          compositionWidth={spec.width}
          compositionHeight={spec.height}
          style={{ width: "100%" }}
          autoPlay={playing}
          controls
        />
      </div>
      <div style={{ marginTop: 12, display: "flex", justifyContent: "space-between", alignItems: "center", color: "#999", fontSize: 13 }}>
        <span>{spec.width}x{spec.height} @ {spec.fps}fps</span>
        <span>{spec.enhancements.length} enhancements</span>
        <span>{Math.round(spec.duration_seconds)}s duration</span>
      </div>
    </div>
  );
};
