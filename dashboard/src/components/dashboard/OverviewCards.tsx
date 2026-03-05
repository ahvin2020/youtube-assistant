interface OverviewCardsProps {
  activeCount: number;
  hooksCount: number;
  topicsCount: number;
  videosAnalyzed: number;
}

const cards = [
  {
    key: "active",
    label: "Total Agents",
    sub: "Registered AI agents",
    icon: "🤖",
    color: "border-indigo-500/30 text-indigo-300",
    bg: "bg-indigo-500/10",
  },
  {
    key: "hooks",
    label: "Active Missions",
    sub: "Currently running",
    icon: "🎯",
    color: "border-emerald-500/30 text-emerald-300",
    bg: "bg-emerald-500/10",
  },
  {
    key: "topics",
    label: "Events Today",
    sub: "Pipeline events",
    icon: "⚡",
    color: "border-amber-500/30 text-amber-300",
    bg: "bg-amber-500/10",
  },
  {
    key: "videos",
    label: "Total Assets",
    sub: "Videos analyzed",
    icon: "📊",
    color: "border-pink-500/30 text-pink-300",
    bg: "bg-pink-500/10",
  },
];

export default function OverviewCards({
  activeCount,
  hooksCount,
  topicsCount,
  videosAnalyzed,
}: OverviewCardsProps) {
  const values: Record<string, number> = {
    active: 5,
    hooks: activeCount,
    topics: hooksCount + topicsCount,
    videos: videosAnalyzed,
  };

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((card) => (
        <div
          key={card.key}
          className={`bg-slate-900/50 border rounded-xl p-4 ${card.color}`}
        >
          <div className="flex items-center justify-between mb-2">
            <div className={`w-8 h-8 rounded-lg ${card.bg} flex items-center justify-center text-sm`}>
              {card.icon}
            </div>
          </div>
          <div className="text-2xl font-bold">{values[card.key]}</div>
          <div className="text-xs text-slate-400 mt-0.5">{card.label}</div>
          <div className="text-[10px] text-slate-600 mt-0.5">{card.sub}</div>
        </div>
      ))}
    </div>
  );
}
