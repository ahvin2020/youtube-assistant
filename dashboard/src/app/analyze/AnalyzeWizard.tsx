"use client";

import { useState, useCallback } from "react";
import { runExecutor } from "@/lib/execute";
import { callClaude, readWorkspaceFile, writeWorkspaceFile } from "@/lib/analyze";
import StepIndicator from "@/components/pipeline/StepIndicator";
import StepCard from "@/components/pipeline/StepCard";
import RunButton from "@/components/pipeline/RunButton";

interface AnalyzeProject {
  slug: string;
  mode?: string;
  phase?: string;
  [key: string]: unknown;
}

interface AnalyzeWizardProps {
  projects: AnalyzeProject[];
}

const STEPS = ["Setup", "Data Gathering", "Analysis", "Results"];

type AnalyzeMode = "full" | "deep-dive";

export default function AnalyzeWizard({ projects }: AnalyzeWizardProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [mode, setMode] = useState<AnalyzeMode>("full");
  const [videoUrl, setVideoUrl] = useState("");
  const [projectSlug, setProjectSlug] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Gathering
  const [gathering, setGathering] = useState(false);
  const [gatherProgress, setGatherProgress] = useState("");

  // Analysis
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState("");
  const [analysisResult, setAnalysisResult] = useState("");
  const [hooksCount, setHooksCount] = useState(0);

  // Export
  const [exporting, setExporting] = useState(false);
  const [sheetUrl, setSheetUrl] = useState<string | null>(null);

  const createProject = useCallback(async () => {
    if (mode === "deep-dive" && !videoUrl.trim()) {
      setError("Please enter a YouTube URL for deep-dive mode");
      return;
    }
    setError(null);

    const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    let slug: string;
    if (mode === "deep-dive") {
      const vidSlug = videoUrl.replace(/[^a-zA-Z0-9]/g, "-").slice(0, 20);
      slug = `${date}_deepdive-${vidSlug}`;
    } else {
      slug = `${date}_content-analysis`;
    }
    setProjectSlug(slug);

    await writeWorkspaceFile(
      `workspace/temp/analyze/${slug}/state.json`,
      JSON.stringify({
        phase: "gathering", mode, project: slug,
        video_url: mode === "deep-dive" ? videoUrl : null,
        created: new Date().toISOString().slice(0, 10),
      }, null, 2)
    );

    setCurrentStep(1);
  }, [mode, videoUrl]);

  const runGathering = useCallback(async () => {
    setGathering(true);
    setError(null);
    setGatherProgress("Fetching channel data (this may take a few minutes)...");

    try {
      // Read channel profile to get channel_id
      const profileData = await readWorkspaceFile("memory/channel-profile.md");
      const profile = profileData.content || "";
      const channelIdMatch = profile.match(/Channel ID[:\s]+([^\s\n]+)/i);
      const channelId = channelIdMatch ? channelIdMatch[1] : "";

      if (!channelId) {
        setError("Channel ID not found in memory/channel-profile.md. Run /analyze first to set up.");
        setGathering(false);
        return;
      }

      const args = [
        "--channel-profile", "memory/channel-profile.md",
        "--channel-id", channelId,
        "--own-count", "50",
        "--competitor-count", "20",
        "--max-channels", "15",
        "--days", "180",
        "--output", `workspace/temp/analyze/${projectSlug}/channel_data.json`,
      ];

      if (mode === "deep-dive" && videoUrl) {
        args.push("--video-url", videoUrl);
      }

      const result = await runExecutor("analyze/fetch_channel_data.py", args, "python3");

      if (!result.success) {
        setError(`Data gathering failed: ${result.stderr.slice(0, 300)}`);
        setGathering(false);
        return;
      }

      setGatherProgress("");
      setCurrentStep(2);
    } catch (err) {
      setError(`Gathering failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setGathering(false);
    }
  }, [projectSlug, mode, videoUrl]);

  const runAnalysis = useCallback(async () => {
    setAnalyzing(true);
    setError(null);
    setAnalysisProgress("Loading channel data...");
    const tempPath = `workspace/temp/analyze/${projectSlug}`;

    try {
      const [channelData, profileData, directiveData] = await Promise.all([
        readWorkspaceFile(`${tempPath}/channel_data.json`),
        readWorkspaceFile("memory/channel-profile.md"),
        readWorkspaceFile("directives/analyze/content-analysis.md"),
      ]);

      setAnalysisProgress("Analyzing channel performance with Opus...");

      const result = await callClaude(
        "claude-opus-4-20250514",
        `You are a YouTube content performance analyst. Analyze channel data and extract insights.

${(directiveData.content || "").slice(0, 4000)}

Channel Profile:
${(profileData.content || "").slice(0, 2000)}`,
        [{
          role: "user",
          content: `Analyze this channel data and produce:

1. **Performance Analysis**: Top-performing videos, patterns, what works
2. **Hook Mining**: Extract proven hooks from top videos with categories
3. **Content Gaps**: What topics are underserved
4. **Competitor Insights**: What competitors do well
5. **Recommendations**: Actionable next steps

CHANNEL DATA:
${(channelData.content || "").slice(0, 25000)}

Also produce a JSON array of mined hooks in this format:
\`\`\`hooks
[
  {
    "text": "<the hook text>",
    "category": "<question|bold_claim|story|statistic|contrarian|curiosity_gap>",
    "format": "<title|opening_line>",
    "source_video_id": "<video_id>",
    "source_channel": "<channel>",
    "views": <number>,
    "outlier_score": <number>,
    "performance_score": <0-10>
  }
]
\`\`\`

Write the analysis as markdown, then append the hooks JSON block at the end.`,
        }],
        16384
      );

      if (!result.success || !result.content) {
        setError(`Analysis failed: ${result.error || "No response"}`);
        setAnalyzing(false);
        return;
      }

      setAnalysisResult(result.content);
      await writeWorkspaceFile(`${tempPath}/analysis.md`, result.content);

      // Extract hooks and save
      const hooksMatch = result.content.match(/```hooks\n([\s\S]*?)\n```/);
      if (hooksMatch) {
        try {
          const hooks = JSON.parse(hooksMatch[1]);
          setHooksCount(hooks.length);

          // Merge with existing hooks.json
          const existingData = await readWorkspaceFile("workspace/config/hooks.json");
          let existingHooks: unknown[] = [];
          if (existingData.content) {
            try { existingHooks = JSON.parse(existingData.content); } catch { /* ignore */ }
          }

          const allHooks = [...existingHooks, ...hooks];
          await writeWorkspaceFile("workspace/config/hooks.json", JSON.stringify(allHooks, null, 2));
        } catch { /* parse error */ }
      }

      // Copy analysis to output
      await writeWorkspaceFile(
        `workspace/output/analyze/${projectSlug}/analysis.md`,
        result.content
      );

      await writeWorkspaceFile(
        `${tempPath}/state.json`,
        JSON.stringify({
          phase: "complete", mode, project: projectSlug,
          created: new Date().toISOString().slice(0, 10),
          updated: new Date().toISOString().slice(0, 10),
        }, null, 2)
      );

      setAnalysisProgress("");
      setCurrentStep(3);
    } catch (err) {
      setError(`Analysis failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setAnalyzing(false);
    }
  }, [projectSlug, mode]);

  const runExport = useCallback(async () => {
    setExporting(true);
    setError(null);
    try {
      const result = await runExecutor(
        "analyze/export_analysis_sheet.py",
        [
          "--input", `workspace/output/analyze/${projectSlug}/analysis.md`,
          "--credentials", "credentials.json",
          "--sheet-config", "workspace/config/intelligence_sheet.json",
        ],
        "python3"
      );
      if (result.success) {
        try {
          const data = JSON.parse(result.stdout);
          if (data.sheet_url) setSheetUrl(data.sheet_url);
        } catch { /* not JSON */ }
      } else {
        setError(`Export failed: ${result.stderr.slice(0, 200)}`);
      }
    } finally {
      setExporting(false);
    }
  }, [projectSlug]);

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-100">Analyze Pipeline</h1>
          <p className="text-sm text-slate-400 mt-1">Channel performance analysis, hook mining, and competitive insights</p>
        </div>
        <div className="flex items-center gap-2">
          {sheetUrl && (
            <a href={sheetUrl} target="_blank" rel="noopener noreferrer"
              className="text-xs px-3 py-1.5 bg-emerald-400/15 text-emerald-400 rounded-lg hover:bg-emerald-400/25 transition-colors">
              Open Sheet
            </a>
          )}
          {currentStep > 0 && (
            <button onClick={() => { setCurrentStep(0); setError(null); setAnalysisResult(""); }}
              className="text-xs px-3 py-1.5 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors">
              New Analysis
            </button>
          )}
        </div>
      </div>

      <StepIndicator steps={STEPS} currentStep={currentStep} />

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">{error}</div>
      )}

      {/* Step 0: Setup */}
      <StepCard title="Step 1: Setup" status={currentStep > 0 ? "done" : "pending"}
        summary={currentStep > 0 ? `Mode: ${mode}` : undefined} defaultExpanded={currentStep === 0}>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">Analysis Mode</label>
            <div className="flex gap-3">
              <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                <input type="radio" name="mode" value="full" checked={mode === "full"}
                  onChange={() => setMode("full")} className="accent-indigo-500" />
                Full Channel Analysis
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                <input type="radio" name="mode" value="deep-dive" checked={mode === "deep-dive"}
                  onChange={() => setMode("deep-dive")} className="accent-indigo-500" />
                Deep-Dive (specific video)
              </label>
            </div>
          </div>
          {mode === "deep-dive" && (
            <div>
              <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">YouTube Video URL</label>
              <input type="text" value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-full placeholder:text-slate-600" />
            </div>
          )}
          <RunButton label="Start Analysis" onClick={createProject} />
        </div>
      </StepCard>

      {/* Step 1: Data Gathering */}
      {currentStep >= 1 && (
        <StepCard title="Step 2: Data Gathering" status={gathering ? "running" : currentStep > 1 ? "done" : "pending"}
          defaultExpanded={currentStep === 1}>
          <div className="space-y-3">
            {gatherProgress && <div className="text-sm text-indigo-400 animate-pulse">{gatherProgress}</div>}
            {!gathering && currentStep === 1 && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">Fetch your channel data and competitor videos for analysis.</p>
                <RunButton label="Gather Data" onClick={runGathering} />
              </div>
            )}
          </div>
        </StepCard>
      )}

      {/* Step 2: Analysis */}
      {currentStep >= 2 && (
        <StepCard title="Step 3: AI Analysis" status={analyzing ? "running" : currentStep > 2 ? "done" : "pending"}
          summary={hooksCount > 0 ? `${hooksCount} hooks mined` : undefined} defaultExpanded={currentStep === 2}>
          <div className="space-y-3">
            {analysisProgress && <div className="text-sm text-indigo-400 animate-pulse">{analysisProgress}</div>}
            {!analyzing && currentStep === 2 && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">Claude Opus will analyze performance, mine hooks, and generate recommendations.</p>
                <RunButton label="Analyze (Opus)" onClick={runAnalysis} />
              </div>
            )}
          </div>
        </StepCard>
      )}

      {/* Step 3: Results */}
      {currentStep >= 3 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">Analysis Results</h2>
            <div className="flex gap-2">
              {!sheetUrl && (
                <RunButton label={exporting ? "Exporting..." : "Export to Sheet"} onClick={runExport}
                  loading={exporting} variant="secondary" />
              )}
            </div>
          </div>

          {analysisResult && (
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 sm:p-6 text-sm text-slate-300 whitespace-pre-line max-h-[600px] overflow-y-auto">
              {analysisResult.replace(/```hooks[\s\S]*?```/, "").trim()}
            </div>
          )}

          {hooksCount > 0 && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4 text-sm text-emerald-400">
              {hooksCount} hooks mined and saved to workspace/config/hooks.json
            </div>
          )}

          <div className="border-t border-slate-700/50 pt-4">
            <div className="text-xs text-slate-400 uppercase tracking-wide mb-2">Next Steps</div>
            <a href="/idea"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30 transition-colors">
              {"💡"} Discover Ideas
            </a>
          </div>
        </div>
      )}

      {/* Previous projects */}
      {projects.length > 0 && currentStep === 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3">Previous Analyses</h2>
          <div className="space-y-2">
            {projects.map((p) => (
              <div key={p.slug} className="bg-slate-900/50 border border-slate-800 rounded-lg px-4 py-3 flex items-center justify-between">
                <div>
                  <span className="text-sm text-slate-200">{p.slug}</span>
                  <span className="ml-2 text-xs text-slate-500">{p.mode}</span>
                  <span className={`ml-2 text-xs px-2 py-0.5 rounded-full ${
                    p.phase === "complete" ? "bg-emerald-400/15 text-emerald-400" : "bg-slate-700 text-slate-400"
                  }`}>{p.phase || "unknown"}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
