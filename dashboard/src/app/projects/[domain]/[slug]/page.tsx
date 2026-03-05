import { getProjectDetail } from "@/lib/workspace";
import { Domain, DOMAIN_PHASES, DOMAIN_ICONS, DOMAIN_COLORS } from "@/lib/types";
import Link from "next/link";

export const dynamic = "force-dynamic";

const DOT_COLORS: Record<string, string> = {
  indigo: "bg-indigo-400",
  pink: "bg-pink-400",
  emerald: "bg-emerald-400",
  amber: "bg-amber-400",
  sky: "bg-sky-400",
};

const BADGE_BG: Record<string, string> = {
  indigo: "bg-indigo-400/15 text-indigo-400",
  pink: "bg-pink-400/15 text-pink-400",
  emerald: "bg-emerald-400/15 text-emerald-400",
  amber: "bg-amber-400/15 text-amber-400",
  sky: "bg-sky-400/15 text-sky-400",
};

interface Props {
  params: Promise<{ domain: string; slug: string }>;
}

export default async function ProjectDetailPage({ params }: Props) {
  const { domain, slug } = await params;
  const detail = await getProjectDetail(domain as Domain, slug);
  const phases = DOMAIN_PHASES[domain as Domain] || [];
  const color = DOMAIN_COLORS[domain as Domain] || "indigo";
  const icon = DOMAIN_ICONS[domain as Domain] || "";
  const currentPhase = detail.state?.phase || "unknown";
  const phaseIndex = phases.indexOf(currentPhase);

  const displayName = (detail.state?.topic as string) ||
    slug.replace(/^\d{8}_/, "").split(/[-_]/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");

  // Filter state keys for display
  const stateEntries = detail.state
    ? Object.entries(detail.state).filter(
        ([k]) => !["phase", "slug"].includes(k) && typeof detail.state![k] !== "object"
      )
    : [];

  const isImage = (f: string) => /\.(png|jpg|jpeg|gif|webp)$/i.test(f);

  return (
    <div className="p-4 sm:p-6 space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Link href="/" className="hover:text-slate-200">Home</Link>
        <span>/</span>
        <Link href="/projects" className="hover:text-slate-200">Projects</Link>
        <span>/</span>
        <span className="text-slate-200 truncate">{displayName}</span>
      </div>

      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl">{icon}</span>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-100">{displayName}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${BADGE_BG[color]}`}>
            {domain}
          </span>
          {detail.state?.format != null && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-300 capitalize">
              {String(detail.state.format)}
            </span>
          )}
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${
            currentPhase === "complete" ? "bg-emerald-400/15 text-emerald-400" : "bg-sky-400/15 text-sky-400"
          }`}>
            {currentPhase}
          </span>
        </div>
      </div>

      {/* Phase Timeline */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 sm:p-5">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-4">Phase Timeline</h2>
        <div className="flex items-center justify-between">
          {phases.map((phase, i) => {
            const isDone = i <= phaseIndex;
            const isCurrent = phase === currentPhase;
            return (
              <div key={phase} className="flex items-center flex-1">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-4 h-4 rounded-full ${
                      isCurrent
                        ? `${DOT_COLORS[color]} ring-4 ring-${color}-400/20 animate-pulse`
                        : isDone
                        ? DOT_COLORS[color]
                        : "bg-slate-600"
                    }`}
                  />
                  <span className={`text-xs mt-1.5 capitalize ${isCurrent ? "text-slate-100 font-medium" : "text-slate-500"}`}>
                    {phase}
                  </span>
                </div>
                {i < phases.length - 1 && (
                  <div className={`flex-1 h-0.5 mx-2 ${isDone ? DOT_COLORS[color] : "bg-slate-600"}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Two column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* Left: Output Files */}
        <div className="lg:col-span-2 space-y-4">
          {/* Output files */}
          {detail.outputFiles.length > 0 && (
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 sm:p-5">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3">
                Output Files
              </h2>
              <div className="space-y-2">
                {detail.outputFiles.map((file) => (
                  <div key={file} className="flex items-center gap-2 text-sm">
                    <span className="text-slate-500">{isImage(file) ? "🖼" : "📄"}</span>
                    <span className="text-slate-200">{file}</span>
                  </div>
                ))}
              </div>

              {/* Image previews */}
              {detail.outputFiles.some(isImage) && (
                <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {detail.outputFiles.filter(isImage).map((file) => (
                    <div key={file} className="bg-slate-700/50 rounded-lg overflow-hidden border border-slate-600/50">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`/api/files/${domain}/${slug}/${file}`}
                        alt={file}
                        className="w-full h-auto"
                      />
                      <div className="px-2 py-1 text-xs text-slate-400 truncate">{file}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Temp files */}
          {detail.tempFiles.length > 0 && (
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 sm:p-5">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3">
                Temp Files
              </h2>
              <div className="space-y-1">
                {detail.tempFiles.map((file) => (
                  <div key={file} className="text-xs text-slate-500">{file}</div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: State + Links */}
        <div className="space-y-4">
          {/* State */}
          {stateEntries.length > 0 && (
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 sm:p-5">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3">State</h2>
              <div className="space-y-2">
                {stateEntries.map(([key, value]) => (
                  <div key={key} className="flex justify-between text-sm">
                    <span className="text-slate-400 capitalize">{key.replace(/_/g, " ")}</span>
                    <span className="text-slate-200 text-right max-w-[60%] truncate">
                      {String(value ?? "—")}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Links */}
          {detail.state?.sheet_url && (
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 sm:p-5">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3">Links</h2>
              <a
                href={String(detail.state.sheet_url)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-emerald-400 hover:text-emerald-300"
              >
                📊 Open Google Sheet ↗
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
