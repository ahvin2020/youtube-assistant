import fs from "fs/promises";
import path from "path";
import AnalyzeWizard from "./AnalyzeWizard";

export const dynamic = "force-dynamic";

const WORKSPACE_ROOT = path.resolve(process.cwd(), "..");

async function getAnalyzeProjects() {
  const tempDir = path.join(WORKSPACE_ROOT, "workspace", "temp", "analyze");
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

export default async function AnalyzePage() {
  const projects = await getAnalyzeProjects();

  return <AnalyzeWizard projects={projects} />;
}
