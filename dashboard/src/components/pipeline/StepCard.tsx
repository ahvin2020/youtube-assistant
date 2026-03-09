"use client";

import { useState } from "react";

export type StepStatus = "pending" | "running" | "done" | "error";

interface StepCardProps {
  title: string;
  status: StepStatus;
  summary?: string;
  children: React.ReactNode;
  defaultExpanded?: boolean;
}

const STATUS_STYLES: Record<StepStatus, { dot: string; label: string; text: string }> = {
  pending: { dot: "bg-slate-500", label: "Pending", text: "text-slate-500" },
  running: { dot: "bg-indigo-400 animate-pulse", label: "Running", text: "text-indigo-400" },
  done: { dot: "bg-emerald-400", label: "Done", text: "text-emerald-400" },
  error: { dot: "bg-red-400", label: "Error", text: "text-red-400" },
};

export default function StepCard({ title, status, summary, children, defaultExpanded }: StepCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded ?? status !== "done");
  const styles = STATUS_STYLES[status];

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 sm:px-5 py-3 flex items-center gap-3 hover:bg-slate-800/30 transition-colors"
      >
        <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${styles.dot}`} />
        <span className="text-sm font-semibold text-slate-200 flex-1 text-left">
          {title}
        </span>
        {status === "done" && summary && !expanded && (
          <span className="text-xs text-slate-400 truncate max-w-[40%]">
            {summary}
          </span>
        )}
        <span className={`text-[10px] font-medium uppercase ${styles.text}`}>
          {styles.label}
        </span>
        <svg
          className={`w-4 h-4 text-slate-500 transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {expanded && (
        <div className="px-4 sm:px-5 pb-4 pt-1">
          {children}
        </div>
      )}
    </div>
  );
}
