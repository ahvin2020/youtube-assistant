"use client";

import { useRouter, useSearchParams } from "next/navigation";

const FILTERS = [
  { key: "", label: "All", style: "bg-slate-600 text-slate-100" },
  { key: "research", label: "Research", style: "bg-indigo-400/20 text-indigo-400 border border-indigo-400/30" },
  { key: "thumbnail", label: "Thumbnail", style: "bg-pink-400/20 text-pink-400 border border-pink-400/30" },
  { key: "topics", label: "Topics", style: "bg-emerald-400/20 text-emerald-400 border border-emerald-400/30" },
  { key: "analyze", label: "Analyze", style: "bg-amber-400/20 text-amber-400 border border-amber-400/30" },
  { key: "video", label: "Video", style: "bg-sky-400/20 text-sky-400 border border-sky-400/30" },
];

export default function FilterBar({ currentDomain }: { currentDomain?: string }) {
  const router = useRouter();

  return (
    <div className="flex flex-wrap gap-2">
      {FILTERS.map((f) => {
        const isActive = (f.key === "" && !currentDomain) || f.key === currentDomain;
        return (
          <button
            key={f.key}
            onClick={() =>
              router.push(f.key ? `/projects?domain=${f.key}` : "/projects")
            }
            className={`text-xs sm:text-sm px-3 py-1.5 rounded-full font-medium transition-all ${
              isActive
                ? f.style
                : "bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700"
            }`}
          >
            {f.label}
          </button>
        );
      })}
    </div>
  );
}
