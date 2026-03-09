import { Project, DOMAIN_ICONS, DOMAIN_COLORS, ROLE_TITLES } from "@/lib/types";

interface RecentActivityProps {
  projects: Project[];
}

const DOT_COLORS: Record<string, string> = {
  indigo: "bg-indigo-400",
  pink: "bg-pink-400",
  emerald: "bg-emerald-400",
  amber: "bg-amber-400",
  sky: "bg-sky-400",
};

function getRelativeTime(dateStr: string): string {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) {
    const m = dateStr.match(/^(\d{4})(\d{2})(\d{2})$/);
    if (m) {
      const parsed = new Date(`${m[1]}-${m[2]}-${m[3]}`);
      const diff = Date.now() - parsed.getTime();
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      if (days === 0) return "today";
      if (days === 1) return "1d ago";
      return `${days}d ago`;
    }
    return dateStr;
  }
  const diff = Date.now() - d.getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "1d ago";
  return `${days}d ago`;
}

function getActivityText(project: Project): string {
  if (project.currentPhase === "complete") {
    return `Completed ${project.displayName}`;
  }
  return `Working on ${project.displayName}`;
}

export default function RecentActivity({ projects }: RecentActivityProps) {
  const sorted = [...projects]
    .sort((a, b) => b.updated.localeCompare(a.updated))
    .slice(0, 15);

  return (
    <div className="overflow-hidden flex flex-col h-full">
      <div className="px-4 py-3 border-b border-slate-800 shrink-0">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
          Activity Feed
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {sorted.map((project) => {
          const role = ROLE_TITLES[project.domain] || "Agent";
          const domainColor = DOMAIN_COLORS[project.domain];
          const dotColor = DOT_COLORS[domainColor] || "bg-slate-400";
          const isComplete = project.currentPhase === "complete";

          return (
            <div
              key={`${project.domain}-${project.slug}`}
              className="px-4 py-3 border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-slate-500">
                  {getRelativeTime(project.updated)}
                </span>
              </div>
              <div className="flex items-start gap-2">
                <span
                  className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${
                    isComplete ? "bg-emerald-400" : dotColor
                  } ${!isComplete ? "animate-pulse" : ""}`}
                />
                <div className="min-w-0">
                  <div className="text-xs">
                    <span className="font-semibold text-slate-200">
                      {role}
                    </span>
                    <span className="text-slate-500"> - </span>
                    <span className="text-slate-400">
                      {getActivityText(project)}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-600 mt-0.5 flex items-center gap-1.5">
                    <span>{DOMAIN_ICONS[project.domain]}</span>
                    <span className="capitalize">{project.currentPhase}</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
        {sorted.length === 0 && (
          <div className="px-4 py-8 text-center text-xs text-slate-500">
            No activity yet. Run a pipeline to get started.
          </div>
        )}
      </div>
    </div>
  );
}
