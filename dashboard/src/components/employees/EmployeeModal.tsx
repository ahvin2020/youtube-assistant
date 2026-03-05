"use client";

import { useState } from "react";
import Image from "next/image";
import { Employee } from "@/lib/types";

const COLOR_MAP: Record<string, { bg: string; text: string; border: string }> = {
  indigo: { bg: "bg-indigo-400", text: "text-indigo-400", border: "border-indigo-400/30" },
  pink: { bg: "bg-pink-400", text: "text-pink-400", border: "border-pink-400/30" },
  emerald: { bg: "bg-emerald-400", text: "text-emerald-400", border: "border-emerald-400/30" },
  amber: { bg: "bg-amber-400", text: "text-amber-400", border: "border-amber-400/30" },
  sky: { bg: "bg-sky-400", text: "text-sky-400", border: "border-sky-400/30" },
};

interface EmployeeModalProps {
  employee: Employee;
  onClose: () => void;
}

export default function EmployeeModal({ employee, onClose }: EmployeeModalProps) {
  const [tab, setTab] = useState<"status" | "chat">("status");
  const colors = COLOR_MAP[employee.color] || COLOR_MAP.indigo;

  // Generate chat messages based on employee state
  const chatMessages = [
    {
      from: employee.name,
      text: employee.status === "busy"
        ? `Working on ${employee.currentAssignment}. Making good progress.`
        : "All caught up! Ready for the next assignment whenever you are.",
    },
    {
      from: employee.name,
      text: employee.projectsCompleted > 0
        ? `I've completed ${employee.projectsCompleted} project${employee.projectsCompleted > 1 ? "s" : ""} so far.`
        : "Haven't had any projects assigned yet. Eager to get started!",
    },
    {
      from: employee.name,
      text: `"${employee.personality}"`,
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-slate-800 border border-slate-600 rounded-t-2xl sm:rounded-2xl w-full sm:max-w-lg max-h-[85vh] overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="p-5 border-b border-slate-700 flex items-center gap-4">
          <Image
            src={employee.avatar}
            alt={employee.name}
            width={56}
            height={56}
            className="w-14 h-14 rounded-lg object-contain bg-slate-700/50"
          />
          <div className="flex-1">
            <div className="text-lg font-semibold text-slate-100">{employee.name}</div>
            <div className="text-sm text-slate-400">{employee.title}</div>
            <div className="flex items-center gap-2 mt-1">
              <span
                className={`w-2 h-2 rounded-full ${
                  employee.status === "busy" ? "bg-emerald-400 animate-pulse" : "bg-slate-500"
                }`}
              />
              <span className="text-xs text-slate-400 capitalize">{employee.status}</span>
              {employee.currentAssignment && (
                <span className="text-xs text-slate-500">
                  — {employee.currentAssignment}
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 text-xl"
          >
            &times;
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-700">
          {(["status", "chat"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2.5 text-sm font-medium capitalize transition-colors ${
                tab === t
                  ? `${colors.text} border-b-2 ${colors.border}`
                  : "text-slate-400 hover:text-slate-300"
              }`}
            >
              {t === "status" ? "Status" : "Chat"}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="p-5">
          {tab === "status" ? (
            <div className="space-y-4">
              {/* Skills */}
              <div>
                <div className="text-xs text-slate-400 uppercase tracking-wide mb-2">Skills</div>
                <div className="flex flex-wrap gap-2">
                  {employee.skills.map((skill) => (
                    <span
                      key={skill}
                      className={`text-xs px-2 py-1 rounded-full border ${colors.border} ${colors.text}`}
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-700/50 rounded-lg p-3">
                  <div className="text-2xl font-bold text-slate-100">
                    {employee.projectsCompleted}
                  </div>
                  <div className="text-xs text-slate-400">Projects completed</div>
                </div>
                <div className="bg-slate-700/50 rounded-lg p-3">
                  <div className="text-2xl font-bold text-slate-100 capitalize">
                    {employee.status}
                  </div>
                  <div className="text-xs text-slate-400">Current status</div>
                </div>
              </div>

              {/* Personality */}
              <div className="bg-slate-700/30 rounded-lg p-3 border border-slate-600/50">
                <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">
                  Philosophy
                </div>
                <div className={`text-sm ${colors.text} italic`}>
                  &ldquo;{employee.personality}&rdquo;
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {chatMessages.map((msg, i) => (
                <div key={i} className="flex gap-3">
                  <Image
                    src={employee.avatar}
                    alt={employee.name}
                    width={32}
                    height={32}
                    className="w-8 h-8 rounded-md object-contain bg-slate-700/50 shrink-0"
                  />
                  <div className="bg-slate-700/50 rounded-lg rounded-tl-none p-3 text-sm text-slate-200 max-w-[85%]">
                    {msg.text}
                  </div>
                </div>
              ))}
              <div className="text-center text-xs text-slate-500 pt-2">
                Live chat coming soon...
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
