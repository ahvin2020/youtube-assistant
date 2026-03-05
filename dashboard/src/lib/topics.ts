import fs from "fs/promises";
import path from "path";
import { Topic } from "./types";

const WORKSPACE_ROOT = path.resolve(process.cwd(), "..");

export async function getTopics(): Promise<{ topics: Topic[]; sheetUrl: string | null }> {
  // Find latest topics output
  const topicsDir = path.join(WORKSPACE_ROOT, "workspace", "output", "topics");
  try {
    const entries = await fs.readdir(topicsDir, { withFileTypes: true });
    const dirs = entries.filter((e) => e.isDirectory()).map((e) => e.name).sort();
    if (dirs.length === 0) return { topics: [], sheetUrl: null };

    const latestSlug = dirs[dirs.length - 1];
    const analysisPath = path.join(topicsDir, latestSlug, "topics_analysis.json");
    const content = await fs.readFile(analysisPath, "utf-8");
    const topics: Topic[] = JSON.parse(content);

    // Get sheet URL from state
    const statePath = path.join(WORKSPACE_ROOT, "workspace", "temp", "topics", latestSlug, "state.json");
    let sheetUrl: string | null = null;
    try {
      const state = JSON.parse(await fs.readFile(statePath, "utf-8"));
      sheetUrl = state.sheet_url || null;
    } catch { /* no state */ }

    return { topics, sheetUrl };
  } catch {
    return { topics: [], sheetUrl: null };
  }
}
