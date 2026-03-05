import Link from "next/link";
import { Project, DOMAIN_PHASES, DOMAIN_ICONS, DOMAIN_COLORS } from "@/lib/types";

const BORDER_COLORS: Record<string, string> = {
  indigo: "border-l-indigo-400",
  pink: "border-l-pink-400",
  emerald: "border-l-emerald-400",
  amber: "border-l-amber-400",
  sky: "border-l-sky-400",
};

const DOT_COLORS: Record<string, string> = {
  indigo: "bg-indigo-400",
  pink: "bg-pink-400",
  emerald: "bg-emerald-400",
  amber: "bg-amber-400",
  sky: "bg-sky-400",
};

const BADGE_BG: Record<string, string> = {
  indigo: "bg-indigo-400/15 text-indigo-400",
  pink: "bg-pink-400/15 text-pink-400",
  emerald: "bg-emerald-400/15 text-emerald-400",
  amber: "bg-amber-400/15 text-amber-400",
  sky: "bg-sky-400/15 text-sky-400",
};

export default function ProjectCard({ project }: { project: Project }) {
  const color = DOMAIN_COLORS[project.domain];
  const phases = DOMAIN_PHASES[project.domain];
  const icon = DOMAIN_ICONS[project.domain];
  const isComplete = project.currentPhase === "complete";

  return (
    <Link href={`/projects/${project.domain}/${project.slug}`}>
      <div
        className={`bg-slate-800 border border-slate-700 border-l-4 ${BORDER_COLORS[color]} rounded-xl p-4 sm:p-5 hover:bg-slate-700/50 transition-colors cursor-pointer h-full`}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-2 mb-3">
          <h3 className="text-sm sm:text-base font-semibold text-slate-100 line-clamp-2">
            {project.displayName}
          </h3>
          <span className="text-lg shrink-0">{icon}</span>
        </div>

        {/* Domain badge */}
        <div className="flex items-center gap-2 mb-3">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${BADGE_BG[color]}`}>
            {project.domain}
          </span>
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${
              isComplete
                ? "bg-emerald-400/15 text-emerald-400"
                : "bg-sky-400/15 text-sky-400"
            }`}
          >
            {project.currentPhase}
          </span>
        </div>

        {/* Phase dots */}
        <div className="flex items-center gap-1.5 mb-3">
          {phases.map((phase, i) => {
            const isDone = i <= project.phaseIndex;
            const isCurrent = phase === project.currentPhase;
            return (
              <div key={phase} className="flex items-center gap-1.5">
                <div
                  className={`w-2 h-2 rounded-full ${
                    isCurrent
                      ? `${DOT_COLORS[color]} animate-pulse`
                      : isDone
                      ? DOT_COLORS[color]
                      : "bg-slate-600"
                  }`}
                  title={phase}
                />
                {i < phases.length - 1 && (
                  <div className={`w-3 h-0.5 ${isDone ? DOT_COLORS[color] : "bg-slate-600"}`} />
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>{project.created}</span>
          {project.sheetUrl && (
            <span className="text-emerald-400" title="Google Sheet">
              📊
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
