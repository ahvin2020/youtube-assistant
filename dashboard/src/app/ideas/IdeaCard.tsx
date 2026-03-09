"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Topic } from "@/lib/types";

const TREND_COLORS: Record<string, string> = {
  Viral: "bg-red-400/20 text-red-400",
  Rising: "bg-amber-400/20 text-amber-400",
  Stable: "bg-slate-400/20 text-slate-400",
  Declining: "bg-slate-600/20 text-slate-500",
};

function ScoreBar({ label, score }: { label: string; score: number }) {
  const pct = Math.min(score * 10, 100);
  const color =
    score >= 7 ? "bg-emerald-400" : score >= 4 ? "bg-amber-400" : "bg-red-400";

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-400 w-12">{label}</span>
      <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium text-slate-200 w-8 text-right">{score.toFixed(1)}</span>
    </div>
  );
}

export default function IdeaCard({ topic, rank }: { topic: Topic; rank: number }) {
  const [expanded, setExpanded] = useState(false);
  const router = useRouter();

  const handleWriteScript = (e: React.MouseEvent) => {
    e.stopPropagation();
    router.push(`/write?topic=${encodeURIComponent(topic.topic)}&format=longform`);
  };

  const handleResearch = (e: React.MouseEvent) => {
    e.stopPropagation();
    router.push(`/write?topic=${encodeURIComponent(topic.topic)}&phase=research`);
  };

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
      <div
        className="p-4 sm:p-5 cursor-pointer hover:bg-slate-700/30 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-start gap-3">
            <span className="text-xs text-slate-500 font-mono mt-0.5">#{rank}</span>
            <h3 className="text-sm sm:text-base font-semibold text-slate-100">
              {topic.topic}
            </h3>
          </div>
          <span className="text-slate-400 text-xs shrink-0">{expanded ? "▲" : "▼"}</span>
        </div>

        {/* Score bars */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
          <ScoreBar label="LF" score={topic.lf_score} />
          <ScoreBar label="Shorts" score={topic.shorts_score} />
        </div>

        {/* Badges */}
        <div className="flex flex-wrap gap-2">
          {topic.format_rec && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-400/15 text-indigo-400">
              {topic.format_rec}
            </span>
          )}
          {topic.trend && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${TREND_COLORS[topic.trend] || TREND_COLORS.Stable}`}>
              {topic.trend}
            </span>
          )}
          {topic.gap_status && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-300">
              {topic.gap_status}
            </span>
          )}
          {topic.sources && (
            <span className="text-xs text-slate-500">{topic.sources}</span>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 sm:px-5 pb-4 sm:pb-5 border-t border-slate-700 pt-4 space-y-3">
          {topic.why_it_works && (
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">Why it works</div>
              <p className="text-sm text-slate-200">{topic.why_it_works}</p>
            </div>
          )}
          {topic.suggested_angle && (
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">Suggested angle</div>
              <p className="text-sm text-slate-200">{topic.suggested_angle}</p>
            </div>
          )}
          {topic.hook_ideas && (
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">Hook ideas</div>
              <p className="text-sm text-slate-200 whitespace-pre-line">{topic.hook_ideas}</p>
            </div>
          )}
          {topic.research_more && (
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">Research more</div>
              <p className="text-sm text-slate-400">{topic.research_more}</p>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-2 pt-2 border-t border-slate-700/50">
            <button
              onClick={handleWriteScript}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/30 transition-colors"
            >
              <span>{"✍️"}</span> Write Script
            </button>
            <button
              onClick={handleResearch}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-700/50 text-slate-300 border border-slate-600/50 hover:bg-slate-700 transition-colors"
            >
              <span>{"🔍"}</span> Research More
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
