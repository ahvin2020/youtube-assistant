"use client";

import { useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { runExecutor } from "@/lib/execute";
import { callClaude, readWorkspaceFile, writeWorkspaceFile } from "@/lib/analyze";
import StepIndicator from "@/components/pipeline/StepIndicator";
import StepCard from "@/components/pipeline/StepCard";
import RunButton from "@/components/pipeline/RunButton";

interface ThumbnailProject {
  slug: string;
  topic?: string;
  phase?: string;
  [key: string]: unknown;
}

interface ThumbnailWizardProps {
  projects: ThumbnailProject[];
  headshots: string[];
}

const STEPS = ["Setup", "Research", "Select References", "Generate", "Review"];

function getProjectSlug(topic: string): string {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const slug = topic.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 30);
  return `${date}_${slug}`;
}

export default function ThumbnailWizard({ projects, headshots }: ThumbnailWizardProps) {
  const searchParams = useSearchParams();
  const paramTopic = searchParams.get("topic") || "";

  const [currentStep, setCurrentStep] = useState(0);
  const [topic, setTopic] = useState(paramTopic);
  const [projectSlug, setProjectSlug] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Research state
  const [researching, setResearching] = useState(false);
  const [researchProgress, setResearchProgress] = useState("");
  const [researchResults, setResearchResults] = useState<Record<string, unknown>[]>([]);
  const [sheetUrl, setSheetUrl] = useState<string | null>(null);

  // Selection state
  const [selectedRefs, setSelectedRefs] = useState<number[]>([]);

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [genProgress, setGenProgress] = useState("");
  const [generatedImages, setGeneratedImages] = useState<string[]>([]);

  const createProject = useCallback(async () => {
    if (!topic.trim()) {
      setError("Please enter a topic");
      return;
    }
    setError(null);
    const slug = getProjectSlug(topic);
    setProjectSlug(slug);

    await writeWorkspaceFile(
      `workspace/temp/thumbnail/${slug}/state.json`,
      JSON.stringify({
        topic, slug, phase: "research", iteration: 0,
        selected_concept: null, concepts: [],
        created: new Date().toISOString().slice(0, 10),
        updated: new Date().toISOString().slice(0, 10),
      }, null, 2)
    );

    setCurrentStep(1);
  }, [topic]);

  const runResearch = useCallback(async () => {
    setResearching(true);
    setError(null);
    setResearchProgress("Running cross-niche thumbnail research...");

    try {
      const result = await runExecutor(
        "thumbnail/cross_niche_research.py",
        [
          "--channel-profile", "memory/channel-profile.md",
          "--config", "workspace/config/research_config.json",
          "--max-keywords", "6",
          "--max-channels", "8",
          "--count", "100",
          "--output", `workspace/temp/thumbnail/${projectSlug}/research/results.json`,
        ],
        "python3"
      );

      if (!result.success) {
        setError(`Research failed: ${result.stderr.slice(0, 300)}`);
        setResearching(false);
        return;
      }

      // Read results
      const data = await readWorkspaceFile(`workspace/temp/thumbnail/${projectSlug}/research/results.json`);
      if (data.content) {
        try {
          const parsed = JSON.parse(data.content);
          const items = parsed.results || parsed.videos || parsed;
          setResearchResults(Array.isArray(items) ? items.slice(0, 50) : []);
        } catch { /* ignore */ }
      }

      // Export to sheet
      setResearchProgress("Exporting to Google Sheet...");
      const sheetResult = await runExecutor(
        "thumbnail/export_research_sheet.py",
        [
          "--input", `workspace/temp/thumbnail/${projectSlug}/research/results.json`,
          "--credentials", "credentials.json",
          "--sheet-config", "workspace/config/research_sheet.json",
          "--tab-name", projectSlug,
        ],
        "python3"
      );

      if (sheetResult.success) {
        try {
          const sheetData = JSON.parse(sheetResult.stdout);
          if (sheetData.sheet_url) setSheetUrl(sheetData.sheet_url);
        } catch { /* stdout not JSON */ }
      }

      await writeWorkspaceFile(
        `workspace/temp/thumbnail/${projectSlug}/state.json`,
        JSON.stringify({
          topic, slug: projectSlug, phase: "select",
          created: new Date().toISOString().slice(0, 10),
          updated: new Date().toISOString().slice(0, 10),
        }, null, 2)
      );

      setResearchProgress("");
      setCurrentStep(2);
    } catch (err) {
      setError(`Research failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setResearching(false);
    }
  }, [projectSlug, topic]);

  const toggleRef = (index: number) => {
    setSelectedRefs((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index].slice(0, 5)
    );
  };

  const runGeneration = useCallback(async () => {
    if (selectedRefs.length === 0) {
      setError("Select at least 1 reference thumbnail");
      return;
    }
    setGenerating(true);
    setError(null);
    setGenProgress("Generating prompt engineering analysis...");

    try {
      // Get selected reference thumbnails
      const selected = selectedRefs.map((i) => researchResults[i]);

      // Use Claude to reverse-engineer prompts
      const promptResult = await callClaude(
        "claude-opus-4-20250514",
        "You are a thumbnail design expert. Analyze reference thumbnails and create generation prompts.",
        [{
          role: "user",
          content: `I'm creating a thumbnail for a YouTube video titled "${topic}".

Here are ${selected.length} reference thumbnails I want to draw inspiration from:
${selected.map((ref, i) => `${i + 1}. "${ref.title}" by ${ref.channel} (${ref.views} views, outlier: ${ref.outlier_score})`).join("\n")}

For each reference, generate a detailed Gemini image generation prompt that:
1. Captures the visual style (composition, colors, mood)
2. Adapts it for my topic "${topic}"
3. Describes "Subject Alpha" (the person in the thumbnail) using the character consistency approach
4. Includes any text overlays needed

Return a JSON array of objects with: { "ref_title": string, "prompt": string, "text_overlay": string }`,
        }],
        8192
      );

      if (!promptResult.success || !promptResult.content) {
        setError(`Prompt generation failed: ${promptResult.error || "No response"}`);
        setGenerating(false);
        return;
      }

      await writeWorkspaceFile(
        `workspace/temp/thumbnail/${projectSlug}/prompts.json`,
        promptResult.content
      );

      // If headshots available, run face replacement for each prompt
      if (headshots.length > 0) {
        setGenProgress("Running pose matching and face replacement...");

        // Match headshot first
        const matchResult = await runExecutor(
          "thumbnail/match_headshot.py",
          [
            "--headshots-dir", "workspace/input/thumbnail/headshots",
            "--target-yaw", "0",
            "--target-pitch", "0",
          ],
          "/opt/homebrew/bin/python3"
        );

        let primaryHeadshot = headshots[0];
        if (matchResult.success) {
          try {
            const matchData = JSON.parse(matchResult.stdout);
            if (matchData.best_match) primaryHeadshot = matchData.best_match;
          } catch { /* use default */ }
        }

        // Generate thumbnails using replace_face for each concept
        let prompts: { prompt: string }[] = [];
        try {
          const match = promptResult.content.match(/\[[\s\S]*\]/);
          prompts = JSON.parse(match ? match[0] : promptResult.content);
        } catch {
          prompts = [{ prompt: `A professional YouTube thumbnail for a video about ${topic}` }];
        }

        const genResults: string[] = [];
        for (let i = 0; i < Math.min(prompts.length, 5); i++) {
          setGenProgress(`Generating thumbnail ${i + 1}/${Math.min(prompts.length, 5)}...`);
          const genResult = await runExecutor(
            "thumbnail/replace_face.py",
            [
              "--headshot", `workspace/input/thumbnail/headshots/${primaryHeadshot}`,
              "--output", `workspace/temp/thumbnail/${projectSlug}/face_replaced/concept_${i}.png`,
              "--full-prompt", prompts[i].prompt,
            ],
            "/opt/homebrew/bin/python3"
          );
          if (genResult.success) {
            genResults.push(`concept_${i}.png`);
          }
        }
        setGeneratedImages(genResults);
      }

      await writeWorkspaceFile(
        `workspace/temp/thumbnail/${projectSlug}/state.json`,
        JSON.stringify({
          topic, slug: projectSlug, phase: "review",
          created: new Date().toISOString().slice(0, 10),
          updated: new Date().toISOString().slice(0, 10),
        }, null, 2)
      );

      setGenProgress("");
      setCurrentStep(4);
    } catch (err) {
      setError(`Generation failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setGenerating(false);
    }
  }, [selectedRefs, researchResults, headshots, projectSlug, topic]);

  const resumeProject = useCallback(async (project: ThumbnailProject) => {
    setProjectSlug(project.slug);
    setTopic(project.topic || "");

    const phase = project.phase || "research";
    if (phase === "research") setCurrentStep(1);
    else if (phase === "select") setCurrentStep(2);
    else if (phase === "generate") setCurrentStep(3);
    else if (phase === "review" || phase === "complete") setCurrentStep(4);
    else setCurrentStep(0);
  }, []);

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-100">Thumbnail Pipeline</h1>
          <p className="text-sm text-slate-400 mt-1">
            Research references, generate thumbnails with face replacement
          </p>
        </div>
        <div className="flex items-center gap-2">
          {sheetUrl && (
            <a href={sheetUrl} target="_blank" rel="noopener noreferrer"
              className="text-xs px-3 py-1.5 bg-emerald-400/15 text-emerald-400 rounded-lg hover:bg-emerald-400/25 transition-colors">
              Open Sheet
            </a>
          )}
          {currentStep > 0 && (
            <button onClick={() => { setCurrentStep(0); setTopic(""); setError(null); }}
              className="text-xs px-3 py-1.5 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors">
              New Project
            </button>
          )}
        </div>
      </div>

      <StepIndicator steps={STEPS} currentStep={currentStep} />

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">{error}</div>
      )}

      {/* Headshot status */}
      {currentStep === 0 && (
        <div className={`text-xs px-3 py-2 rounded-lg ${headshots.length > 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"}`}>
          {headshots.length > 0
            ? `${headshots.length} headshots available: ${headshots.join(", ")}`
            : "No headshots found in workspace/input/thumbnail/headshots/. Will generate background-only thumbnails."}
        </div>
      )}

      {/* Step 0: Setup */}
      <StepCard title="Step 1: Setup" status={currentStep > 0 ? "done" : "pending"}
        summary={currentStep > 0 ? topic : undefined} defaultExpanded={currentStep === 0}>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">Video Topic</label>
            <input type="text" value={topic} onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. CPF FRS vs ERS, DCA vs Lump Sum"
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-full placeholder:text-slate-600" />
          </div>
          <RunButton label="Start Research" onClick={createProject} />
        </div>
      </StepCard>

      {/* Step 1: Research */}
      {currentStep >= 1 && (
        <StepCard title="Step 2: Cross-Niche Research" status={researching ? "running" : currentStep > 1 ? "done" : "pending"}
          summary={currentStep > 1 ? `${researchResults.length} references found` : undefined}
          defaultExpanded={currentStep === 1}>
          <div className="space-y-3">
            {researchProgress && <div className="text-sm text-indigo-400 animate-pulse">{researchProgress}</div>}
            {!researching && currentStep === 1 && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">Search cross-niche keywords and monitored channels for high-performing thumbnail references.</p>
                <RunButton label="Run Research" onClick={runResearch} />
              </div>
            )}
          </div>
        </StepCard>
      )}

      {/* Step 2: Select References */}
      {currentStep >= 2 && (
        <StepCard title="Step 3: Select References" status={currentStep > 2 ? "done" : "pending"}
          summary={currentStep > 2 ? `${selectedRefs.length} selected` : undefined}
          defaultExpanded={currentStep === 2}>
          <div className="space-y-4">
            <p className="text-sm text-slate-400">
              {sheetUrl
                ? <>Browse the <a href={sheetUrl} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:text-indigo-300">Google Sheet</a> for full details. Select up to 5 references below.</>
                : "Select up to 5 reference thumbnails to base your concepts on."}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-96 overflow-y-auto">
              {researchResults.map((ref, i) => (
                <button key={i} onClick={() => toggleRef(i)}
                  className={`text-left p-3 rounded-lg border transition-colors ${
                    selectedRefs.includes(i)
                      ? "bg-pink-500/15 border-pink-500/30"
                      : "bg-slate-800/50 border-slate-700/50 hover:border-slate-600"
                  }`}>
                  <div className="text-xs font-medium text-slate-200 truncate">{String(ref.title || `Reference ${i + 1}`)}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{String(ref.channel || "")} — {String(ref.views || "")} views</div>
                  {ref.outlier_score ? <div className="text-[10px] text-amber-400 mt-0.5">Outlier: {String(ref.outlier_score)}x</div> : null}
                </button>
              ))}
            </div>
            {selectedRefs.length > 0 && (
              <RunButton label={`Generate from ${selectedRefs.length} Reference${selectedRefs.length > 1 ? "s" : ""}`} onClick={() => { setCurrentStep(3); runGeneration(); }} />
            )}
          </div>
        </StepCard>
      )}

      {/* Step 3: Generate */}
      {currentStep >= 3 && (
        <StepCard title="Step 4: Generate Thumbnails" status={generating ? "running" : currentStep > 3 ? "done" : "pending"}
          summary={generatedImages.length > 0 ? `${generatedImages.length} generated` : undefined}
          defaultExpanded={currentStep === 3}>
          <div className="space-y-3">
            {genProgress && <div className="text-sm text-indigo-400 animate-pulse">{genProgress}</div>}
          </div>
        </StepCard>
      )}

      {/* Step 4: Review */}
      {currentStep >= 4 && (
        <StepCard title="Step 5: Review" status={generatedImages.length > 0 ? "done" : "pending"}
          defaultExpanded={currentStep === 4}>
          <div className="space-y-4">
            {generatedImages.length > 0 ? (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">{generatedImages.length} thumbnails generated in workspace/temp/thumbnail/{projectSlug}/face_replaced/</p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {generatedImages.map((img, i) => (
                    <div key={i} className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 text-center">
                      <div className="text-sm text-slate-300">{img}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-400">Prompts generated. Check workspace/temp/thumbnail/{projectSlug}/prompts.json to review and refine.</p>
            )}
            <div className="border-t border-slate-700/50 pt-4">
              <div className="text-xs text-slate-400 uppercase tracking-wide mb-2">Next Steps</div>
              <a href={`/cut?topic=${encodeURIComponent(topic)}`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-sky-500/20 text-sky-300 border border-sky-500/30 hover:bg-sky-500/30 transition-colors">
                {"🎬"} Cut Video
              </a>
            </div>
          </div>
        </StepCard>
      )}

      {/* Previous projects */}
      {projects.length > 0 && currentStep === 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3">Previous Projects</h2>
          <div className="space-y-2">
            {projects.map((p) => (
              <div key={p.slug} className="bg-slate-900/50 border border-slate-800 rounded-lg px-4 py-3 flex items-center justify-between">
                <div>
                  <span className="text-sm text-slate-200">{p.topic || p.slug}</span>
                  <span className={`ml-2 text-xs px-2 py-0.5 rounded-full ${
                    p.phase === "complete" ? "bg-emerald-400/15 text-emerald-400" : "bg-slate-700 text-slate-400"
                  }`}>{p.phase || "unknown"}</span>
                </div>
                <button onClick={() => resumeProject(p)} className="text-xs text-indigo-400 hover:text-indigo-300">
                  {p.phase === "complete" ? "View" : "Resume"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
