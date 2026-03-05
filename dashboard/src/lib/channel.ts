import fs from "fs/promises";
import path from "path";

const WORKSPACE_ROOT = path.resolve(process.cwd(), "..");

export interface ChannelProfile {
  identity: Record<string, string>;
  nicheTermsCount: number;
  crossNicheKeywordsCount: number;
  monitoredChannelsCount: number;
  discoveryKeywordsCount: number;
  subreddits: string[];
  performanceBaseline: Record<string, string>;
}

export async function getChannelProfile(): Promise<ChannelProfile | null> {
  const profilePath = path.join(WORKSPACE_ROOT, "memory", "channel-profile.md");
  try {
    const content = await fs.readFile(profilePath, "utf-8");
    const lines = content.split("\n");

    const profile: ChannelProfile = {
      identity: {},
      nicheTermsCount: 0,
      crossNicheKeywordsCount: 0,
      monitoredChannelsCount: 0,
      discoveryKeywordsCount: 0,
      subreddits: [],
      performanceBaseline: {},
    };

    let currentSection = "";
    for (const line of lines) {
      if (line.startsWith("## ")) {
        currentSection = line.replace("## ", "").trim();
        continue;
      }

      if (currentSection === "Identity" && line.startsWith("- ")) {
        const [key, ...rest] = line.slice(2).split(":");
        if (key && rest.length) {
          profile.identity[key.trim()] = rest.join(":").trim();
        }
      }

      if (currentSection === "Niche Terms" && line.trim()) {
        profile.nicheTermsCount += line.split(",").length;
      }

      if (currentSection === "Cross-Niche Keywords" && line.trim() && !line.startsWith("#")) {
        profile.crossNicheKeywordsCount += line.split(",").length;
      }

      if (currentSection === "Monitored Channels" && line.startsWith("- ")) {
        profile.monitoredChannelsCount++;
      }

      if (currentSection === "Discovery Keywords" && line.trim() && !line.startsWith("#")) {
        profile.discoveryKeywordsCount += line.split(",").length;
      }

      if (currentSection === "Community Sources" && line.includes("r/")) {
        const matches = line.match(/r\/\w+/g);
        if (matches) profile.subreddits.push(...matches);
      }

      if (currentSection === "Performance Baseline" && line.startsWith("- ")) {
        const [key, ...rest] = line.slice(2).split(":");
        if (key && rest.length) {
          profile.performanceBaseline[key.trim()] = rest.join(":").trim();
        }
      }
    }

    return profile;
  } catch {
    return null;
  }
}

export async function getResearchConfig(): Promise<Record<string, unknown> | null> {
  const configPath = path.join(WORKSPACE_ROOT, "workspace", "config", "research_config.json");
  try {
    const content = await fs.readFile(configPath, "utf-8");
    return JSON.parse(content);
  } catch {
    return null;
  }
}

export async function getSheetLinks(): Promise<Array<{ name: string; url: string }>> {
  const configDir = path.join(WORKSPACE_ROOT, "workspace", "config");
  const sheetFiles = [
    { file: "research_sheet.json", name: "Research Sheet" },
    { file: "intelligence_sheet.json", name: "Intelligence Sheet" },
    { file: "analysis_sheet.json", name: "Analysis Sheet" },
  ];

  const links: Array<{ name: string; url: string }> = [];
  for (const { file, name } of sheetFiles) {
    try {
      const content = await fs.readFile(path.join(configDir, file), "utf-8");
      const data = JSON.parse(content);
      if (data.sheet_url) links.push({ name, url: data.sheet_url });
    } catch { /* skip */ }
  }
  return links;
}
