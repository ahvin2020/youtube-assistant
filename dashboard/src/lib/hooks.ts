import fs from "fs/promises";
import path from "path";
import { Hook } from "./types";

const WORKSPACE_ROOT = path.resolve(process.cwd(), "..");

interface HooksFile {
  hooks: Hook[];
  analyzed_videos: string[];
  last_updated: string;
  max_hooks: number;
}

export async function getHooks(filters?: {
  category?: string;
  format?: string;
  search?: string;
  minOutlier?: number;
}): Promise<{ hooks: Hook[]; total: number; analyzedVideos: number; lastUpdated: string }> {
  const hooksPath = path.join(WORKSPACE_ROOT, "workspace", "config", "hooks.json");
  try {
    const content = await fs.readFile(hooksPath, "utf-8");
    const data: HooksFile = JSON.parse(content);
    let hooks = data.hooks || [];

    if (filters?.category) {
      hooks = hooks.filter((h) => h.category === filters.category);
    }
    if (filters?.format) {
      hooks = hooks.filter((h) => h.format === filters.format);
    }
    if (filters?.search) {
      const q = filters.search.toLowerCase();
      hooks = hooks.filter(
        (h) =>
          h.text.toLowerCase().includes(q) ||
          h.source_channel.toLowerCase().includes(q)
      );
    }
    if (filters?.minOutlier) {
      hooks = hooks.filter((h) => h.outlier_score >= filters.minOutlier!);
    }

    // Sort by performance score descending
    hooks.sort((a, b) => b.performance_score - a.performance_score);

    return {
      hooks,
      total: data.hooks?.length || 0,
      analyzedVideos: data.analyzed_videos?.length || 0,
      lastUpdated: data.last_updated || "",
    };
  } catch {
    return { hooks: [], total: 0, analyzedVideos: 0, lastUpdated: "" };
  }
}
