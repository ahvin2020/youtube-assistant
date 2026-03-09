import Link from "next/link";
import { ContentProject, Domain, Project } from "@/lib/types";

interface PipelineTrackerProps {
  contentProjects: ContentProject[];
}

const COLUMN_COLORS = {
  indigo: {
    header: "text-indigo-300",
    badge: "bg-indigo-500/20 text-indigo-300",
    border: "border-indigo-500/30",
    cardBg: "bg-indigo-500/5",
    dot: "bg-indigo-400",
  },
  sky: {
    header: "text-sky-300",
    badge: "bg-sky-500/20 text-sky-300",
    border: "border-sky-500/30",
    cardBg: "bg-sky-500/5",
    dot: "bg-sky-400",
  },
  emerald: {
    header: "text-emerald-300",
    badge: "bg-emerald-500/20 text-emerald-300",
    border: "border-emerald-500/30",
    cardBg: "bg-emerald-500/5",
    dot: "bg-emerald-400",
  },
};

type ColumnKey = "writing" | "post-prod" | "ready";

const COLUMNS: { key: ColumnKey; label: string; color: keyof typeof COLUMN_COLORS }[] = [
  { key: "writing", label: "Writing", color: "indigo" },
  { key: "post-prod", label: "Post-Production", color: "sky" },
  { key: "ready", label: "Ready to Post", color: "emerald" },
];

function getRelativeTime(dateStr: string): string {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) {
    const m = dateStr.match(/^(\d{4})(\d{2})(\d{2})$/);
    if (m) {
      const days = Math.floor((Date.now() - new Date(`${m[1]}-${m[2]}-${m[3]}`).getTime()) / 86400000);
      if (days === 0) return "today";
      if (days === 1) return "1d ago";
      return `${days}d ago`;
    }
    return dateStr;
  }
  const hours = Math.floor((Date.now() - d.getTime()) / 3600000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "1d ago";
  return `${days}d ago`;
}

function classifyProject(cp: ContentProject): ColumnKey {
  const write = cp.stages.research;
  const edit = cp.stages.video;
  const thumb = cp.stages.thumbnail;

  const writeDone = write?.currentPhase === "complete";
  const editDone = edit?.currentPhase === "complete";
  const thumbDone = thumb?.currentPhase === "complete";

  if (editDone && thumbDone) return "ready";
  if (writeDone || (!write && (edit || thumb))) return "post-prod";
  return "writing";
}

function getNextAction(cp: ContentProject): string | null {
  const write = cp.stages.research;
  const edit = cp.stages.video;
  const thumb = cp.stages.thumbnail;

  const writeDone = write?.currentPhase === "complete";
  const editDone = edit?.currentPhase === "complete";
  const thumbDone = thumb?.currentPhase === "complete";

  if (editDone && thumbDone) return "Ready to publish";
  if (writeDone && !edit && !thumb) return "Record video, then /edit and /thumbnail";
  if (writeDone && !thumb) return "Run /thumbnail";
  if (writeDone && !edit) return "Run /edit after recording";
  if (write && !writeDone) return null;
  if (thumb && !thumbDone && !write) return "Run /write for the script";
  return null;
}

function StatusDot({ done, active, label }: { done: boolean; active: boolean; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      {done ? (
        <svg className="w-3 h-3 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      ) : active ? (
        <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse shrink-0" />
      ) : (
        <span className="w-1.5 h-1.5 rounded-full bg-slate-600 shrink-0" />
      )}
      <span className={`text-[11px] ${done ? "text-emerald-400" : active ? "text-slate-300" : "text-slate-500"}`}>
        {label}
      </span>
    </div>
  );
}

function ProjectCard({ cp, color }: { cp: ContentProject; color: keyof typeof COLUMN_COLORS }) {
  const colors = COLUMN_COLORS[color];
  const column = classifyProject(cp);
  const nextAction = getNextAction(cp);

  const write = cp.stages.research;
  const edit = cp.stages.video;
  const thumb = cp.stages.thumbnail;

  return (
    <div className={`${colors.cardBg} border ${colors.border} rounded-lg p-3 transition-all hover:brightness-110`}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-xs font-semibold text-slate-200 truncate">{cp.displayName}</h4>
        <span className="text-[10px] text-slate-500 shrink-0 ml-2">{getRelativeTime(cp.lastUpdated)}</span>
      </div>

      {column === "writing" && write && (
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${colors.dot} animate-pulse`} />
          <span className="text-[11px] text-indigo-300 font-medium">
            {write.currentPhase.charAt(0).toUpperCase() + write.currentPhase.slice(1)}
          </span>
        </div>
      )}

      {column === "post-prod" && (
        <div className="flex items-center gap-3">
          <StatusDot
            done={edit?.currentPhase === "complete"}
            active={!!edit && edit.currentPhase !== "complete"}
            label={edit ? (edit.currentPhase === "complete" ? "Edit" : `Edit: ${edit.currentPhase}`) : "Edit"}
          />
          <StatusDot
            done={thumb?.currentPhase === "complete"}
            active={!!thumb && thumb.currentPhase !== "complete"}
            label={thumb ? (thumb.currentPhase === "complete" ? "Thumb" : `Thumb: ${thumb.currentPhase}`) : "Thumb"}
          />
        </div>
      )}

      {column === "ready" && (
        <div className="flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-[11px] text-emerald-400 font-medium">All stages complete</span>
        </div>
      )}

      {nextAction && (
        <div className="mt-2 text-[10px] text-slate-500">
          → {nextAction}
        </div>
      )}
    </div>
  );
}

function KanbanColumn({ column, cards }: { column: typeof COLUMNS[number]; cards: ContentProject[] }) {
  const colors = COLUMN_COLORS[column.color];

  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-2 mb-3">
        <h3 className={`text-xs font-semibold uppercase tracking-wide ${colors.header}`}>
          {column.label}
        </h3>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${colors.badge}`}>
          {cards.length}
        </span>
      </div>

      {cards.length === 0 ? (
        <div className="border border-dashed border-slate-700/50 rounded-lg p-4 text-center">
          <p className="text-[11px] text-slate-600">No projects</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {cards.map((cp) => (
            <ProjectCard key={cp.contentSlug} cp={cp} color={column.color} />
          ))}
        </div>
      )}
    </div>
  );
}

function IdeaBankRow({ cp }: { cp: ContentProject }) {
  const idea = cp.stages.ideas;
  const state = idea?.state as Record<string, unknown> | null;
  const count = (state?.topics_count as number) || 0;
  const sources = (state?.sources_succeeded as string[]) || [];
  const format = (state?.format as string) || "";

  return (
    <Link
      href="/ideas"
      className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-800/50 transition-colors group"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400/60 shrink-0" />
      <span className="text-xs text-slate-300 font-medium truncate flex-1">
        {cp.displayName}
      </span>
      <span className="text-[10px] text-slate-500 shrink-0">
        {count} ideas
      </span>
      {sources.length > 0 && (
        <span className="text-[10px] text-slate-600 shrink-0">
          {sources.length}/4 sources
        </span>
      )}
      {format && !sources.length && (
        <span className="text-[10px] text-slate-600 shrink-0">
          {format}
        </span>
      )}
      <span className="text-[10px] text-slate-600 shrink-0">
        {getRelativeTime(cp.lastUpdated)}
      </span>
      <svg className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 transition-colors shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      </svg>
    </Link>
  );
}

export default function PipelineTracker({ contentProjects }: PipelineTrackerProps) {
  const production = contentProjects.filter(
    (cp) => cp.stages.research || cp.stages.video || cp.stages.thumbnail
  );
  const ideaBank = contentProjects.filter(
    (cp) => cp.stages.ideas && !cp.stages.research && !cp.stages.video && !cp.stages.thumbnail
  );

  const columnCards: Record<ColumnKey, ContentProject[]> = {
    writing: [],
    "post-prod": [],
    ready: [],
  };
  for (const cp of production) {
    columnCards[classifyProject(cp)].push(cp);
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Kanban Board */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
            In Production
          </h2>
          {production.length > 0 && (
            <span className="text-[10px] text-slate-500">
              {production.length} {production.length === 1 ? "video" : "videos"}
            </span>
          )}
        </div>

        {production.length === 0 ? (
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 text-center">
            <p className="text-xs text-slate-500">
              No videos in production. Pick an idea below or run <code className="text-indigo-400">/write</code> to start.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            {COLUMNS.map((col) => (
              <KanbanColumn key={col.key} column={col} cards={columnCards[col.key]} />
            ))}
          </div>
        )}
      </div>

      {/* Idea Bank */}
      {ideaBank.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
              Idea Bank
            </h2>
            <span className="text-[10px] text-slate-500">
              {ideaBank.length} {ideaBank.length === 1 ? "session" : "sessions"}
            </span>
          </div>
          <div className="bg-slate-900/30 border border-slate-800/50 rounded-xl divide-y divide-slate-800/50">
            {ideaBank.map((cp) => (
              <IdeaBankRow key={cp.contentSlug} cp={cp} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
