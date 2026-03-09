import fs from "fs/promises";
import path from "path";
import WriteWizard from "./WriteWizard";

export const dynamic = "force-dynamic";

const WORKSPACE_ROOT = path.resolve(process.cwd(), "..");

async function getWriteProjects() {
  const tempDir = path.join(WORKSPACE_ROOT, "workspace", "temp", "research");
  try {
    const entries = await fs.readdir(tempDir, { withFileTypes: true });
    const dirs = entries.filter((e) => e.isDirectory()).map((e) => e.name).sort().reverse();
    const projects = [];
    for (const slug of dirs.slice(0, 20)) {
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

export default async function WritePage() {
  const projects = await getWriteProjects();

  return <WriteWizard projects={projects} />;
}
