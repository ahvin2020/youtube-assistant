"use client";

import { useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { runExecutor } from "@/lib/execute";
import { callClaude, readWorkspaceFile, writeWorkspaceFile } from "@/lib/analyze";
import StepIndicator from "@/components/pipeline/StepIndicator";
import StepCard from "@/components/pipeline/StepCard";
import RunButton from "@/components/pipeline/RunButton";

interface CutProject {
  slug: string;
  topic?: string;
  phase?: string;
  [key: string]: unknown;
}

interface CutWizardProps {
  projects: CutProject[];
  videoFiles: { dir: string; files: string[] }[];
}

const STEPS = ["Setup", "Transcribe", "Analyze & Cut", "Review"];

function getProjectSlug(topic: string): string {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const slug = topic.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 30);
  return `${date}_${slug}`;
}

export default function CutWizard({ projects, videoFiles }: CutWizardProps) {
  const searchParams = useSearchParams();
  const paramTopic = searchParams.get("topic") || "";

  const [currentStep, setCurrentStep] = useState(0);
  const [topic, setTopic] = useState(paramTopic);
  const [selectedVideo, setSelectedVideo] = useState("");
  const [scriptSource, setScriptSource] = useState<"none" | "paste" | "file">("none");
  const [scriptText, setScriptText] = useState("");
  const [projectSlug, setProjectSlug] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Transcription state
  const [transcribing, setTranscribing] = useState(false);
  const [transcribeProgress, setTranscribeProgress] = useState("");
  const [segmentCount, setSegmentCount] = useState(0);

  // Cut state
  const [cutting, setCutting] = useState(false);
  const [cutProgress, setCutProgress] = useState("");
  const [cutSummary, setCutSummary] = useState("");
  const [outputFile, setOutputFile] = useState("");

  const createProject = useCallback(async () => {
    if (!selectedVideo) {
      setError("Please select a video file");
      return;
    }
    setError(null);
    const slug = getProjectSlug(topic || selectedVideo.split("/").pop()?.replace(/\.[^.]+$/, "") || "video");
    setProjectSlug(slug);

    const tempPath = `workspace/temp/video/${slug}`;
    await writeWorkspaceFile(
      `${tempPath}/state.json`,
      JSON.stringify({
        topic: topic || slug, slug, phase: "transcribe",
        video_file: selectedVideo,
        script_mode: scriptSource !== "none",
        created: new Date().toISOString().slice(0, 10),
      }, null, 2)
    );

    // If user pasted a script, save it
    if (scriptSource === "paste" && scriptText.trim()) {
      await writeWorkspaceFile(`${tempPath}/script.txt`, scriptText);
    }

    setCurrentStep(1);
  }, [topic, selectedVideo, scriptSource, scriptText]);

  const runTranscribe = useCallback(async () => {
    setTranscribing(true);
    setError(null);
    setTranscribeProgress("Transcribing video with Whisper (this may take a few minutes)...");

    try {
      const result = await runExecutor(
        "video/transcribe.py",
        [
          selectedVideo,
          `workspace/temp/video/${projectSlug}/transcript.json`,
          "--language", "en",
          "--model", "small",
          "--workers", "4",
        ],
        "python3"
      );

      if (!result.success) {
        setError(`Transcription failed: ${result.stderr.slice(0, 300)}`);
        setTranscribing(false);
        return;
      }

      try {
        const data = JSON.parse(result.stdout);
        setSegmentCount(data.segments || data.segment_count || 0);
      } catch {
        setSegmentCount(0);
      }

      setTranscribeProgress("");
      setCurrentStep(2);
    } catch (err) {
      setError(`Transcription failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setTranscribing(false);
    }
  }, [selectedVideo, projectSlug]);

  const runCut = useCallback(async () => {
    setCutting(true);
    setError(null);
    const tempPath = `workspace/temp/video/${projectSlug}`;
    const outputPath = `workspace/output/video/${projectSlug}`;
    const hasScript = scriptSource !== "none";

    try {
      // Step 1: Build cut spec with Claude Opus
      setCutProgress("Analyzing transcript and building cut spec (Opus)...");

      const transcriptData = await readWorkspaceFile(`${tempPath}/transcript.json`);
      if (!transcriptData.content) {
        setError("Transcript file not found");
        setCutting(false);
        return;
      }

      let scriptContent = "";
      if (hasScript) {
        const scriptData = await readWorkspaceFile(`${tempPath}/script.txt`);
        scriptContent = scriptData.content || "";
      }

      const directiveData = await readWorkspaceFile("directives/video/auto-edit.md");
      const directive = directiveData.content || "";

      const cutSpecResult = await callClaude(
        "claude-opus-4-20250514",
        `You are a video editor. Analyze the transcript and build a cut specification.

${directive.slice(0, 6000)}`,
        [{
          role: "user",
          content: `${hasScript ? "SCRIPT-GUIDED MODE" : "RETAKE-ONLY MODE"}: Analyze this transcript and produce a cut_spec.json.

${hasScript ? `SCRIPT:\n${scriptContent.slice(0, 5000)}\n\n` : ""}TRANSCRIPT (segments):
${transcriptData.content.slice(0, 30000)}

Produce a JSON object with:
{
  "mode": "${hasScript ? "script-guided" : "retake-only"}",
  "source_file": "${selectedVideo}",
  "segments_to_keep": [
    { "start": <seconds>, "end": <seconds>, "label": "<section name or reason>" }
  ],
  "segments_to_remove": [
    { "start": <seconds>, "end": <seconds>, "reason": "<retake|off-script|silence>" }
  ],
  "summary": "<brief description of what was kept and removed>"
}

Output ONLY valid JSON. No markdown fences.`,
        }],
        16384
      );

      if (!cutSpecResult.success || !cutSpecResult.content) {
        setError(`Cut spec generation failed: ${cutSpecResult.error || "No response"}`);
        setCutting(false);
        return;
      }

      // Parse and save cut spec
      let cutSpec: string;
      try {
        const match = cutSpecResult.content.match(/\{[\s\S]*\}/);
        const parsed = JSON.parse(match ? match[0] : cutSpecResult.content);
        cutSpec = JSON.stringify(parsed, null, 2);
        setCutSummary(parsed.summary || "Cut spec generated");
      } catch {
        cutSpec = cutSpecResult.content;
        setCutSummary("Cut spec generated");
      }

      await writeWorkspaceFile(`${tempPath}/cut_spec.json`, cutSpec);

      // Step 2: Validate cut spec
      setCutProgress("Validating cut spec...");
      const validateResult = await runExecutor(
        "video/validate_cut_spec.py",
        [`${tempPath}/cut_spec.json`],
        "python3"
      );

      if (!validateResult.success) {
        setError(`Cut spec validation warning: ${validateResult.stderr.slice(0, 200)}`);
        // Continue anyway — validation is advisory
      }

      // Step 3: Apply cuts
      setCutProgress("Applying cuts to video...");
      const stem = selectedVideo.split("/").pop()?.replace(/\.[^.]+$/, "") || "video";
      const ext = selectedVideo.split(".").pop() || "mp4";
      const outputFilePath = `${outputPath}/${stem}_trimmed.${ext}`;

      const applyResult = await runExecutor(
        "video/apply_cuts.py",
        [
          `${tempPath}/cut_spec.json`,
          outputFilePath,
          "--mode", "joined",
          "--temp-dir", tempPath,
        ],
        "python3"
      );

      if (!applyResult.success) {
        setError(`Apply cuts failed: ${applyResult.stderr.slice(0, 300)}`);
        setCutting(false);
        return;
      }

      setOutputFile(outputFilePath);

      await writeWorkspaceFile(
        `${tempPath}/state.json`,
        JSON.stringify({
          topic, slug: projectSlug, phase: "complete",
          video_file: selectedVideo, output_file: outputFilePath,
          created: new Date().toISOString().slice(0, 10),
          updated: new Date().toISOString().slice(0, 10),
        }, null, 2)
      );

      setCutProgress("");
      setCurrentStep(3);
    } catch (err) {
      setError(`Cut pipeline failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setCutting(false);
    }
  }, [projectSlug, selectedVideo, scriptSource, topic]);

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-100">Cut Pipeline</h1>
          <p className="text-sm text-slate-400 mt-1">Transcribe, analyze, and auto-edit raw video</p>
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
        summary={currentStep > 0 ? `${selectedVideo.split("/").pop()}` : undefined}
        defaultExpanded={currentStep === 0}>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">Video Topic (optional)</label>
            <input type="text" value={topic} onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. CPF Basics"
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-full placeholder:text-slate-600" />
          </div>
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">Video File</label>
            {videoFiles.length > 0 ? (
              <select value={selectedVideo} onChange={(e) => setSelectedVideo(e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-full">
                <option value="">Select a video...</option>
                {videoFiles.map((dir) =>
                  dir.files.map((file) => (
                    <option key={`${dir.dir}/${file}`} value={`workspace/input/video/${dir.dir}/${file}`}>
                      {dir.dir}/{file}
                    </option>
                  ))
                )}
              </select>
            ) : (
              <p className="text-sm text-slate-500">No video files found in workspace/input/video/. Drop your raw video there first.</p>
            )}
          </div>
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">Script</label>
            <div className="flex gap-3 mb-2">
              {(["none", "paste"] as const).map((opt) => (
                <label key={opt} className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                  <input type="radio" name="scriptSource" value={opt} checked={scriptSource === opt}
                    onChange={() => setScriptSource(opt)} className="accent-indigo-500" />
                  {opt === "none" ? "No script (retake-only)" : "Paste script"}
                </label>
              ))}
            </div>
            {scriptSource === "paste" && (
              <textarea value={scriptText} onChange={(e) => setScriptText(e.target.value)}
                placeholder="Paste your video script here..."
                rows={6}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-full placeholder:text-slate-600" />
            )}
          </div>
          <RunButton label="Create Project" onClick={createProject} disabled={!selectedVideo} />
        </div>
      </StepCard>

      {/* Step 1: Transcribe */}
      {currentStep >= 1 && (
        <StepCard title="Step 2: Transcribe" status={transcribing ? "running" : currentStep > 1 ? "done" : "pending"}
          summary={currentStep > 1 ? `${segmentCount} segments` : undefined}
          defaultExpanded={currentStep === 1}>
          <div className="space-y-3">
            {transcribeProgress && <div className="text-sm text-indigo-400 animate-pulse">{transcribeProgress}</div>}
            {!transcribing && currentStep === 1 && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">Run Whisper transcription on the video. This may take a few minutes.</p>
                <RunButton label="Transcribe" onClick={runTranscribe} />
              </div>
            )}
          </div>
        </StepCard>
      )}

      {/* Step 2: Analyze & Cut */}
      {currentStep >= 2 && (
        <StepCard title="Step 3: Analyze & Cut" status={cutting ? "running" : currentStep > 2 ? "done" : "pending"}
          summary={cutSummary || undefined}
          defaultExpanded={currentStep === 2}>
          <div className="space-y-3">
            {cutProgress && <div className="text-sm text-indigo-400 animate-pulse">{cutProgress}</div>}
            {!cutting && currentStep === 2 && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">
                  Claude Opus will analyze the transcript{scriptSource !== "none" ? " against your script" : ""}, build a cut spec, and apply edits.
                </p>
                <RunButton label="Analyze & Cut (Opus)" onClick={runCut} />
              </div>
            )}
          </div>
        </StepCard>
      )}

      {/* Step 3: Review */}
      {currentStep >= 3 && (
        <StepCard title="Step 4: Review" status="done" defaultExpanded={currentStep === 3}>
          <div className="space-y-4">
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4">
              <div className="text-sm font-medium text-emerald-400 mb-2">Video Cut Complete!</div>
              <div className="text-xs text-slate-400 space-y-1">
                <div>Output: {outputFile}</div>
                <div>Cut spec: workspace/temp/video/{projectSlug}/cut_spec.json</div>
              </div>
              {cutSummary && <p className="text-sm text-slate-300 mt-2">{cutSummary}</p>}
            </div>
            <div className="border-t border-slate-700/50 pt-4">
              <div className="text-xs text-slate-400 uppercase tracking-wide mb-2">Next Steps</div>
              <div className="flex flex-wrap gap-2">
                <a href={`/enhance?topic=${encodeURIComponent(topic)}&project=${projectSlug}`}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-violet-500/20 text-violet-300 border border-violet-500/30 hover:bg-violet-500/30 transition-colors">
                  {"✨"} Enhance Video
                </a>
              </div>
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
