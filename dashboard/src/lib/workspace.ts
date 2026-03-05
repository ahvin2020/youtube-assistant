import fs from "fs/promises";
import path from "path";
import { Domain, DOMAIN_PHASES, Project, BaseState, DashboardData } from "./types";

// Workspace root is the parent of the dashboard/ directory
const WORKSPACE_ROOT = path.resolve(process.cwd(), "..");

const DOMAINS: Domain[] = ["research", "thumbnail", "topics", "analyze", "video"];

function slugToDisplayName(slug: string): string {
  // Remove date prefix (YYYYMMDD_) and humanize
  const name = slug.replace(/^\d{8}_/, "");
  return name
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

async function dirExists(p: string): Promise<boolean> {
  try {
    const stat = await fs.stat(p);
    return stat.isDirectory();
  } catch {
    return false;
  }
}

async function fileExists(p: string): Promise<boolean> {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

async function readJson<T>(p: string): Promise<T | null> {
  try {
    const content = await fs.readFile(p, "utf-8");
    return JSON.parse(content) as T;
  } catch {
    return null;
  }
}

async function listDirs(p: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(p, { withFileTypes: true });
    return entries.filter((e) => e.isDirectory()).map((e) => e.name);
  } catch {
    return [];
  }
}

async function listFiles(p: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(p, { withFileTypes: true });
    return entries.filter((e) => e.isFile()).map((e) => e.name);
  } catch {
    return [];
  }
}

export async function getAllProjects(): Promise<Project[]> {
  const projects: Project[] = [];

  for (const domain of DOMAINS) {
    const tempDir = path.join(WORKSPACE_ROOT, "workspace", "temp", domain);
    const outputDir = path.join(WORKSPACE_ROOT, "workspace", "output", domain);

    // Collect all project slugs from both temp and output
    const tempSlugs = await listDirs(tempDir);
    const outputSlugs = await listDirs(outputDir);
    const allSlugs = [...new Set([...tempSlugs, ...outputSlugs])];

    for (const slug of allSlugs) {
      const statePath = path.join(tempDir, slug, "state.json");
      const state = await readJson<BaseState>(statePath);
      const hasOutput = await dirExists(path.join(outputDir, slug));
      const outputFiles = hasOutput
        ? await listFiles(path.join(outputDir, slug))
        : [];

      const phases = DOMAIN_PHASES[domain];
      const currentPhase = state?.phase || "unknown";
      const phaseIndex = phases.indexOf(currentPhase);

      // Get sheet URL from state or config
      let sheetUrl = (state?.sheet_url as string) || null;
      if (!sheetUrl) {
        // Check domain-specific sheet configs
        const configNames: Record<string, string> = {
          thumbnail: "research_sheet.json",
          topics: "intelligence_sheet.json",
          analyze: "analysis_sheet.json",
        };
        const configName = configNames[domain];
        if (configName) {
          const config = await readJson<{ sheet_url?: string }>(
            path.join(WORKSPACE_ROOT, "workspace", "config", configName)
          );
          if (config?.sheet_url) sheetUrl = config.sheet_url;
        }
      }

      const displayName =
        (state?.topic as string) || slugToDisplayName(slug);

      projects.push({
        domain,
        slug,
        displayName,
        state,
        currentPhase,
        totalPhases: phases.length,
        phaseIndex: phaseIndex >= 0 ? phaseIndex : 0,
        hasOutput,
        outputFiles,
        sheetUrl,
        created: (state?.created as string) || slug.slice(0, 8),
        updated: (state?.updated as string) || (state?.created as string) || slug.slice(0, 8),
      });
    }
  }

  // Sort by updated date descending
  projects.sort((a, b) => b.updated.localeCompare(a.updated));
  return projects;
}

export async function getDashboardData(): Promise<DashboardData> {
  const projects = await getAllProjects();
  const activeCount = projects.filter(
    (p) => p.state?.phase && p.state.phase !== "complete"
  ).length;

  // Hooks count
  const hooksPath = path.join(WORKSPACE_ROOT, "workspace", "config", "hooks.json");
  const hooksData = await readJson<{ hooks?: unknown[] }>(hooksPath);
  const hooksCount = hooksData?.hooks?.length || 0;

  // Topics count — find latest topics analysis
  const topicsOutputDir = path.join(WORKSPACE_ROOT, "workspace", "output", "topics");
  const topicsSlugs = await listDirs(topicsOutputDir);
  let topicsCount = 0;
  if (topicsSlugs.length > 0) {
    const latestSlug = topicsSlugs.sort().pop()!;
    const analysisPath = path.join(topicsOutputDir, latestSlug, "topics_analysis.json");
    const analysis = await readJson<unknown[]>(analysisPath);
    topicsCount = analysis?.length || 0;
  }

  // Videos analyzed
  const analyzeDir = path.join(WORKSPACE_ROOT, "workspace", "temp", "analyze");
  const analyzeSlugs = await listDirs(analyzeDir);
  let videosAnalyzed = 0;
  for (const slug of analyzeSlugs) {
    const state = await readJson<{ videos_analyzed?: number }>(
      path.join(analyzeDir, slug, "state.json")
    );
    if (state?.videos_analyzed) videosAnalyzed += state.videos_analyzed;
  }

  return { projects, activeCount, hooksCount, topicsCount, videosAnalyzed };
}

export async function getProjectDetail(domain: Domain, slug: string) {
  const tempDir = path.join(WORKSPACE_ROOT, "workspace", "temp", domain, slug);
  const outputDir = path.join(WORKSPACE_ROOT, "workspace", "output", domain, slug);

  const state = await readJson<BaseState>(path.join(tempDir, "state.json"));
  const tempFiles = await listFiles(tempDir);
  const outputFiles = await listFiles(outputDir);
  const hasOutput = await dirExists(outputDir);

  return { domain, slug, state, tempFiles, outputFiles, hasOutput };
}

export { WORKSPACE_ROOT };
