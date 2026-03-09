import fs from "fs/promises";
import path from "path";
import CutWizard from "./CutWizard";

export const dynamic = "force-dynamic";

const WORKSPACE_ROOT = path.resolve(process.cwd(), "..");

async function getCutProjects() {
  const tempDir = path.join(WORKSPACE_ROOT, "workspace", "temp", "video");
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

async function getVideoFiles() {
  const inputDir = path.join(WORKSPACE_ROOT, "workspace", "input", "video");
  try {
    const entries = await fs.readdir(inputDir, { withFileTypes: true });
    const dirs = entries.filter((e) => e.isDirectory()).map((e) => e.name);
    const result = [];
    for (const dir of dirs) {
      try {
        const files = await fs.readdir(path.join(inputDir, dir));
        const videoFiles = files.filter((f) =>
          /\.(mov|mp4|avi|mkv|webm|m4v)$/i.test(f)
        );
        if (videoFiles.length > 0) {
          result.push({ dir, files: videoFiles });
        }
      } catch { /* skip */ }
    }
    return result;
  } catch {
    return [];
  }
}

export default async function CutPage() {
  const [projects, videoFiles] = await Promise.all([
    getCutProjects(),
    getVideoFiles(),
  ]);

  return <CutWizard projects={projects} videoFiles={videoFiles} />;
}
