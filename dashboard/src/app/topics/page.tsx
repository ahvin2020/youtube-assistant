import { getTopics } from "@/lib/topics";
import TopicCard from "./TopicCard";

export const dynamic = "force-dynamic";

export default async function TopicsPage() {
  const { topics, sheetUrl } = await getTopics();

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-100">Topic Intelligence</h1>
          <p className="text-sm text-slate-400 mt-1">
            {topics.length} opportunities discovered from multiple sources
          </p>
        </div>
        {sheetUrl && (
          <a
            href={sheetUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs px-3 py-1.5 bg-emerald-400/15 text-emerald-400 rounded-lg hover:bg-emerald-400/25 transition-colors shrink-0"
          >
            Open Sheet ↗
          </a>
        )}
      </div>

      {/* Source badges */}
      <div className="flex flex-wrap gap-2">
        {["YouTube", "Trends", "Reddit", "Twitter"].map((src) => (
          <span
            key={src}
            className="text-xs px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700"
          >
            ✓ {src}
          </span>
        ))}
      </div>

      {/* Topic cards */}
      <div className="space-y-4">
        {topics.map((topic, i) => (
          <TopicCard key={i} topic={topic} rank={i + 1} />
        ))}
      </div>

      {topics.length === 0 && (
        <div className="text-center text-slate-400 py-12">
          No topics found. Run /topics to discover content opportunities.
        </div>
      )}
    </div>
  );
}
