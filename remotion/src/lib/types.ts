// Position types
export type NamedX = "left" | "center" | "right";
export type NamedY = "top" | "center" | "bottom" | "top_third" | "bottom_third";
export interface Position {
  x: NamedX | number;
  y: NamedY | number;
}

// Animation presets
export type AnimationPreset =
  | "fade"
  | "slide_up"
  | "slide_down"
  | "slide_left"
  | "slide_right"
  | "scale_bounce"
  | "pop"
  | "bounce_in"
  | "spring_in"
  | "blur_in"
  | "rotate_in"
  | "build_up"
  | "typewriter"
  | "wipe"
  | "none";

// Easing types
export type EasingType = "ease_in" | "ease_out" | "ease_in_out" | "linear" | "spring";

// Enhancement content types
export interface TextOverlayContent {
  text: string;
  style?: "kinetic_pop" | "slide_in" | "typewriter" | "highlight" | "fade";
  position?: Position;
  font_size?: number;
  color?: string;
  animation_in?: AnimationPreset;
  animation_out?: AnimationPreset;
}

export interface LowerThirdContent {
  name: string;
  title: string;
  position?: "bottom_left" | "bottom_right" | "bottom_center";
  animation_in?: AnimationPreset;
  animation_out?: AnimationPreset;
}

export interface SourceOverlayContent {
  source_url?: string;
  screenshot_path?: string;
  headline?: string;
  highlight_regions?: Array<{ x: number; y: number; width: number; height: number }>;
  position?: Position;
  scale?: number;
  animation_in?: AnimationPreset;
  animation_out?: AnimationPreset;
}

export interface ZoomEffectContent {
  zoom_type: "push_in" | "push_out" | "pan_left" | "pan_right" | "ken_burns";
  from_scale?: number;
  to_scale?: number;
  focal_point?: Position;
  easing?: EasingType;
}

export interface SoundEffectContent {
  sfx_id: string;
  volume?: number;
}

export interface SectionDividerContent {
  label: string;
  number?: number;
  total_sections?: number;
  style?: "minimal_bar" | "full_card";
  position?: "full_width_center" | "top" | "bottom";
}

export interface DataVizContent {
  chart_type: "bar" | "comparison" | "pie" | "timeline" | "flowchart" | "table" | "gauge" | "funnel";
  title?: string;
  data: Array<{
    label: string;
    value: number;
    color?: string;
    description?: string;
    icon?: string;
  }>;
  position?: Position;
  scale?: number;
  animation_in?: AnimationPreset;
  animation_out?: AnimationPreset;
}

export interface IconAccentContent {
  icon: string;
  position?: Position;
  size?: number;
  animation?: AnimationPreset;
  color?: string;
}

export interface CalloutBoxContent {
  text: string;
  style?: "quote" | "insight" | "warning" | "tip";
  position?: Position;
  animation_in?: AnimationPreset;
  animation_out?: AnimationPreset;
}

export interface AnimatedListContent {
  items: Array<{ text: string; icon?: string }>;
  reveal_style?: "sequential" | "cascade" | "all_at_once";
  stagger_frames?: number;
  position?: Position;
  animation_in?: AnimationPreset;
  animation_out?: AnimationPreset;
}

export interface NumberCounterContent {
  from: number;
  to: number;
  prefix?: string;
  suffix?: string;
  title?: string;
  subtitle?: string;
  from_color?: string;
  to_color?: string;
  position?: Position;
  font_size?: number;
  color?: string;
  animation_in?: AnimationPreset;
  animation_out?: AnimationPreset;
}

export interface SplitScreenContent {
  left: { label: string; value: string; color?: string };
  right: { label: string; value: string; color?: string };
  divider_style?: "vs" | "line" | "arrow";
  animation_in?: AnimationPreset;
  animation_out?: AnimationPreset;
}

export interface ProgressTrackerContent {
  steps: Array<{ label: string; completed?: boolean }>;
  current_step: number;
  style?: "dots" | "bar" | "numbered" | "checkmarks";
  position?: Position;
  animation_in?: AnimationPreset;
  animation_out?: AnimationPreset;
}

export interface MapHighlightContent {
  image_path: string;
  highlights?: Array<{ x: number; y: number; width: number; height: number; label?: string; color?: string }>;
  position?: Position;
  scale?: number;
  animation_in?: AnimationPreset;
  animation_out?: AnimationPreset;
}

export interface TransitionContent {
  transition_type: "whip" | "swish" | "wipe" | "dissolve" | "zoom_through";
  direction?: "left" | "right" | "up" | "down";
  speed?: "slow" | "normal" | "fast";
}

// Enhancement type union
export type EnhancementType =
  | "text_overlay"
  | "lower_third"
  | "source_overlay"
  | "zoom_effect"
  | "sound_effect"
  | "section_divider"
  | "data_viz"
  | "icon_accent"
  | "callout_box"
  | "animated_list"
  | "number_counter"
  | "split_screen"
  | "progress_tracker"
  | "map_highlight"
  | "transition"
  | "image_overlay";

export interface ImageOverlayContent {
  image_path: string;
  position?: Position;
  width?: number;
  height?: number;
  animation_in?: AnimationPreset;
  animation_out?: AnimationPreset;
}

export type EnhancementContent =
  | TextOverlayContent
  | LowerThirdContent
  | SourceOverlayContent
  | ZoomEffectContent
  | SoundEffectContent
  | SectionDividerContent
  | DataVizContent
  | IconAccentContent
  | CalloutBoxContent
  | AnimatedListContent
  | NumberCounterContent
  | SplitScreenContent
  | ProgressTrackerContent
  | MapHighlightContent
  | TransitionContent
  | ImageOverlayContent;

// Enhancement entry
export interface Enhancement {
  id: string;
  type: EnhancementType;
  section_id: string;
  start_seconds: number;
  end_seconds: number;
  content: EnhancementContent;
}

// Section
export interface Section {
  id: string;
  label: string;
  start_seconds: number;
  end_seconds: number;
  script_text?: string;
}

// Global style
export interface GlobalStyle {
  font_family?: string;
  accent_color?: string;
  secondary_color?: string;
  text_color?: string;
  background_opacity?: number;
}

// Top-level spec
export interface EnhancementSpec {
  version: string;
  source_video: string;
  fps: number;
  duration_seconds: number;
  width: number;
  height: number;
  global_style: GlobalStyle;
  sections: Section[];
  enhancements: Enhancement[];
}
