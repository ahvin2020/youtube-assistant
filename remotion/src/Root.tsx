import React from "react";
import { Composition, getInputProps } from "remotion";
import { EnhancedVideo } from "./EnhancedVideo";
import type { EnhancementSpec } from "./lib/types";

// Load spec from Remotion input props (passed via --props flag or Studio props editor)
const inputProps = getInputProps() as { spec?: EnhancementSpec } | null;

// Also try loading from env var at build time (Vite exposes import.meta.env)
let envSpec: EnhancementSpec | undefined;
try {
  const specPath = (import.meta as any).env?.VITE_ENHANCE_SPEC;
  if (specPath) {
    // In Node/SSR context during rendering, we can read the file
    // But in browser context, we need to fetch it
    envSpec = undefined; // Will be loaded via props instead
  }
} catch {}

const defaultSpec = inputProps?.spec ?? envSpec ?? undefined;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="EnhancedVideo"
      component={EnhancedVideo as any}
      durationInFrames={300}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{ spec: defaultSpec as unknown as EnhancementSpec }}
      calculateMetadata={({ props }: { props: Record<string, any> }) => {
        const spec = props.spec as EnhancementSpec | undefined;
        if (!spec) return {};
        return {
          durationInFrames: Math.ceil(spec.duration_seconds * spec.fps),
          fps: spec.fps,
          width: spec.width,
          height: spec.height,
        };
      }}
    />
  );
};
