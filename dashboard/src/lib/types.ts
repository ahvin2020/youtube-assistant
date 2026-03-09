// === Domain types ===
export type Domain = "research" | "thumbnail" | "ideas" | "analyze" | "video";

export const DOMAIN_PHASES: Record<Domain, string[]> = {
  research: ["research", "outline", "script", "complete"],
  thumbnail: ["research", "concepts", "generate", "edit", "complete"],
  ideas: ["gathering", "analysis", "complete"],
  analyze: ["scanning", "analysis", "complete"],
  video: ["cut", "graphics", "complete"],
};

export const DOMAIN_COLORS: Record<Domain, string> = {
  research: "indigo",
  thumbnail: "pink",
  ideas: "emerald",
  analyze: "amber",
  video: "sky",
};

export const DOMAIN_ICONS: Record<Domain, string> = {
  research: "\u{1F4DD}",
  thumbnail: "\u{1F3A8}",
  ideas: "\u{1F4A1}",
  analyze: "\u{1F4CA}",
  video: "\u{1F3AC}",
};

// === State types ===
export interface BaseState {
  phase: string;
  created: string;
  updated?: string;
  slug?: string;
  topic?: string;
  project?: string;
  sheet_url?: string;
  [key: string]: unknown;
}

// === Project (aggregated) ===
export interface Project {
  domain: Domain;
  slug: string;
  displayName: string;
  state: BaseState | null;
  currentPhase: string;
  totalPhases: number;
  phaseIndex: number;
  hasOutput: boolean;
  outputFiles: string[];
  sheetUrl: string | null;
  created: string;
  updated: string;
}

// === Pipeline definitions ===
export interface Pipeline {
  id: string;
  role: string;
  domain: Domain;
  command: string;
  description: string;
  icon: string;
  color: string;
}

export const PIPELINES: Pipeline[] = [
  { id: "ideas", role: "Idea Finder", domain: "ideas", command: "/idea", description: "Discover trending content opportunities", icon: "\u{1F4A1}", color: "emerald" },
  { id: "write", role: "Scriptwriter", domain: "research", command: "/write", description: "Research and write video scripts", icon: "\u{1F4DD}", color: "indigo" },
  { id: "thumbnail", role: "Thumbnail Designer", domain: "thumbnail", command: "/thumbnail", description: "Design high-CTR thumbnails", icon: "\u{1F3A8}", color: "pink" },
  { id: "edit", role: "Video Editor", domain: "video", command: "/edit", description: "Cut retakes and add motion graphics", icon: "\u{1F3AC}", color: "sky" },
  { id: "analyze", role: "Content Analyst", domain: "analyze", command: "/analyze", description: "Analyze channel performance", icon: "\u{1F4CA}", color: "amber" },
];

export const ROLE_TITLES: Record<string, string> = {
  research: "Scriptwriter",
  thumbnail: "Thumbnail Designer",
  ideas: "Idea Finder",
  analyze: "Content Analyst",
  video: "Video Editor",
};

// === Next Action ===
export interface NextAction {
  label: string;
  command: string;
  description: string;
  domain: Domain;
  icon: string;
  priority: "primary" | "secondary";
}

// === Hook ===
export interface Hook {
  text: string;
  category: string;
  format: string;
  opening_seconds: number | null;
  source_video_id: string;
  source_channel: string;
  views: number;
  outlier_score: number;
  performance_score: number;
  id: string;
}

// === Topic ===
export interface Topic {
  topic: string;
  lf_score: number;
  shorts_score: number;
  format_rec: string;
  trend: string;
  sources: string;
  evidence: string;
  gap_status: string;
  why_it_works: string;
  suggested_angle: string;
  hook_ideas: string;
  research_more: string;
}

// === Content project (cross-pipeline grouping) ===
export interface ContentProject {
  contentSlug: string;
  displayName: string;
  stages: Partial<Record<Domain, Project>>;
  lastUpdated: string;
}

// === Dashboard overview ===
export interface DashboardData {
  projects: Project[];
  contentProjects: ContentProject[];
  activeCount: number;
  hooksCount: number;
  ideasCount: number;
  videosAnalyzed: number;
}
