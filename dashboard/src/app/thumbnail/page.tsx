import fs from "fs/promises";
import path from "path";
import ThumbnailWizard from "./ThumbnailWizard";

export const dynamic = "force-dynamic";

const WORKSPACE_ROOT = path.resolve(process.cwd(), "..");

async function getThumbnailProjects() {
  const tempDir = path.join(WORKSPACE_ROOT, "workspace", "temp", "thumbnail");
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

async function getHeadshots() {
  const headshotsDir = path.join(WORKSPACE_ROOT, "workspace", "input", "thumbnail", "headshots");
  try {
    const entries = await fs.readdir(headshotsDir);
    return entries.filter((f) => /\.(jpg|jpeg|png)$/i.test(f));
  } catch {
    return [];
  }
}

export default async function ThumbnailPage() {
  const [projects, headshots] = await Promise.all([
    getThumbnailProjects(),
    getHeadshots(),
  ]);

  return <ThumbnailWizard projects={projects} headshots={headshots} />;
}
