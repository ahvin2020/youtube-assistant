import { getChannelProfile, getResearchConfig, getSheetLinks } from "@/lib/channel";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const [profile, config, sheets] = await Promise.all([
    getChannelProfile(),
    getResearchConfig(),
    getSheetLinks(),
  ]);

  const hookCategories = (config?.hook_categories || {}) as Record<
    string,
    { modifier: number; terms?: string[] }
  >;
  const constants = (config?.constants || {}) as Record<string, number>;

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-slate-100">Settings</h1>
        <p className="text-sm text-slate-400 mt-1">Channel profile and system configuration</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Channel Profile */}
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 sm:p-5">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-4">
            Channel Profile
          </h2>
          {profile ? (
            <div className="space-y-3">
              {Object.entries(profile.identity).map(([key, value]) => (
                <div key={key} className="flex justify-between text-sm">
                  <span className="text-slate-400">{key}</span>
                  <span className="text-slate-200 text-right max-w-[60%] truncate">{value}</span>
                </div>
              ))}
              <div className="border-t border-slate-700 pt-3 mt-3 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Niche terms</span>
                  <span className="text-indigo-400">{profile.nicheTermsCount}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Discovery keywords</span>
                  <span className="text-emerald-400">{profile.discoveryKeywordsCount}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Cross-niche keywords</span>
                  <span className="text-pink-400">{profile.crossNicheKeywordsCount}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Monitored channels</span>
                  <span className="text-amber-400">{profile.monitoredChannelsCount}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Subreddits</span>
                  <span className="text-sky-400">{profile.subreddits.length}</span>
                </div>
              </div>
              {Object.keys(profile.performanceBaseline).length > 0 && (
                <div className="border-t border-slate-700 pt-3 mt-3 space-y-2">
                  <div className="text-xs text-slate-500 uppercase tracking-wide">Performance Baseline</div>
                  {Object.entries(profile.performanceBaseline).map(([key, value]) => (
                    <div key={key} className="flex justify-between text-sm">
                      <span className="text-slate-400">{key}</span>
                      <span className="text-slate-200 text-right max-w-[60%]">{value}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-500">Channel profile not found.</p>
          )}
        </div>

        <div className="space-y-4 sm:space-y-6">
          {/* Research Config */}
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 sm:p-5">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-4">
              Research Config
            </h2>
            {Object.keys(hookCategories).length > 0 && (
              <div className="mb-4">
                <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">Hook Modifiers</div>
                <div className="space-y-1.5">
                  {Object.entries(hookCategories)
                    .sort(([, a], [, b]) => b.modifier - a.modifier)
                    .map(([cat, data]) => (
                      <div key={cat} className="flex items-center justify-between text-sm">
                        <span className="text-slate-300 capitalize">{cat.replace(/_/g, " ")}</span>
                        <span
                          className={`font-mono text-xs ${
                            data.modifier > 0 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {data.modifier > 0 ? "+" : ""}
                          {(data.modifier * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            )}
            {Object.keys(constants).length > 0 && (
              <div>
                <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">Constants</div>
                <div className="space-y-1.5">
                  {Object.entries(constants).map(([key, value]) => (
                    <div key={key} className="flex justify-between text-sm">
                      <span className="text-slate-400">{key.replace(/_/g, " ")}</span>
                      <span className="text-slate-200 font-mono">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Connected Sheets */}
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 sm:p-5">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-4">
              Connected Sheets
            </h2>
            {sheets.length > 0 ? (
              <div className="space-y-2">
                {sheets.map((sheet) => (
                  <a
                    key={sheet.name}
                    href={sheet.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between text-sm p-2 rounded-lg hover:bg-slate-700/50 transition-colors"
                  >
                    <span className="text-slate-200">{sheet.name}</span>
                    <span className="text-emerald-400 text-xs">Open ↗</span>
                  </a>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No sheets connected yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
