import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  Sequence,
  Audio,
  useVideoConfig,
  staticFile,
} from "remotion";
import type { EnhancementSpec, Enhancement, ZoomEffectContent } from "./lib/types";
import { secondsToFrames } from "./lib/timing";
import { EnhancementRenderer } from "./components/EnhancementRenderer";
import { ZoomEffect } from "./components/ZoomEffect";

interface Props {
  spec: EnhancementSpec;
}

export const EnhancedVideo: React.FC<Props> = ({ spec }) => {
  const { fps } = useVideoConfig();

  if (!spec) {
    return (
      <AbsoluteFill style={{ backgroundColor: "#1a1a2e", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ color: "#fff", fontSize: 48, fontFamily: "Inter, system-ui, sans-serif" }}>
          No spec loaded
        </div>
      </AbsoluteFill>
    );
  }

  const zoomEffects = spec.enhancements.filter((e) => e.type === "zoom_effect");
  const visualEnhancements = spec.enhancements.filter(
    (e) => e.type !== "zoom_effect" && e.type !== "sound_effect"
  );
  const soundEffects = spec.enhancements.filter((e) => e.type === "sound_effect");

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Layer 1: Video with zoom effects */}
      <AbsoluteFill>
        <ZoomStack zooms={zoomEffects} fps={fps}>
          {spec.source_video ? (
            <OffthreadVideo src={staticFile("source_video.mp4")} />
          ) : (
            <AbsoluteFill style={{ backgroundColor: "#1a1a2e" }} />
          )}
        </ZoomStack>
      </AbsoluteFill>

      {/* Layer 2: Visual enhancements */}
      {visualEnhancements.map((enh) => {
        const startFrame = secondsToFrames(enh.start_seconds, fps);
        const durationFrames = secondsToFrames(enh.end_seconds - enh.start_seconds, fps);
        return (
          <Sequence key={enh.id} from={startFrame} durationInFrames={durationFrames}>
            <AbsoluteFill>
              <EnhancementRenderer enhancement={enh} spec={spec} />
            </AbsoluteFill>
          </Sequence>
        );
      })}

      {/* Layer 3: Sound effects */}
      {soundEffects.map((enh) => {
        const startFrame = secondsToFrames(enh.start_seconds, fps);
        const content = enh.content as { sfx_id: string; volume?: number };
        return (
          <Sequence key={enh.id} from={startFrame}>
            <Audio
              src={staticFile(`sfx/${content.sfx_id}.mp3`)}
              volume={content.volume ?? 0.5}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

// Helper: applies nested zoom effects to the video layer
const ZoomStack: React.FC<{
  zooms: Enhancement[];
  fps: number;
  children: React.ReactNode;
}> = ({ zooms, fps, children }) => {
  if (zooms.length === 0) return <>{children}</>;

  let wrapped = children;
  for (const z of zooms) {
    const startFrame = secondsToFrames(z.start_seconds, fps);
    const durationFrames = secondsToFrames(z.end_seconds - z.start_seconds, fps);
    const content = z.content as ZoomEffectContent;
    wrapped = (
      <ZoomEffect
        content={content}
        startFrame={startFrame}
        durationFrames={durationFrames}
      >
        {wrapped}
      </ZoomEffect>
    );
  }
  return <>{wrapped}</>;
};
