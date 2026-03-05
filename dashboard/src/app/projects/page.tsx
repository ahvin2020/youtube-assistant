import { getAllProjects } from "@/lib/workspace";
import { Domain, DOMAIN_COLORS } from "@/lib/types";
import ProjectCard from "@/components/projects/ProjectCard";
import FilterBar from "./FilterBar";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{ domain?: string }>;
}

const DOMAIN_FILTER_COLORS: Record<string, string> = {
  all: "bg-slate-600 text-slate-100",
  research: "bg-indigo-400/20 text-indigo-400 border border-indigo-400/30",
  thumbnail: "bg-pink-400/20 text-pink-400 border border-pink-400/30",
  topics: "bg-emerald-400/20 text-emerald-400 border border-emerald-400/30",
  analyze: "bg-amber-400/20 text-amber-400 border border-amber-400/30",
  video: "bg-sky-400/20 text-sky-400 border border-sky-400/30",
};

export default async function ProjectsPage({ searchParams }: Props) {
  const params = await searchParams;
  const projects = await getAllProjects();
  const domainFilter = params.domain;

  const filtered = domainFilter
    ? projects.filter((p) => p.domain === domainFilter)
    : projects;

  return (
    <div className="p-4 sm:p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-slate-100">Projects</h1>
        <p className="text-sm text-slate-400 mt-1">
          {projects.length} projects across all pipelines
        </p>
      </div>

      {/* Filter tabs */}
      <FilterBar currentDomain={domainFilter} />

      {/* Project grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((project) => (
          <ProjectCard key={`${project.domain}-${project.slug}`} project={project} />
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="text-center text-slate-400 py-12">
          No projects found{domainFilter ? ` for ${domainFilter}` : ""}.
        </div>
      )}
    </div>
  );
}
