import { Project, DOMAIN_PHASES, DOMAIN_ICONS, DOMAIN_COLORS } from "@/lib/types";

const COLOR_MAP: Record<string, string> = {
  indigo: "bg-indigo-400",
  pink: "bg-pink-400",
  emerald: "bg-emerald-400",
  amber: "bg-amber-400",
  sky: "bg-sky-400",
};

const BADGE_COLORS: Record<string, string> = {
  complete: "bg-emerald-400/20 text-emerald-400",
  default: "bg-sky-400/20 text-sky-400",
};

interface PipelineStatusGridProps {
  projects: Project[];
}

export default function PipelineStatusGrid({ projects }: PipelineStatusGridProps) {
  if (projects.length === 0) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 text-slate-400 text-sm text-center">
        No projects yet. Run a pipeline to get started.
      </div>
    );
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
      <div className="px-4 sm:px-5 py-3 border-b border-slate-700">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
          Active Pipelines
        </h2>
      </div>
      <div className="divide-y divide-slate-700/50">
        {projects.map((project) => {
          const phases = DOMAIN_PHASES[project.domain];
          const domainColor = DOMAIN_COLORS[project.domain];
          const icon = DOMAIN_ICONS[project.domain];
          const isComplete = project.currentPhase === "complete";
          const badgeColor = isComplete
            ? BADGE_COLORS.complete
            : BADGE_COLORS.default;

          return (
            <div
              key={`${project.domain}-${project.slug}`}
              className="px-4 sm:px-5 py-3 flex items-center gap-3 sm:gap-4 hover:bg-slate-700/30 transition-colors"
            >
              {/* Domain icon */}
              <span className="text-lg shrink-0">{icon}</span>

              {/* Project name */}
              <div className="flex-1 min-w-0">
                <div className="text-sm text-slate-200 truncate">
                  {project.displayName}
                </div>
              </div>

              {/* Phase dots */}
              <div className="hidden sm:flex items-center gap-1.5">
                {phases.map((phase, i) => {
                  const isCurrent = phase === project.currentPhase;
                  const isDone = i <= project.phaseIndex;
                  return (
                    <div key={phase} className="flex items-center gap-1.5">
                      <div
                        className={`w-2.5 h-2.5 rounded-full transition-all ${
                          isCurrent
                            ? `${COLOR_MAP[domainColor]} animate-pulse ring-2 ring-offset-1 ring-offset-slate-800 ring-${domainColor}-400/50`
                            : isDone
                            ? COLOR_MAP[domainColor]
                            : "bg-slate-600"
                        }`}
                        title={phase}
                      />
                      {i < phases.length - 1 && (
                        <div
                          className={`w-3 h-0.5 ${
                            isDone ? COLOR_MAP[domainColor] : "bg-slate-600"
                          }`}
                        />
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Status badge */}
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${badgeColor}`}
              >
                {project.currentPhase}
              </span>

              {/* Date */}
              <span className="text-xs text-slate-500 hidden sm:block w-16 text-right">
                {project.updated}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
