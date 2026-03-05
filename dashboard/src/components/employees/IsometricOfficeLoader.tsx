"use client";

import dynamic from "next/dynamic";
import { Employee } from "@/lib/types";

const IsometricOffice = dynamic(() => import("./IsometricOffice"), {
  ssr: false,
  loading: () => (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden flex flex-col">
      <div className="px-4 sm:px-5 py-3 border-b border-slate-800">
        <h2 className="text-sm font-semibold text-slate-300">Virtual Office</h2>
      </div>
      <div className="w-full aspect-[1408/768] bg-slate-900/30 animate-pulse" />
    </div>
  ),
});

export default function IsometricOfficeLoader({ employees }: { employees: Employee[] }) {
  return <IsometricOffice employees={employees} />;
}
