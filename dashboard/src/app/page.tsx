import { getDashboardData } from "@/lib/workspace";
import { getEmployees } from "@/lib/employees";
import IsometricOfficeLoader from "@/components/employees/IsometricOfficeLoader";
import OverviewCards from "@/components/dashboard/OverviewCards";
import RecentActivity from "@/components/dashboard/RecentActivity";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const data = await getDashboardData();
  const employees = getEmployees(data.projects);

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="border-b border-slate-800 px-4 sm:px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-slate-100">Dashboard</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Overview of your AI agent team
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-300">Kelvin Learns Investing</span>
            <span className="text-xs text-slate-500">
              {new Date().toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </span>
          </div>
        </div>
      </header>

      <div className="flex-1 p-4 sm:p-6 flex flex-col gap-5">
        {/* Stat cards strip */}
        <OverviewCards
          activeCount={data.activeCount}
          hooksCount={data.hooksCount}
          topicsCount={data.topicsCount}
          videosAnalyzed={data.videosAnalyzed}
        />

        {/* Main content: Activity feed (1/3) + Office (2/3) */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 flex-1 min-h-0">
          <RecentActivity projects={data.projects} employees={employees} />
          <div className="lg:col-span-2">
            <IsometricOfficeLoader employees={employees} />
          </div>
        </div>
      </div>
    </div>
  );
}
