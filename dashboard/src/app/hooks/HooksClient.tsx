"use client";

import { useState } from "react";
import { Hook } from "@/lib/types";

const CATEGORY_COLORS: Record<string, string> = {
  curiosity: "bg-purple-400/20 text-purple-400",
  money: "bg-emerald-400/20 text-emerald-400",
  transformation: "bg-blue-400/20 text-blue-400",
  contrarian: "bg-red-400/20 text-red-400",
  time: "bg-amber-400/20 text-amber-400",
  urgency: "bg-orange-400/20 text-orange-400",
  technical: "bg-slate-400/20 text-slate-400",
};

interface HooksClientProps {
  hooks: Hook[];
  categories: Record<string, number>;
}

export default function HooksClient({ hooks, categories }: HooksClientProps) {
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");

  const filtered = hooks.filter((h) => {
    if (filter && h.category !== filter) return false;
    if (search) {
      const q = search.toLowerCase();
      if (!h.text.toLowerCase().includes(q) && !h.source_channel.toLowerCase().includes(q)) {
        return false;
      }
    }
    return true;
  });

  return (
    <>
      {/* Category badges */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setFilter("")}
          className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all ${
            !filter ? "bg-slate-600 text-slate-100" : "bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700"
          }`}
        >
          All ({hooks.length})
        </button>
        {Object.entries(categories)
          .sort(([, a], [, b]) => b - a)
          .map(([cat, count]) => (
            <button
              key={cat}
              onClick={() => setFilter(filter === cat ? "" : cat)}
              className={`text-xs px-3 py-1.5 rounded-full font-medium capitalize transition-all ${
                filter === cat
                  ? CATEGORY_COLORS[cat] || "bg-slate-600 text-slate-100"
                  : "bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700"
              }`}
            >
              {cat} ({count})
            </button>
          ))}
      </div>

      {/* Search */}
      <input
        type="text"
        placeholder="Search hooks..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full sm:w-80 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-slate-500"
      />

      {/* Table */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left p-3 text-xs text-slate-400 font-medium uppercase">Hook Text</th>
                <th className="text-left p-3 text-xs text-slate-400 font-medium uppercase w-24">Category</th>
                <th className="text-left p-3 text-xs text-slate-400 font-medium uppercase w-20 hidden sm:table-cell">Format</th>
                <th className="text-left p-3 text-xs text-slate-400 font-medium uppercase hidden md:table-cell">Channel</th>
                <th className="text-right p-3 text-xs text-slate-400 font-medium uppercase w-20 hidden sm:table-cell">Views</th>
                <th className="text-right p-3 text-xs text-slate-400 font-medium uppercase w-16 hidden lg:table-cell">Outlier</th>
                <th className="text-right p-3 text-xs text-slate-400 font-medium uppercase w-16">Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {filtered.map((hook) => (
                <tr key={hook.id} className="hover:bg-slate-700/30 transition-colors">
                  <td className="p-3 text-slate-200 max-w-xs">
                    <div className="line-clamp-2">{hook.text}</div>
                  </td>
                  <td className="p-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${CATEGORY_COLORS[hook.category] || "bg-slate-600 text-slate-300"}`}>
                      {hook.category}
                    </span>
                  </td>
                  <td className="p-3 text-slate-400 capitalize hidden sm:table-cell">{hook.format}</td>
                  <td className="p-3 text-slate-400 truncate max-w-[150px] hidden md:table-cell">{hook.source_channel}</td>
                  <td className="p-3 text-right text-slate-300 hidden sm:table-cell">
                    {hook.views >= 1000000
                      ? `${(hook.views / 1000000).toFixed(1)}M`
                      : hook.views >= 1000
                      ? `${(hook.views / 1000).toFixed(0)}K`
                      : hook.views}
                  </td>
                  <td className="p-3 text-right text-slate-300 hidden lg:table-cell">
                    {hook.outlier_score.toFixed(1)}
                  </td>
                  <td className="p-3 text-right font-medium text-slate-100">
                    {hook.performance_score.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && (
          <div className="text-center text-slate-500 py-8">No hooks match your filters.</div>
        )}
      </div>
    </>
  );
}
