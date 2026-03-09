import { getDashboardData } from "@/lib/workspace";
import { PIPELINES } from "@/lib/types";
import OverviewCards from "@/components/dashboard/OverviewCards";
import PipelineTracker from "@/components/dashboard/PipelineTracker";
import RecentActivity from "@/components/dashboard/RecentActivity";
import Link from "next/link";

export const dynamic = "force-dynamic";

const COLOR_MAP: Record<string, { bg: string; border: string; text: string }> = {
  indigo: { bg: "bg-indigo-500/10", border: "border-indigo-500/30", text: "text-indigo-300" },
  pink: { bg: "bg-pink-500/10", border: "border-pink-500/30", text: "text-pink-300" },
  emerald: { bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-300" },
  amber: { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-300" },
  sky: { bg: "bg-sky-500/10", border: "border-sky-500/30", text: "text-sky-300" },
  violet: { bg: "bg-violet-500/10", border: "border-violet-500/30", text: "text-violet-300" },
};

const PIPELINE_ROUTES: Record<string, string> = {
  ideas: "/idea",
  write: "/write",
  thumbnail: "/thumbnail",
  cut: "/cut",
  enhance: "/enhance",
  analyze: "/analyze",
};

export default async function HomePage() {
  const data = await getDashboardData();

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="border-b border-slate-800 px-4 sm:px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
              Command Center
            </h1>
            <span className="text-slate-600">/</span>
            <span className="text-xs text-slate-500">Overview</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-300">Kelvin Learns Investing</span>
            <span className="text-xs text-slate-500">
              {new Date().toLocaleDateString("en-US", {
                weekday: "short",
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </span>
          </div>
        </div>
      </header>

      {/* Main layout: content + sidebar */}
      <div className="flex-1 flex min-h-0">
        {/* Left: main content */}
        <div className="flex-1 p-4 sm:p-6 flex flex-col gap-5 overflow-y-auto">
          <OverviewCards
            projects={data.projects}
            activeCount={data.activeCount}
            hooksCount={data.hooksCount}
            ideasCount={data.ideasCount}
            videosAnalyzed={data.videosAnalyzed}
          />

          <PipelineTracker contentProjects={data.contentProjects} />

          {/* Pipeline quick-launch grid */}
          <div>
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3">
              Pipelines
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {PIPELINES.map((pipeline) => {
                const colors = COLOR_MAP[pipeline.color] || COLOR_MAP.indigo;
                const route = PIPELINE_ROUTES[pipeline.id] || "/";
                const domainProjects = data.projects.filter((p) => p.domain === pipeline.domain);
                const active = domainProjects.filter((p) => p.state?.phase && p.state.phase !== "complete").length;
                const completed = domainProjects.filter((p) => p.state?.phase === "complete").length;

                return (
                  <Link
                    key={pipeline.id}
                    href={route}
                    className={`${colors.bg} border ${colors.border} rounded-xl p-4 flex flex-col hover:brightness-110 transition-all`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-lg">{pipeline.icon}</span>
                      {active > 0 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-bold">
                          {active}
                        </span>
                      )}
                    </div>
                    <div className={`text-sm font-semibold ${colors.text}`}>
                      {pipeline.role}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5 mb-3 flex-1">
                      {pipeline.description}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      {completed} completed
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right: activity sidebar */}
        <div className="hidden lg:block w-72 xl:w-80 border-l border-slate-800 shrink-0">
          <RecentActivity projects={data.projects} />
        </div>
      </div>
    </div>
  );
}
