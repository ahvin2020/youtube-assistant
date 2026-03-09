import fs from "fs/promises";
import path from "path";
import EnhanceWizard from "./EnhanceWizard";

export const dynamic = "force-dynamic";

const WORKSPACE_ROOT = path.resolve(process.cwd(), "..");

async function getEnhanceProjects() {
  const tempDir = path.join(WORKSPACE_ROOT, "workspace", "temp", "enhance");
  try {
    const entries = await fs.readdir(tempDir, { withFileTypes: true });
    const dirs = entries.filter((e) => e.isDirectory()).map((e) => e.name).sort().reverse();
    const projects = [];
    for (const slug of dirs.slice(0, 10)) {
      try {
        const state = JSON.parse(
          await fs.readFile(path.join(tempDir, slug, "state.json"), "utf-8")
        );
        projects.push({ slug, ...state });
      } catch {
        projects.push({ slug, phase: "unknown" });
      }
    }
    return projects;
  } catch {
    return [];
  }
}

async function getCutOutputs() {
  const outputDir = path.join(WORKSPACE_ROOT, "workspace", "output", "video");
  try {
    const entries = await fs.readdir(outputDir, { withFileTypes: true });
    const dirs = entries.filter((e) => e.isDirectory()).map((e) => e.name);
    const results = [];
    for (const dir of dirs) {
      try {
        const files = await fs.readdir(path.join(outputDir, dir));
        const trimmed = files.filter((f) => /trimmed\.(mov|mp4|avi|mkv|webm|m4v)$/i.test(f));
        for (const file of trimmed) {
          results.push({ slug: dir, file: `workspace/output/video/${dir}/${file}` });
        }
      } catch { /* skip */ }
    }
    return results;
  } catch {
    return [];
  }
}

export default async function EnhancePage() {
  const [projects, cutOutputs] = await Promise.all([
    getEnhanceProjects(),
    getCutOutputs(),
  ]);

  return <EnhanceWizard projects={projects} cutOutputs={cutOutputs} />;
}
