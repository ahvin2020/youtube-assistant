"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Employee } from "@/lib/types";
import EmployeeModal from "./EmployeeModal";

export default function IsometricOffice({ employees }: { employees: Employee[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<unknown>(null);
  const [selected, setSelected] = useState<Employee | null>(null);
  const [error, setError] = useState<string | null>(null);

  const clickRef = useRef<(id: string) => void>(() => {});
  clickRef.current = useCallback(
    (id: string) => {
      const emp = employees.find((e) => e.id === id);
      if (emp) setSelected(emp);
    },
    [employees],
  );

  useEffect(() => {
    if (!containerRef.current || gameRef.current) return;

    let destroyed = false;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let game: any = null;

    const init = async () => {
      try {
        // Must dynamically import Phaser — it uses browser globals (navigator, window)
        const Phaser = await import("phaser");
        if (destroyed) return;

        // Dynamically import scene (also depends on Phaser)
        const { default: OfficeScene } = await import("@/game/OfficeScene");
        if (destroyed || !containerRef.current) return;

        const empData = employees.map((e) => ({
          id: e.id,
          name: e.name,
          avatar: e.avatar,
          color: e.color,
          status: e.status,
        }));

        game = new Phaser.Game({
          type: Phaser.AUTO,
          parent: containerRef.current,
          width: 1408,
          height: 768,
          backgroundColor: "#0f172a",
          scale: {
            mode: Phaser.Scale.FIT,
            autoCenter: Phaser.Scale.CENTER_HORIZONTALLY,
          },
          scene: [],
          audio: { noAudio: true },
        });

        game.scene.add("office", OfficeScene, true, {
          employees: empData,
          onClick: (id: string) => clickRef.current(id),
        });

        gameRef.current = game;
      } catch (err) {
        console.error("Phaser init error:", err);
        setError(err instanceof Error ? err.message : String(err));
      }
    };

    init();

    return () => {
      destroyed = true;
      if (game) {
        game.destroy(true);
      }
      gameRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden flex flex-col">
        <div className="px-4 sm:px-5 py-3 border-b border-slate-800 flex items-center justify-between shrink-0">
          <h2 className="text-sm font-semibold text-slate-300">Virtual Office</h2>
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>{employees.filter((e) => e.status === "busy").length} active</span>
          </div>
        </div>
        {error && (
          <div className="p-4 text-xs text-red-400 font-mono whitespace-pre-wrap">Error: {error}</div>
        )}
        <div ref={containerRef} className="w-full" style={{ aspectRatio: "1408 / 768" }} />
      </div>

      {selected && <EmployeeModal employee={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
