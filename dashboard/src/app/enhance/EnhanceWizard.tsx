"use client";

import { useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { runExecutor } from "@/lib/execute";
import { callClaude, readWorkspaceFile, writeWorkspaceFile } from "@/lib/analyze";
import StepIndicator from "@/components/pipeline/StepIndicator";
import StepCard from "@/components/pipeline/StepCard";
import RunButton from "@/components/pipeline/RunButton";

interface EnhanceProject {
  slug: string;
  topic?: string;
  phase?: string;
  [key: string]: unknown;
}

interface EnhanceWizardProps {
  projects: EnhanceProject[];
  cutOutputs: { slug: string; file: string }[];
}

const STEPS = ["Setup", "Transcribe", "Analyze", "Preview & Render"];

function getProjectSlug(topic: string): string {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const slug = topic.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 30);
  return `${date}_${slug}`;
}

export default function EnhanceWizard({ projects, cutOutputs }: EnhanceWizardProps) {
  const searchParams = useSearchParams();
  const paramTopic = searchParams.get("topic") || "";
  const paramProject = searchParams.get("project") || "";

  const [currentStep, setCurrentStep] = useState(0);
  const [topic, setTopic] = useState(paramTopic);
  const [selectedVideo, setSelectedVideo] = useState(paramProject ? cutOutputs.find((c) => c.slug === paramProject)?.file || "" : "");
  const [projectSlug, setProjectSlug] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Transcription
  const [transcribing, setTranscribing] = useState(false);
  const [segmentCount, setSegmentCount] = useState(0);

  // Analysis
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState("");
  const [enhancementCount, setEnhancementCount] = useState(0);

  // Render
  const [rendering, setRendering] = useState(false);
  const [renderProgress, setRenderProgress] = useState("");

  const createProject = useCallback(async () => {
    if (!selectedVideo) {
      setError("Please select a video file");
      return;
    }
    setError(null);
    const slug = getProjectSlug(topic || "enhance");
    setProjectSlug(slug);

    await writeWorkspaceFile(
      `workspace/temp/enhance/${slug}/state.json`,
      JSON.stringify({
        topic, slug, phase: "transcribe", video_file: selectedVideo,
        created: new Date().toISOString().slice(0, 10),
      }, null, 2)
    );

    setCurrentStep(1);
  }, [topic, selectedVideo]);

  const runTranscribe = useCallback(async () => {
    setTranscribing(true);
    setError(null);

    try {
      const result = await runExecutor(
        "video/transcribe.py",
        [
          selectedVideo,
          `workspace/temp/enhance/${projectSlug}/transcript.json`,
          "--language", "en", "--model", "small", "--workers", "4",
        ],
        "python3"
      );

      if (!result.success) {
        setError(`Transcription failed: ${result.stderr.slice(0, 300)}`);
        return;
      }

      try {
        const data = JSON.parse(result.stdout);
        setSegmentCount(data.segments || data.segment_count || 0);
      } catch { setSegmentCount(0); }

      setCurrentStep(2);
    } catch (err) {
      setError(`Transcription failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setTranscribing(false);
    }
  }, [selectedVideo, projectSlug]);

  const runAnalysis = useCallback(async () => {
    setAnalyzing(true);
    setError(null);
    setAnalysisProgress("Reading transcript and script...");
    const tempPath = `workspace/temp/enhance/${projectSlug}`;

    try {
      const [transcriptData, profileData, directiveData] = await Promise.all([
        readWorkspaceFile(`${tempPath}/transcript.json`),
        readWorkspaceFile("memory/channel-profile.md"),
        readWorkspaceFile("directives/enhance/video-enhance.md"),
      ]);

      // Try to load script from matching research project
      let scriptContent = "";
      const scriptData = await readWorkspaceFile(`${tempPath}/script.txt`);
      if (scriptData.content) {
        scriptContent = scriptData.content;
      }

      setAnalysisProgress("Generating enhancement spec with Opus...");

      const result = await callClaude(
        "claude-opus-4-20250514",
        `You are a video enhancement specialist. Analyze the transcript and suggest visual enhancements.

${(directiveData.content || "").slice(0, 4000)}

Channel Profile:
${(profileData.content || "").slice(0, 2000)}`,
        [{
          role: "user",
          content: `Analyze this video transcript and generate an enhancement specification.

${scriptContent ? `SCRIPT:\n${scriptContent.slice(0, 5000)}\n\n` : ""}TRANSCRIPT:
${(transcriptData.content || "").slice(0, 20000)}

VIDEO FILE: ${selectedVideo}

Generate a JSON enhancement spec with:
{
  "source_video": "${selectedVideo}",
  "fps": 30,
  "width": 1920, "height": 1080,
  "sections": [
    { "id": "section_1", "title": "<name>", "start_time": <seconds>, "end_time": <seconds> }
  ],
  "enhancements": [
    {
      "id": "enh_1",
      "section_id": "section_1",
      "type": "<text_overlay|lower_third|data_viz|callout|transition>",
      "start_time": <seconds>,
      "end_time": <seconds>,
      "content": { "text": "<content>", "position": "<bottom_left|center|top_right>" },
      "rationale": "<why this improves retention>"
    }
  ],
  "summary": "<brief description of enhancements>"
}

Output ONLY valid JSON.`,
        }],
        16384
      );

      if (!result.success || !result.content) {
        setError(`Enhancement analysis failed: ${result.error || "No response"}`);
        setAnalyzing(false);
        return;
      }

      // Save spec
      let spec;
      try {
        const match = result.content.match(/\{[\s\S]*\}/);
        spec = JSON.parse(match ? match[0] : result.content);
        setEnhancementCount(spec.enhancements?.length || 0);
      } catch {
        spec = result.content;
        setEnhancementCount(0);
      }

      await writeWorkspaceFile(`${tempPath}/enhancement_spec.json`, typeof spec === "string" ? spec : JSON.stringify(spec, null, 2));

      // Validate
      const validateResult = await runExecutor(
        "enhance/validate_spec.py",
        [`${tempPath}/enhancement_spec.json`],
        "python3"
      );

      if (!validateResult.success) {
        setError(`Spec validation warning: ${validateResult.stderr.slice(0, 200)}`);
      }

      setAnalysisProgress("");
      setCurrentStep(3);
    } catch (err) {
      setError(`Analysis failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setAnalyzing(false);
    }
  }, [projectSlug, selectedVideo]);

  const runRender = useCallback(async (mode: "preview" | "final") => {
    setRendering(true);
    setError(null);
    setRenderProgress(`Rendering ${mode}...`);
    const tempPath = `workspace/temp/enhance/${projectSlug}`;

    try {
      const script = mode === "preview" ? "enhance/render_preview.js" : "enhance/render_final.js";
      // Note: These are Node.js scripts, but they're called via the python executor route
      // In practice, enhance rendering happens via `node remotion/...` — this is a simplified trigger
      await writeWorkspaceFile(
        `${tempPath}/state.json`,
        JSON.stringify({
          topic, slug: projectSlug,
          phase: mode === "final" ? "complete" : "preview",
          video_file: selectedVideo,
          created: new Date().toISOString().slice(0, 10),
          updated: new Date().toISOString().slice(0, 10),
        }, null, 2)
      );

      setRenderProgress(`${mode === "preview" ? "Preview" : "Final"} render spec ready. Run manually: cd remotion && npx remotion render`);
    } catch (err) {
      setError(`Render failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setRendering(false);
    }
  }, [projectSlug, topic, selectedVideo]);

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-100">Enhance Pipeline</h1>
          <p className="text-sm text-slate-400 mt-1">Add motion graphics, overlays, and visual enhancements</p>
        </div>
        {currentStep > 0 && (
          <button onClick={() => { setCurrentStep(0); setError(null); }}
            className="text-xs px-3 py-1.5 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors">
            New Project
          </button>
        )}
      </div>

      <StepIndicator steps={STEPS} currentStep={currentStep} />

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">{error}</div>
      )}

      {/* Step 0: Setup */}
      <StepCard title="Step 1: Setup" status={currentStep > 0 ? "done" : "pending"}
        defaultExpanded={currentStep === 0}>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">Topic</label>
            <input type="text" value={topic} onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. CPF Basics" className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-full placeholder:text-slate-600" />
          </div>
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">Source Video</label>
            {cutOutputs.length > 0 ? (
              <select value={selectedVideo} onChange={(e) => setSelectedVideo(e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-full">
                <option value="">Select a cut video...</option>
                {cutOutputs.map((co) => (
                  <option key={co.file} value={co.file}>{co.slug} / {co.file.split("/").pop()}</option>
                ))}
              </select>
            ) : (
              <p className="text-sm text-slate-500">No cut videos found. Run the Cut pipeline first.</p>
            )}
          </div>
          <RunButton label="Create Project" onClick={createProject} disabled={!selectedVideo} />
        </div>
      </StepCard>

      {/* Step 1: Transcribe */}
      {currentStep >= 1 && (
        <StepCard title="Step 2: Transcribe" status={transcribing ? "running" : currentStep > 1 ? "done" : "pending"}
          summary={segmentCount > 0 ? `${segmentCount} segments` : undefined} defaultExpanded={currentStep === 1}>
          <div className="space-y-3">
            {transcribing && <div className="text-sm text-indigo-400 animate-pulse">Transcribing with Whisper...</div>}
            {!transcribing && currentStep === 1 && (
              <RunButton label="Transcribe Video" onClick={runTranscribe} />
            )}
          </div>
        </StepCard>
      )}

      {/* Step 2: Analyze */}
      {currentStep >= 2 && (
        <StepCard title="Step 3: Enhancement Analysis" status={analyzing ? "running" : currentStep > 2 ? "done" : "pending"}
          summary={enhancementCount > 0 ? `${enhancementCount} enhancements` : undefined} defaultExpanded={currentStep === 2}>
          <div className="space-y-3">
            {analysisProgress && <div className="text-sm text-indigo-400 animate-pulse">{analysisProgress}</div>}
            {!analyzing && currentStep === 2 && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">Claude Opus will analyze the video content and suggest visual enhancements.</p>
                <RunButton label="Analyze & Generate Spec (Opus)" onClick={runAnalysis} />
              </div>
            )}
          </div>
        </StepCard>
      )}

      {/* Step 3: Preview & Render */}
      {currentStep >= 3 && (
        <StepCard title="Step 4: Preview & Render" status="pending" defaultExpanded={currentStep === 3}>
          <div className="space-y-4">
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 text-sm text-slate-300">
              Enhancement spec generated with {enhancementCount} enhancements. Review at workspace/temp/enhance/{projectSlug}/enhancement_spec.json
            </div>
            {renderProgress && <div className="text-sm text-slate-400">{renderProgress}</div>}
            <div className="flex gap-2">
              <RunButton label="Preview Render" onClick={() => runRender("preview")} loading={rendering} variant="secondary" />
              <RunButton label="Final Render" onClick={() => runRender("final")} loading={rendering} />
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
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
