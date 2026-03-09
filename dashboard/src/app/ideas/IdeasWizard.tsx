"use client";

import { useState, useCallback } from "react";
import { Topic } from "@/lib/types";
import { runExecutor, ExecuteResult } from "@/lib/execute";
import { callClaude, readWorkspaceFile, writeWorkspaceFile } from "@/lib/analyze";
import StepIndicator from "@/components/pipeline/StepIndicator";
import StepCard from "@/components/pipeline/StepCard";
import RunButton from "@/components/pipeline/RunButton";
import IdeaCard from "./IdeaCard";

interface IdeasWizardProps {
  existingIdeas: Topic[];
  existingSheetUrl: string | null;
  projects: { slug: string; phase?: string; [key: string]: unknown }[];
}

type SourceStatus = "idle" | "running" | "done" | "error";

interface GatheringState {
  youtube: SourceStatus;
  trends: SourceStatus;
  reddit: SourceStatus;
  twitter: SourceStatus;
  youtubeResult?: ExecuteResult;
  trendsResult?: ExecuteResult;
  redditResult?: ExecuteResult;
  twitterResult?: ExecuteResult;
}

const STEPS = ["Configure", "Data Gathering", "Analysis", "Results"];

function getProjectSlug(hint?: string): string {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const suffix = hint
    ? hint.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 30)
    : "idea-discovery";
  return `${date}_${suffix}`;
}

export default function IdeasWizard({ existingIdeas, existingSheetUrl, projects }: IdeasWizardProps) {
  const [currentStep, setCurrentStep] = useState(existingIdeas.length > 0 ? 3 : 0);
  const [format, setFormat] = useState("both");
  const [topicHint, setTopicHint] = useState("");
  const [projectSlug, setProjectSlug] = useState("");
  const [gathering, setGathering] = useState<GatheringState>({
    youtube: "idle", trends: "idle", reddit: "idle", twitter: "idle",
  });
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState("");
  const [ideas, setIdeas] = useState<Topic[]>(existingIdeas);
  const [sheetUrl, setSheetUrl] = useState(existingSheetUrl);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const startNewDiscovery = () => {
    setCurrentStep(0);
    setIdeas([]);
    setSheetUrl(null);
    setError(null);
    setGathering({ youtube: "idle", trends: "idle", reddit: "idle", twitter: "idle" });
  };

  const runGathering = useCallback(async () => {
    const slug = getProjectSlug(topicHint || undefined);
    setProjectSlug(slug);
    setCurrentStep(1);
    setError(null);

    const tempPath = `workspace/temp/ideas/${slug}`;

    // Write initial state
    await writeWorkspaceFile(
      `${tempPath}/state.json`,
      JSON.stringify({ phase: "gathering", format, project: slug, created: new Date().toISOString() })
    );

    const sources: {
      key: keyof GatheringState;
      executor: string;
      python: string;
      args: string[];
    }[] = [
      {
        key: "youtube",
        executor: "ideas/youtube_ideas.py",
        python: "python3",
        args: [
          "--channel-profile", "memory/channel-profile.md",
          "--format", format,
          "--max-channels", "15", "--max-keywords", "10", "--days", "90",
          ...(topicHint ? ["--topic-hint", topicHint] : []),
          "--output", `${tempPath}/youtube_data.json`,
        ],
      },
      {
        key: "trends",
        executor: "ideas/google_trends_ideas.py",
        python: "/opt/homebrew/bin/python3",
        args: [
          "--channel-profile", "memory/channel-profile.md",
          "--region", "SG", "--max-keywords", "15",
          "--output", `${tempPath}/trends_data.json`,
        ],
      },
      {
        key: "reddit",
        executor: "ideas/reddit_ideas.py",
        python: "python3",
        args: [
          "--channel-profile", "memory/channel-profile.md",
          "--timeframe", "month", "--max-posts", "25", "--max-subs", "8",
          "--output", `${tempPath}/reddit_data.json`,
        ],
      },
      {
        key: "twitter",
        executor: "ideas/twitter_ideas.py",
        python: "/opt/homebrew/bin/python3",
        args: [
          "--channel-profile", "memory/channel-profile.md",
          "--max-tweets", "20", "--max-terms", "10",
          "--output", `${tempPath}/twitter_data.json`,
        ],
      },
    ];

    // Set all to running
    setGathering({
      youtube: "running", trends: "running", reddit: "running", twitter: "running",
    });

    // Run all in parallel
    const promises = sources.map(async (src) => {
      try {
        const result = await runExecutor(src.executor, src.args, src.python);
        setGathering((prev) => ({
          ...prev,
          [src.key]: result.success ? "done" : "error",
          [`${src.key}Result`]: result,
        }));
        return { key: src.key, result };
      } catch (err) {
        setGathering((prev) => ({
          ...prev,
          [src.key]: "error",
        }));
        return { key: src.key, result: { success: false, stdout: "", stderr: String(err) } };
      }
    });

    const results = await Promise.all(promises);

    // YouTube is required
    const ytResult = results.find((r) => r.key === "youtube");
    if (!ytResult?.result.success) {
      setError("YouTube data gathering failed (required). Check yt-dlp installation.");
      return;
    }

    // Update state
    const succeeded = results.filter((r) => r.result.success).map((r) => r.key);
    const failed = results.filter((r) => !r.result.success).map((r) => r.key);
    await writeWorkspaceFile(
      `${tempPath}/state.json`,
      JSON.stringify({
        phase: "analyzing",
        format,
        project: slug,
        created: new Date().toISOString(),
        updated: new Date().toISOString(),
        sources_succeeded: succeeded,
        sources_failed: failed,
      })
    );

    setCurrentStep(2);
  }, [format, topicHint]);

  const runAnalysis = useCallback(async () => {
    setAnalyzing(true);
    setError(null);
    const tempPath = `workspace/temp/ideas/${projectSlug}`;

    try {
      // Read raw data files
      setAnalysisProgress("Loading raw data...");
      const [ytData, trendsData, redditData, twitterData, profileData] = await Promise.all([
        readWorkspaceFile(`${tempPath}/youtube_data.json`),
        readWorkspaceFile(`${tempPath}/trends_data.json`),
        readWorkspaceFile(`${tempPath}/reddit_data.json`),
        readWorkspaceFile(`${tempPath}/twitter_data.json`),
        readWorkspaceFile("memory/channel-profile.md"),
      ]);

      // Trim data for token efficiency
      const trimYt = (raw: string) => {
        try {
          const data = JSON.parse(raw);
          const videos = (data.videos || data).slice(0, 50);
          return JSON.stringify(videos.map((v: Record<string, unknown>) => ({
            title: v.title, channel: v.channel, views: v.views,
            outlier_score: v.outlier_score, upload_date: v.upload_date, duration: v.duration,
          })));
        } catch { return raw; }
      };

      const trimReddit = (raw: string) => {
        try {
          const data = JSON.parse(raw);
          const posts = (data.posts || data).slice(0, 50);
          return JSON.stringify(posts.map((p: Record<string, unknown>) => ({
            title: p.title, subreddit: p.subreddit, score: p.score,
            num_comments: p.num_comments, selftext_preview: p.selftext_preview,
          })));
        } catch { return raw; }
      };

      const trimTwitter = (raw: string) => {
        try {
          const data = JSON.parse(raw);
          const tweets = (data.tweets || data).slice(0, 30);
          return JSON.stringify(tweets.map((t: Record<string, unknown>) => ({
            text: t.text, author_handle: t.author_handle, likes: t.likes,
            retweets: t.retweets, replies: t.replies, search_term: t.search_term,
          })));
        } catch { return raw; }
      };

      const youtube = ytData.content ? trimYt(ytData.content) : "[]";
      const trends = trendsData.content || "[]";
      const reddit = redditData.content ? trimReddit(redditData.content) : "[]";
      const twitter = twitterData.content ? trimTwitter(twitterData.content) : "[]";
      const profile = profileData.content || "";

      // Pass 1: Sonnet — cluster & score
      setAnalysisProgress("Pass 1: Clustering and scoring ideas (Sonnet)...");
      const pass1 = await callClaude(
        "claude-sonnet-4-20250514",
        `You are a content strategy analyst for a personal finance YouTube channel. Analyze raw data from multiple sources and produce a scored topic list.

Channel Profile:
${profile}

Format: ${format}`,
        [{
          role: "user",
          content: `Analyze these data sources and produce a JSON array of scored ideas.

YOUTUBE DATA (top videos by outlier score):
${youtube}

GOOGLE TRENDS DATA:
${trends}

REDDIT DATA (top posts):
${reddit}

TWITTER DATA (top tweets):
${twitter}

Instructions:
1. Extract topic signals from each source. A "topic" = an addressable content idea, not a specific video.
2. Cluster similar ideas. Merge ideas sharing 2+ keywords and same intent.
3. Score each topic 0-10 for both LF (long-form) and Shorts.
   - LF weights: discussion depth (Reddit) 30%, search demand 25%, competitor validation 25%, content gap 15%, trend momentum 5%
   - Shorts weights: trend velocity 35%, virality 25%, hook potential 20%, shareability 10%, competitor shorts 10%
4. For each topic output: topic, lf_score, shorts_score, format_rec (Long/Short/Both), trend (Rising/Stable/Viral/Declining), sources, evidence (1-line), gap_status (Uncovered/Partially covered/Covered)

Output ONLY a valid JSON array of up to 50 ideas, sorted by source breadth then score. No markdown, no explanation.`,
        }],
        8192
      );

      if (!pass1.success || !pass1.content) {
        setError(`Sonnet analysis failed: ${pass1.error || "No response"}`);
        setAnalyzing(false);
        return;
      }

      // Parse scored ideas
      let scoredTopics: Topic[];
      try {
        const jsonMatch = pass1.content.match(/\[[\s\S]*\]/);
        scoredTopics = JSON.parse(jsonMatch ? jsonMatch[0] : pass1.content);
      } catch {
        setError("Failed to parse Sonnet scoring output as JSON");
        setAnalyzing(false);
        return;
      }

      await writeWorkspaceFile(`${tempPath}/ideas_scored.json`, JSON.stringify(scoredTopics, null, 2));

      // Pass 2: Opus — enrich top 40
      setAnalysisProgress(`Pass 2: Enriching top ${Math.min(40, scoredTopics.length)} ideas (Opus)...`);
      const top40 = scoredTopics.slice(0, 40);

      const pass2 = await callClaude(
        "claude-opus-4-20250514",
        `You are a content strategy analyst. Enrich pre-scored ideas with deep analysis for a personal finance YouTube channel.

Channel Profile:
${profile}`,
        [{
          role: "user",
          content: `Enrich these ${top40.length} pre-scored ideas. For each topic, ADD these fields while keeping all existing fields unchanged:
- why_it_works: 2-3 sentences citing specific evidence
- suggested_angle: tailored to this channel's audience
- hook_ideas: 2-3 title/hook ideas (newline-separated)
- research_more: channels, subreddits, search terms to explore further

Input ideas:
${JSON.stringify(top40)}

Output ONLY a valid JSON array with all original fields plus the 4 new fields. No markdown, no explanation.`,
        }],
        16384
      );

      if (!pass2.success || !pass2.content) {
        // Fall back to scored ideas without enrichment
        setIdeas(scoredTopics);
        setError(`Opus enrichment failed (using scored ideas without enrichment): ${pass2.error || "No response"}`);
      } else {
        try {
          const jsonMatch = pass2.content.match(/\[[\s\S]*\]/);
          const enriched = JSON.parse(jsonMatch ? jsonMatch[0] : pass2.content);
          setIdeas(enriched);
          await writeWorkspaceFile(`${tempPath}/ideas_analysis.json`, JSON.stringify(enriched, null, 2));

          // Copy to output
          await writeWorkspaceFile(
            `workspace/output/ideas/${projectSlug}/ideas_analysis.json`,
            JSON.stringify(enriched, null, 2)
          );
        } catch {
          setIdeas(scoredTopics);
          setError("Failed to parse Opus enrichment output. Using scored ideas.");
        }
      }

      // Update state
      await writeWorkspaceFile(
        `${tempPath}/state.json`,
        JSON.stringify({
          phase: "complete",
          format,
          project: projectSlug,
          created: new Date().toISOString(),
          updated: new Date().toISOString(),
          ideas_count: ideas.length,
        })
      );

      setAnalysisProgress("");
      setCurrentStep(3);
    } catch (err) {
      setError(`Analysis failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setAnalyzing(false);
    }
  }, [projectSlug, format, ideas.length]);

  const runExport = useCallback(async () => {
    if (!projectSlug) return;
    setExporting(true);
    setError(null);
    try {
      const result = await runExecutor(
        "ideas/export_ideas_sheet.py",
        [
          "--input", `workspace/temp/ideas/${projectSlug}/ideas_analysis.json`,
          "--credentials", "credentials.json",
          "--sheet-config", "workspace/config/intelligence_sheet.json",
        ],
        "python3"
      );
      if (result.success) {
        try {
          const data = JSON.parse(result.stdout);
          if (data.sheet_url) setSheetUrl(data.sheet_url);
        } catch { /* stdout might not be JSON */ }
      } else {
        setError(`Sheet export failed: ${result.stderr.slice(0, 200)}`);
      }
    } finally {
      setExporting(false);
    }
  }, [projectSlug]);

  const sourceLabel = (status: SourceStatus) => {
    switch (status) {
      case "idle": return { text: "Waiting", cls: "text-slate-500" };
      case "running": return { text: "Running...", cls: "text-indigo-400 animate-pulse" };
      case "done": return { text: "Done", cls: "text-emerald-400" };
      case "error": return { text: "Failed", cls: "text-red-400" };
    }
  };

  return (
    <div className="p-4 sm:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-100">Idea Discovery</h1>
          <p className="text-sm text-slate-400 mt-1">
            Find trending content opportunities from multiple sources
          </p>
        </div>
        <div className="flex items-center gap-2">
          {sheetUrl && (
            <a
              href={sheetUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs px-3 py-1.5 bg-emerald-400/15 text-emerald-400 rounded-lg hover:bg-emerald-400/25 transition-colors"
            >
              Open Sheet
            </a>
          )}
          {currentStep > 0 && (
            <button
              onClick={startNewDiscovery}
              className="text-xs px-3 py-1.5 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors"
            >
              New Discovery
            </button>
          )}
        </div>
      </div>

      {/* Step indicator */}
      <StepIndicator steps={STEPS} currentStep={currentStep} />

      {/* Error banner */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Step 0: Configure */}
      <StepCard
        title="Step 1: Configure"
        status={currentStep > 0 ? "done" : "pending"}
        summary={`Format: ${format}${topicHint ? `, Hint: ${topicHint}` : ""}`}
        defaultExpanded={currentStep === 0}
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">Format</label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-full sm:w-auto"
            >
              <option value="both">Both (Long-form + Shorts)</option>
              <option value="longform">Long-form only</option>
              <option value="shorts">Shorts only</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">
              Topic Hint (optional)
            </label>
            <input
              type="text"
              value={topicHint}
              onChange={(e) => setTopicHint(e.target.value)}
              placeholder="e.g. CPF, robo-advisors, REITs"
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-full sm:w-96 placeholder:text-slate-600"
            />
          </div>
          <RunButton label="Run Discovery" onClick={runGathering} />
        </div>
      </StepCard>

      {/* Step 1: Data Gathering */}
      {currentStep >= 1 && (
        <StepCard
          title="Step 2: Data Gathering"
          status={
            currentStep > 1 ? "done" :
            Object.values(gathering).some((v) => v === "running") ? "running" :
            Object.values(gathering).some((v) => v === "error") && gathering.youtube === "error" ? "error" :
            "done"
          }
          summary={`${Object.values(gathering).filter((v) => v === "done").length}/4 sources collected`}
          defaultExpanded={currentStep === 1}
        >
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {(["youtube", "trends", "reddit", "twitter"] as const).map((src) => {
              const status = gathering[src];
              const label = sourceLabel(status);
              const names = { youtube: "YouTube", trends: "Google Trends", reddit: "Reddit", twitter: "Twitter" };
              return (
                <div key={src} className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3">
                  <div className="text-xs font-medium text-slate-300 mb-1">{names[src]}</div>
                  <div className={`text-xs ${label.cls}`}>{label.text}</div>
                </div>
              );
            })}
          </div>
        </StepCard>
      )}

      {/* Step 2: Analysis */}
      {currentStep >= 2 && (
        <StepCard
          title="Step 3: AI Analysis"
          status={analyzing ? "running" : currentStep > 2 ? "done" : "pending"}
          summary={ideas.length > 0 ? `${ideas.length} ideas analyzed` : undefined}
          defaultExpanded={currentStep === 2}
        >
          <div className="space-y-3">
            {analysisProgress && (
              <div className="text-sm text-indigo-400 animate-pulse">{analysisProgress}</div>
            )}
            {!analyzing && currentStep === 2 && (
              <RunButton label="Analyze Topics" onClick={runAnalysis} />
            )}
          </div>
        </StepCard>
      )}

      {/* Step 3: Results */}
      {currentStep >= 3 && ideas.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
              {ideas.length} Ideas Discovered
            </h2>
            <div className="flex gap-2">
              {!sheetUrl && projectSlug && (
                <RunButton
                  label={exporting ? "Exporting..." : "Export to Sheet"}
                  onClick={runExport}
                  loading={exporting}
                  variant="secondary"
                />
              )}
            </div>
          </div>
          <div className="space-y-4">
            {ideas.map((topic, i) => (
              <IdeaCard key={i} topic={topic} rank={i + 1} />
            ))}
          </div>
        </div>
      )}

      {/* Previous runs */}
      {projects.length > 0 && currentStep === 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3">
            Previous Runs
          </h2>
          <div className="space-y-2">
            {projects.map((p) => (
              <div
                key={p.slug}
                className="bg-slate-900/50 border border-slate-800 rounded-lg px-4 py-3 flex items-center justify-between"
              >
                <div>
                  <span className="text-sm text-slate-200">{p.slug}</span>
                  <span className={`ml-2 text-xs px-2 py-0.5 rounded-full ${
                    p.phase === "complete" ? "bg-emerald-400/15 text-emerald-400" : "bg-slate-700 text-slate-400"
                  }`}>
                    {String(p.phase || "unknown")}
                  </span>
                </div>
                {p.phase === "complete" && (
                  <button
                    onClick={async () => {
                      const result = await readWorkspaceFile(
                        `workspace/output/ideas/${p.slug}/ideas_analysis.json`
                      );
                      if (result.content) {
                        try {
                          setIdeas(JSON.parse(result.content));
                          setProjectSlug(p.slug);
                          setCurrentStep(3);
                        } catch { /* parse error */ }
                      }
                    }}
                    className="text-xs text-indigo-400 hover:text-indigo-300"
                  >
                    View Results
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
