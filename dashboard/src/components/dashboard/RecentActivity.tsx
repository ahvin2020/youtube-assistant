import Image from "next/image";
import { Project, DOMAIN_ICONS } from "@/lib/types";
import { Employee } from "@/lib/types";

interface RecentActivityProps {
  projects: Project[];
  employees: Employee[];
}

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

function getEmployeeForDomain(employees: Employee[], domain: string): Employee | undefined {
  return employees.find((e) => e.domains.includes(domain as Employee["domains"][0]));
}

function getActivityText(project: Project): string {
  if (project.currentPhase === "complete") {
    return `completed ${project.displayName}`;
  }
  return `working on ${project.displayName}`;
}

const STATUS_COLORS: Record<string, string> = {
  complete: "bg-emerald-400",
  research: "bg-indigo-400",
  outline: "bg-indigo-400",
  script: "bg-indigo-400",
  concepts: "bg-pink-400",
  generate: "bg-pink-400",
  edit: "bg-pink-400",
  gathering: "bg-emerald-400",
  analysis: "bg-amber-400",
  scanning: "bg-amber-400",
  transcribe: "bg-sky-400",
  align: "bg-sky-400",
  cut: "bg-sky-400",
};

export default function RecentActivity({ projects, employees }: RecentActivityProps) {
  const sorted = [...projects]
    .sort((a, b) => b.updated.localeCompare(a.updated))
    .slice(0, 10);

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden flex flex-col min-h-0">
      <div className="px-4 sm:px-5 py-3 border-b border-slate-800 flex items-center justify-between shrink-0">
        <h2 className="text-sm font-semibold text-slate-300">
          Recent Activity
        </h2>
        <span className="text-xs text-slate-500">{sorted.length} events</span>
      </div>
      <div className="flex-1 overflow-y-auto divide-y divide-slate-800/50 scrollbar-thin">
        {sorted.map((project) => {
          const employee = getEmployeeForDomain(employees, project.domain);
          const isComplete = project.currentPhase === "complete";
          const dotColor = isComplete
            ? STATUS_COLORS.complete
            : STATUS_COLORS[project.currentPhase] || "bg-sky-400";

          return (
            <div
              key={`${project.domain}-${project.slug}`}
              className="px-4 sm:px-5 py-3 flex items-start gap-3 hover:bg-slate-800/30 transition-colors"
            >
              {/* Employee avatar */}
              <div className="relative shrink-0 mt-0.5">
                {employee ? (
                  <Image
                    src={employee.avatar}
                    alt={employee.name}
                    width={32}
                    height={32}
                    className="w-8 h-8 rounded-full object-cover bg-slate-800"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-xs">
                    {DOMAIN_ICONS[project.domain]}
                  </div>
                )}
                {/* Status dot */}
                <span
                  className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-slate-900 ${dotColor} ${
                    !isComplete ? "animate-pulse" : ""
                  }`}
                />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="text-sm text-slate-200">
                  <span className="font-medium">{employee?.name || "Agent"}</span>{" "}
                  <span className="text-slate-400">{getActivityText(project)}</span>
                </div>
                <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-2">
                  <span>{DOMAIN_ICONS[project.domain]}</span>
                  <span className="capitalize">{project.currentPhase}</span>
                  <span className="text-slate-600">·</span>
                  <span>{getRelativeTime(project.updated)}</span>
                </div>
              </div>
            </div>
          );
        })}
        {sorted.length === 0 && (
          <div className="px-5 py-8 text-center text-sm text-slate-500">
            No activity yet. Run a pipeline to get started.
          </div>
        )}
      </div>
    </div>
  );
}
