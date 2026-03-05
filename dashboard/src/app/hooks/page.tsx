import { getHooks } from "@/lib/hooks";
import HooksClient from "./HooksClient";

export const dynamic = "force-dynamic";

export default async function HooksPage() {
  const { hooks, total, analyzedVideos, lastUpdated } = await getHooks();

  // Get unique categories with counts
  const categories: Record<string, number> = {};
  hooks.forEach((h) => {
    categories[h.category] = (categories[h.category] || 0) + 1;
  });

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-slate-100">Hooks Database</h1>
        <p className="text-sm text-slate-400 mt-1">
          {total} proven hooks extracted from {analyzedVideos} videos
          {lastUpdated && ` · Updated ${lastUpdated}`}
        </p>
      </div>

      <HooksClient hooks={hooks} categories={categories} />
    </div>
  );
}
