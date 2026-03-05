interface TopBarProps {
  activeCount: number;
  hooksCount: number;
}

export default function TopBar({ activeCount, hooksCount }: TopBarProps) {
  const today = new Date().toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <header className="bg-slate-900 border-b border-slate-700 px-4 sm:px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <h1 className="text-base sm:text-lg font-bold text-slate-100 tracking-wide uppercase">
          Command Center
        </h1>
        <div className="hidden sm:flex items-center gap-3 text-xs text-slate-400">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            {activeCount} active
          </span>
          <span>{hooksCount} hooks</span>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-sm text-slate-300">Kelvin Learns Investing</span>
        <span className="text-xs text-slate-500">{today}</span>
      </div>
    </header>
  );
}
