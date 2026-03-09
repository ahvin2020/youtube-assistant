import React from "react";
import { useVideoConfig } from "remotion";
import type { Enhancement, EnhancementSpec } from "../lib/types";
import { secondsToFrames } from "../lib/timing";
import { TextOverlay } from "./TextOverlay";
import { LowerThird } from "./LowerThird";
import { SourceOverlay } from "./SourceOverlay";
import { SectionDivider } from "./SectionDivider";
import { DataVisualization } from "./DataVisualization";
import { IconAccent } from "./IconAccent";
import { CalloutBox } from "./CalloutBox";
import { AnimatedList } from "./AnimatedList";
import { NumberCounter } from "./NumberCounter";
import { SplitScreen } from "./SplitScreen";
import { ProgressTracker } from "./ProgressTracker";
import { MapHighlight } from "./MapHighlight";
import { TransitionEffect } from "./TransitionEffect";
import { ImageOverlay } from "./ImageOverlay";

interface Props {
  enhancement: Enhancement;
  spec: EnhancementSpec;
}

export const EnhancementRenderer: React.FC<Props> = ({ enhancement, spec }) => {
  const { fps } = useVideoConfig();
  const durationFrames = secondsToFrames(
    enhancement.end_seconds - enhancement.start_seconds,
    fps
  );

  const content = enhancement.content as any;

  switch (enhancement.type) {
    case "text_overlay":
      return <TextOverlay content={content} spec={spec} durationFrames={durationFrames} />;
    case "lower_third":
      return <LowerThird content={content} spec={spec} durationFrames={durationFrames} />;
    case "source_overlay":
      return <SourceOverlay content={content} spec={spec} durationFrames={durationFrames} />;
    case "section_divider":
      return <SectionDivider content={content} spec={spec} durationFrames={durationFrames} />;
    case "data_viz":
      return <DataVisualization content={content} spec={spec} durationFrames={durationFrames} />;
    case "icon_accent":
      return <IconAccent content={content} spec={spec} durationFrames={durationFrames} />;
    case "callout_box":
      return <CalloutBox content={content} spec={spec} durationFrames={durationFrames} />;
    case "animated_list":
      return <AnimatedList content={content} spec={spec} durationFrames={durationFrames} />;
    case "number_counter":
      return <NumberCounter content={content} spec={spec} durationFrames={durationFrames} />;
    case "split_screen":
      return <SplitScreen content={content} spec={spec} durationFrames={durationFrames} />;
    case "progress_tracker":
      return <ProgressTracker content={content} spec={spec} durationFrames={durationFrames} />;
    case "map_highlight":
      return <MapHighlight content={content} spec={spec} durationFrames={durationFrames} />;
    case "transition":
      return <TransitionEffect content={content} durationFrames={durationFrames} />;
    case "image_overlay":
      return <ImageOverlay content={content} spec={spec} durationFrames={durationFrames} />;
    default:
      return null;
  }
};
