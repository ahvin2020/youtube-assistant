// === Domain types ===
export type Domain = "research" | "thumbnail" | "topics" | "analyze" | "video";

export const DOMAIN_PHASES: Record<Domain, string[]> = {
  research: ["research", "outline", "script", "complete"],
  thumbnail: ["research", "concepts", "generate", "edit", "complete"],
  topics: ["gathering", "analysis", "complete"],
  analyze: ["scanning", "analysis", "complete"],
  video: ["transcribe", "align", "cut", "complete"],
};

export const DOMAIN_COLORS: Record<Domain, string> = {
  research: "indigo",
  thumbnail: "pink",
  topics: "emerald",
  analyze: "amber",
  video: "sky",
};

export const DOMAIN_ICONS: Record<Domain, string> = {
  research: "\u{1F4DD}",
  thumbnail: "\u{1F3A8}",
  topics: "\u{1F4A1}",
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

// === Employee ===
export type EmployeeStatus = "busy" | "idle";

export interface Employee {
  id: string;
  name: string;
  title: string;
  avatar: string;
  domains: Domain[];
  personality: string;
  skills: string[];
  color: string;
  status: EmployeeStatus;
  currentAssignment: string | null;
  projectsCompleted: number;
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

// === Dashboard overview ===
export interface DashboardData {
  projects: Project[];
  activeCount: number;
  hooksCount: number;
  topicsCount: number;
  videosAnalyzed: number;
}
