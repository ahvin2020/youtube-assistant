import { Project } from "@/lib/types";

interface OverviewCardsProps {
  projects: Project[];
  activeCount: number;
  hooksCount: number;
  ideasCount: number;
  videosAnalyzed: number;
}

function getThisWeekCount(projects: Project[]): number {
  const now = Date.now();
  const weekAgo = now - 7 * 24 * 60 * 60 * 1000;
  return projects.filter((p) => {
    const m = p.created.match(/^(\d{4})(\d{2})(\d{2})$/);
    if (!m) return false;
    return new Date(`${m[1]}-${m[2]}-${m[3]}`).getTime() >= weekAgo;
  }).length;
}

export default function OverviewCards({
  projects,
  activeCount,
  hooksCount,
  ideasCount,
  videosAnalyzed,
}: OverviewCardsProps) {
  const completedCount = projects.filter(
    (p) => p.currentPhase === "complete"
  ).length;
  const thisWeek = getThisWeekCount(projects);

  const cards = [
    {
      label: "Active Pipelines",
      value: activeCount,
      delta: activeCount > 0 ? `${activeCount} running now` : "All idle",
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      ),
      color: "text-emerald-400",
      bg: "bg-emerald-500/10",
      border: "border-emerald-500/20",
    },
    {
      label: "Tasks Completed",
      value: completedCount,
      delta: thisWeek > 0 ? `+${thisWeek} this week` : "No new this week",
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      color: "text-indigo-400",
      bg: "bg-indigo-500/10",
      border: "border-indigo-500/20",
    },
    {
      label: "Ideas Discovered",
      value: ideasCount,
      delta: hooksCount > 0 ? `${hooksCount} hooks mined` : "Run /idea to discover",
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
      ),
      color: "text-amber-400",
      bg: "bg-amber-500/10",
      border: "border-amber-500/20",
    },
    {
      label: "Videos Analyzed",
      value: videosAnalyzed,
      delta: videosAnalyzed > 0 ? "Across all runs" : "Run /analyze to start",
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M7 4V2m0 2a2 2 0 012 2v1a2 2 0 01-2 2 2 2 0 01-2-2V6a2 2 0 012-2zm0 10v2m0-2a2 2 0 01-2-2v-1a2 2 0 012-2 2 2 0 012 2v1a2 2 0 01-2 2zM17 4V2m0 2a2 2 0 012 2v1a2 2 0 01-2 2 2 2 0 01-2-2V6a2 2 0 012-2zm0 10v2m0-2a2 2 0 01-2-2v-1a2 2 0 012-2 2 2 0 012 2v1a2 2 0 01-2 2z" />
        </svg>
      ),
      color: "text-pink-400",
      bg: "bg-pink-500/10",
      border: "border-pink-500/20",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((card) => (
        <div
          key={card.label}
          className={`${card.bg} border ${card.border} rounded-xl p-4`}
        >
          <div className="flex items-center justify-between mb-3">
            <div className={`${card.color}`}>{card.icon}</div>
          </div>
          <div className={`text-2xl font-bold ${card.color}`}>
            {card.value}
          </div>
          <div className="text-xs text-slate-300 mt-1 font-medium">
            {card.label}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {card.delta}
          </div>
        </div>
      ))}
    </div>
  );
}
