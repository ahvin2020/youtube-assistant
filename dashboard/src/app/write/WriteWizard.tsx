"use client";

import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { runExecutor } from "@/lib/execute";
import { callClaude, readWorkspaceFile, writeWorkspaceFile } from "@/lib/analyze";
import StepIndicator from "@/components/pipeline/StepIndicator";
import StepCard from "@/components/pipeline/StepCard";
import RunButton from "@/components/pipeline/RunButton";

interface WriteProject {
  slug: string;
  topic?: string;
  format?: string;
  phase?: string;
  [key: string]: unknown;
}

interface WriteWizardProps {
  projects: WriteProject[];
}

const STEPS = ["Setup", "Research", "Outline", "Script", "Finalize"];

const FORMAT_OPTIONS = [
  { value: "long-form", label: "Long-form (10+ min)" },
  { value: "short-form", label: "Short-form (reel)" },
  { value: "brand-mention", label: "Brand Mention (sponsored)" },
];

function getProjectSlug(topic: string): string {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const slug = topic.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 30);
  return `${date}_${slug}`;
}

function phaseToStep(phase?: string): number {
  switch (phase) {
    case "research": return 1;
    case "research-complete": return 2;
    case "outline": return 2;
    case "script": return 3;
    case "title": return 4;
    case "complete": return 4;
    default: return 0;
  }
}

export default function WriteWizard({ projects }: WriteWizardProps) {
  const searchParams = useSearchParams();

  // Pre-fill from query params (coming from Ideas pipeline)
  const paramTopic = searchParams.get("topic") || "";
  const paramFormat = searchParams.get("format") || "long-form";
  const paramPhase = searchParams.get("phase") || "";

  const [currentStep, setCurrentStep] = useState(0);
  const [topic, setTopic] = useState(paramTopic);
  const [format, setFormat] = useState(paramFormat);
  const [angle, setAngle] = useState("");
  const [projectSlug, setProjectSlug] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Research state
  const [researching, setResearching] = useState(false);
  const [researchProgress, setResearchProgress] = useState("");
  const [brief, setBrief] = useState("");
  const [transcriptCount, setTranscriptCount] = useState(0);

  // Outline state
  const [outlining, setOutlining] = useState(false);
  const [outline, setOutline] = useState("");

  // Script state
  const [scripting, setScripting] = useState(false);
  const [scriptProgress, setScriptProgress] = useState("");
  const [script, setScript] = useState("");

  // Finalize state
  const [exporting, setExporting] = useState(false);
  const [docUrl, setDocUrl] = useState<string | null>(null);

  // If phase=research was passed, auto-start at research step
  useEffect(() => {
    if (paramPhase === "research" && paramTopic) {
      // User wants to start research immediately
    }
  }, [paramPhase, paramTopic]);

  const createProject = useCallback(async () => {
    if (!topic.trim()) {
      setError("Please enter a topic");
      return;
    }
    setError(null);
    const slug = getProjectSlug(topic);
    setProjectSlug(slug);

    const tempPath = `workspace/temp/research/${slug}`;

    await writeWorkspaceFile(
      `${tempPath}/state.json`,
      JSON.stringify({
        topic,
        slug,
        format,
        mode: null,
        phase: format === "brand-mention" ? "outline" : "research",
        tone_override: null,
        parent_project: null,
        brand_brief: null,
        created: new Date().toISOString().slice(0, 10),
        updated: new Date().toISOString().slice(0, 10),
      }, null, 2)
    );

    if (format === "brand-mention") {
      // Skip research for brand mentions
      setCurrentStep(2);
    } else if (format === "short-form") {
      // Ask-free: shorts can skip research
      setCurrentStep(1);
    } else {
      setCurrentStep(1);
    }
  }, [topic, format]);

  const runResearch = useCallback(async () => {
    setResearching(true);
    setError(null);
    const tempPath = `workspace/temp/research/${projectSlug}`;

    try {
      // Read channel profile for context
      setResearchProgress("Loading channel profile...");
      const profileData = await readWorkspaceFile("memory/channel-profile.md");
      const profile = profileData.content || "";

      // Check if user provided YouTube URLs to fetch transcripts from
      const urlMatches = angle.match(/https?:\/\/(?:www\.)?(?:youtube\.com|youtu\.be)\/[^\s]+/g);
      let transcriptContent = "";

      if (urlMatches && urlMatches.length > 0) {
        setResearchProgress(`Fetching ${urlMatches.length} transcript(s)...`);
        const fetchPromises = urlMatches.slice(0, 5).map(async (url, i) => {
          try {
            const result = await runExecutor(
              "research/fetch_transcript.py",
              [url, `${tempPath}/transcripts/video_${i}.json`],
              "python3"
            );
            if (result.success) {
              setTranscriptCount((prev) => prev + 1);
              const data = await readWorkspaceFile(`${tempPath}/transcripts/video_${i}.json`);
              if (data.content) {
                try {
                  const parsed = JSON.parse(data.content);
                  const text = parsed.full_text || "";
                  return `### ${parsed.title || `Video ${i + 1}`}\n${text.slice(0, 3000)}`;
                } catch { return ""; }
              }
            }
            return "";
          } catch { return ""; }
        });
        const transcripts = await Promise.all(fetchPromises);
        transcriptContent = transcripts.filter(Boolean).join("\n\n---\n\n");
      }

      // Synthesize brief with Claude
      setResearchProgress("Synthesizing research brief with AI...");

      const briefResult = await callClaude(
        "claude-sonnet-4-20250514",
        `You are a research assistant for a personal finance YouTube channel. Write a comprehensive research brief.

Channel Profile:
${profile.slice(0, 2000)}`,
        [{
          role: "user",
          content: `Write a research brief for a ${format} video about "${topic}".${angle ? ` Angle/Context: ${angle}` : ""}

${transcriptContent ? `Here are transcripts from relevant YouTube videos:\n\n${transcriptContent.slice(0, 15000)}` : "No transcripts provided. Synthesize from your knowledge of this topic in the personal finance space."}

Write the brief in this format:

# Research Brief: ${topic}
**Mode**: Topic Deep-Dive | **Date**: ${new Date().toISOString().slice(0, 10)} | **Status**: Complete

## Executive Summary
<2-3 sentences: the key takeaway>

## Key Findings
### Finding 1: <title>
<detail>

### Finding 2: <title>
...

## What Other Creators Typically Cover
<common angles and arguments on this topic>

## Conflicting Views
<where opinions or data disagree>

## Data Points
<key statistics worth mentioning in a video>

## Potential Video Angles
1. <angle 1>
2. <angle 2>
3. <angle 3>

Be thorough but concise. Focus on actionable insights for a video script.`,
        }],
        8192
      );

      if (!briefResult.success || !briefResult.content) {
        setError(`Research brief generation failed: ${briefResult.error || "No response"}`);
        setResearching(false);
        return;
      }

      setBrief(briefResult.content);
      await writeWorkspaceFile(`${tempPath}/brief.md`, briefResult.content);

      // Update state
      await writeWorkspaceFile(
        `${tempPath}/state.json`,
        JSON.stringify({
          topic, slug: projectSlug, format, mode: "topic-deep-dive",
          phase: "outline", tone_override: null, parent_project: null, brand_brief: null,
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
  }, [topic, angle, format, projectSlug]);

  const runOutline = useCallback(async () => {
    setOutlining(true);
    setError(null);
    const tempPath = `workspace/temp/research/${projectSlug}`;

    try {
      // Read brief if we don't have it
      let briefContent = brief;
      if (!briefContent) {
        const briefData = await readWorkspaceFile(`${tempPath}/brief.md`);
        briefContent = briefData.content || "";
        setBrief(briefContent);
      }

      const profileData = await readWorkspaceFile("memory/channel-profile.md");
      const profile = profileData.content || "";

      const isShort = format === "short-form";
      const isBrand = format === "brand-mention";

      const outlinePrompt = isShort
        ? `Create a short-form reel outline (3-beat structure: Hook, Core Point, Payoff) for "${topic}".${angle ? ` Angle: ${angle}` : ""}

${briefContent ? `Research brief:\n${briefContent.slice(0, 4000)}` : ""}

Format:
# Reel Outline: ${topic}
**Format**: Short-form | **Target Length**: ~60s | **Status**: In Progress

## Hook (first 3 seconds)
- <one line that stops the scroll>

## Core Point
- <the single insight>
- <supporting detail>

## Payoff / CTA
- <punchline or takeaway>`
        : isBrand
        ? `Create a brand mention outline for "${topic}".${angle ? ` Details: ${angle}` : ""}

Format:
# Brand Mention Outline: ${topic}
**Format**: Brand-mention | **Target Length**: ~60s | **Status**: In Progress

## Transition In
- <bridge from main video to sponsor>

## Problem / Need
- <pain point the product addresses>

## Product Introduction
- <name, what it is, value proposition>

## Key Features (2-3 max)
- <feature tied to viewer need>

## Personal Touch
- <creator's experience>

## CTA
- <promo code, link, action>

## Transition Out
- <return to main video>`
        : `Create a long-form video outline for "${topic}".${angle ? ` Angle: ${angle}` : ""}

Research brief:
${briefContent.slice(0, 6000)}

Format:
# Video Outline: ${topic}
**Format**: Long-form | **Target Length**: <estimate> | **Status**: In Progress

## Hook (0:00-0:30)
- <what grabs attention>

## Section 1: <title>
- Point A
- Point B
- Transition to next

## Section 2: <title>
...

## Call to Action / Outro
- <how to end>

Propose 4-6 body sections. Consider: strongest hook, logical flow, sections needing visuals.`;

      const outlineResult = await callClaude(
        "claude-sonnet-4-20250514",
        `You are a content strategist for a personal finance YouTube channel.

Channel Profile:
${profile.slice(0, 2000)}`,
        [{ role: "user", content: outlinePrompt }],
        4096
      );

      if (!outlineResult.success || !outlineResult.content) {
        setError(`Outline generation failed: ${outlineResult.error || "No response"}`);
        setOutlining(false);
        return;
      }

      setOutline(outlineResult.content);
      await writeWorkspaceFile(`${tempPath}/outline.md`, outlineResult.content);

      // Update state
      await writeWorkspaceFile(
        `${tempPath}/state.json`,
        JSON.stringify({
          topic, slug: projectSlug, format, mode: "topic-deep-dive",
          phase: "script", tone_override: null, parent_project: null, brand_brief: null,
          created: new Date().toISOString().slice(0, 10),
          updated: new Date().toISOString().slice(0, 10),
        }, null, 2)
      );

      setCurrentStep(3);
    } catch (err) {
      setError(`Outline failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setOutlining(false);
    }
  }, [topic, angle, format, projectSlug, brief]);

  const runScript = useCallback(async () => {
    setScripting(true);
    setScriptProgress("Preparing script draft...");
    setError(null);
    const tempPath = `workspace/temp/research/${projectSlug}`;
    const outputPath = `workspace/output/research/${projectSlug}`;

    try {
      // Read inputs
      let briefContent = brief;
      let outlineContent = outline;

      if (!briefContent) {
        const d = await readWorkspaceFile(`${tempPath}/brief.md`);
        briefContent = d.content || "";
        setBrief(briefContent);
      }
      if (!outlineContent) {
        const d = await readWorkspaceFile(`${tempPath}/outline.md`);
        outlineContent = d.content || "";
        setOutline(outlineContent);
      }

      const profileData = await readWorkspaceFile("memory/channel-profile.md");
      const profile = profileData.content || "";

      // Load writing style reference if available
      let writingStyle = "";
      const styleData = await readWorkspaceFile("memory/writing-style.md");
      if (styleData.content) {
        writingStyle = styleData.content.slice(0, 4000);
      }

      // Load hooks for inspiration if available
      let hooksRef = "";
      const hooksData = await readWorkspaceFile("workspace/config/hooks.json");
      if (hooksData.content) {
        try {
          const hooks = JSON.parse(hooksData.content);
          const topHooks = hooks.slice(0, 10).map((h: { text: string; category: string }) =>
            `- [${h.category}] ${h.text}`
          ).join("\n");
          hooksRef = `\n\nProven hooks from top-performing videos (use as inspiration, not verbatim):\n${topHooks}`;
        } catch { /* ignore */ }
      }

      const isShort = format === "short-form";

      setScriptProgress("Writing script with Opus...");

      const scriptPrompt = isShort
        ? `Write a short-form reel script for "${topic}".

Outline:
${outlineContent}

${briefContent ? `Research brief:\n${briefContent.slice(0, 3000)}` : ""}

Rules:
- Target ~150-250 words (~60-90 seconds)
- Write as one continuous piece, no section headers
- Every word must earn its place - cut fluff
- Punchy, conversational, immediate hook
- Do NOT use em dashes in the script
${hooksRef}

Output format:
# Reel Script: ${topic}
**Format**: Short-form | **Based on**: outline.md | **Tone**: conversational
**Word count**: <actual count>

<full script text>`
        : `Write a full long-form video script for "${topic}".

Outline:
${outlineContent}

Research brief:
${briefContent.slice(0, 8000)}

${writingStyle ? `Writing style reference:\n${writingStyle}\n` : ""}

Rules:
- Target ~1500-2500 words (~10-17 minutes)
- Write section by section following the outline
- Conversational tone, like explaining to a friend
- Include [Source: name](url) citations on their own lines below claims
- Do NOT use em dashes in the script - use periods, commas, or line breaks
- Make the hook the strongest part
${hooksRef}

Output format:
# Script: ${topic}
**Format**: Long-form | **Based on**: outline.md | **Tone**: conversational

## Hook
<full script text>

## Section 1: <title>
<full script text>

...`;

      const scriptResult = await callClaude(
        "claude-opus-4-20250514",
        `You are a skilled scriptwriter for a personal finance YouTube channel. Write engaging, educational scripts.

Channel Profile:
${profile.slice(0, 2000)}`,
        [{ role: "user", content: scriptPrompt }],
        16384
      );

      if (!scriptResult.success || !scriptResult.content) {
        setError(`Script generation failed: ${scriptResult.error || "No response"}`);
        setScripting(false);
        return;
      }

      setScript(scriptResult.content);
      await writeWorkspaceFile(`${outputPath}/script.md`, scriptResult.content);

      // Update state
      await writeWorkspaceFile(
        `${tempPath}/state.json`,
        JSON.stringify({
          topic, slug: projectSlug, format, mode: "topic-deep-dive",
          phase: "complete", tone_override: null, parent_project: null, brand_brief: null,
          created: new Date().toISOString().slice(0, 10),
          updated: new Date().toISOString().slice(0, 10),
        }, null, 2)
      );

      setScriptProgress("");
      setCurrentStep(4);
    } catch (err) {
      setError(`Script writing failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setScripting(false);
    }
  }, [topic, format, projectSlug, brief, outline]);

  const runExport = useCallback(async () => {
    setExporting(true);
    setError(null);
    try {
      const result = await runExecutor(
        "research/export_google_doc.py",
        [
          `workspace/output/research/${projectSlug}/script.md`,
          "--title", `Script: ${topic}`,
        ],
        "/opt/homebrew/bin/python3"
      );
      if (result.success) {
        try {
          const data = JSON.parse(result.stdout);
          if (data.url) setDocUrl(data.url);
          if (data.doc_url) setDocUrl(data.doc_url);
        } catch { /* stdout not JSON */ }
      } else {
        setError(`Google Docs export failed: ${result.stderr.slice(0, 200)}`);
      }
    } finally {
      setExporting(false);
    }
  }, [projectSlug, topic]);

  const resumeProject = useCallback(async (project: WriteProject) => {
    setProjectSlug(project.slug);
    setTopic(project.topic || "");
    setFormat(project.format || "long-form");

    const tempPath = `workspace/temp/research/${project.slug}`;
    const step = phaseToStep(project.phase);

    // Load existing files
    const [briefData, outlineData, scriptData] = await Promise.all([
      readWorkspaceFile(`${tempPath}/brief.md`),
      readWorkspaceFile(`${tempPath}/outline.md`),
      readWorkspaceFile(`workspace/output/research/${project.slug}/script.md`),
    ]);

    if (briefData.content) setBrief(briefData.content);
    if (outlineData.content) setOutline(outlineData.content);
    if (scriptData.content) setScript(scriptData.content);

    setCurrentStep(step);
  }, []);

  return (
    <div className="p-4 sm:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-100">Write Pipeline</h1>
          <p className="text-sm text-slate-400 mt-1">
            Research, outline, and write video scripts
          </p>
        </div>
        {currentStep > 0 && (
          <button
            onClick={() => {
              setCurrentStep(0);
              setTopic("");
              setFormat("long-form");
              setAngle("");
              setProjectSlug("");
              setBrief("");
              setOutline("");
              setScript("");
              setError(null);
              setDocUrl(null);
            }}
            className="text-xs px-3 py-1.5 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors"
          >
            New Project
          </button>
        )}
      </div>

      <StepIndicator steps={STEPS} currentStep={currentStep} />

      {/* Error banner */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Step 0: Setup */}
      <StepCard
        title="Step 1: Setup"
        status={currentStep > 0 ? "done" : "pending"}
        summary={currentStep > 0 ? `${topic} (${format})` : undefined}
        defaultExpanded={currentStep === 0}
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">Topic</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. DCA vs Lump Sum, CPF Basics, Fed Rate Cut Impact"
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-full placeholder:text-slate-600"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">Format</label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-full sm:w-auto"
            >
              {FORMAT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wide block mb-1.5">
              Angle / Context (optional)
            </label>
            <input
              type="text"
              value={angle}
              onChange={(e) => setAngle(e.target.value)}
              placeholder="e.g. focused on Singapore investors, contrarian take, news just broke"
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-full placeholder:text-slate-600"
            />
          </div>
          <RunButton label="Create Project" onClick={createProject} />
        </div>
      </StepCard>

      {/* Step 1: Research */}
      {currentStep >= 1 && (
        <StepCard
          title="Step 2: Research"
          status={researching ? "running" : currentStep > 1 ? "done" : "pending"}
          summary={currentStep > 1 ? `Brief ready (${transcriptCount} transcripts)` : undefined}
          defaultExpanded={currentStep === 1}
        >
          <div className="space-y-4">
            {researchProgress && (
              <div className="text-sm text-indigo-400 animate-pulse">{researchProgress}</div>
            )}
            {!researching && currentStep === 1 && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">
                  AI will synthesize a research brief on your topic. Paste YouTube URLs in the angle/context field above to include their transcripts.
                </p>
                <div className="flex gap-2">
                  <RunButton label="Run Research" onClick={runResearch} />
                  {format === "short-form" && (
                    <RunButton
                      label="Skip Research"
                      onClick={() => setCurrentStep(2)}
                      variant="secondary"
                    />
                  )}
                </div>
              </div>
            )}
            {brief && currentStep > 1 && (
              <details className="group">
                <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-300">
                  View research brief
                </summary>
                <div className="mt-2 bg-slate-800/50 border border-slate-700/50 rounded-lg p-4 text-sm text-slate-300 whitespace-pre-line max-h-96 overflow-y-auto">
                  {brief}
                </div>
              </details>
            )}
          </div>
        </StepCard>
      )}

      {/* Step 2: Outline */}
      {currentStep >= 2 && (
        <StepCard
          title="Step 3: Outline"
          status={outlining ? "running" : currentStep > 2 ? "done" : "pending"}
          summary={currentStep > 2 ? "Outline approved" : undefined}
          defaultExpanded={currentStep === 2}
        >
          <div className="space-y-4">
            {!outlining && !outline && currentStep === 2 && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">
                  Generate a structured outline based on the research brief.
                </p>
                <RunButton label="Generate Outline" onClick={runOutline} />
              </div>
            )}
            {outlining && (
              <div className="text-sm text-indigo-400 animate-pulse">Generating outline...</div>
            )}
            {outline && (
              <div className="space-y-3">
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4 text-sm text-slate-300 whitespace-pre-line max-h-96 overflow-y-auto">
                  {outline}
                </div>
                {currentStep === 2 && (
                  <div className="flex gap-2">
                    <RunButton
                      label="Approve & Write Script"
                      onClick={() => setCurrentStep(3)}
                    />
                    <RunButton
                      label="Regenerate"
                      onClick={runOutline}
                      variant="secondary"
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        </StepCard>
      )}

      {/* Step 3: Script */}
      {currentStep >= 3 && (
        <StepCard
          title="Step 4: Script"
          status={scripting ? "running" : currentStep > 3 ? "done" : "pending"}
          summary={currentStep > 3 ? "Script complete" : undefined}
          defaultExpanded={currentStep === 3}
        >
          <div className="space-y-4">
            {scriptProgress && (
              <div className="text-sm text-indigo-400 animate-pulse">{scriptProgress}</div>
            )}
            {!scripting && !script && currentStep === 3 && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">
                  Write the full script using Claude Opus for maximum quality.
                </p>
                <RunButton label="Write Script (Opus)" onClick={runScript} />
              </div>
            )}
            {script && (
              <div className="space-y-3">
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4 text-sm text-slate-300 whitespace-pre-line max-h-[600px] overflow-y-auto">
                  {script}
                </div>
                {currentStep === 3 && (
                  <div className="flex gap-2">
                    <RunButton
                      label="Approve & Finalize"
                      onClick={() => setCurrentStep(4)}
                    />
                    <RunButton
                      label="Rewrite"
                      onClick={runScript}
                      variant="secondary"
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        </StepCard>
      )}

      {/* Step 4: Finalize */}
      {currentStep >= 4 && (
        <StepCard
          title="Step 5: Finalize"
          status={docUrl ? "done" : "pending"}
          summary={docUrl ? "Exported to Google Docs" : undefined}
          defaultExpanded={currentStep === 4}
        >
          <div className="space-y-4">
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4">
              <div className="text-sm font-medium text-emerald-400 mb-2">Script Complete!</div>
              <div className="text-xs text-slate-400 space-y-1">
                <div>Script: workspace/output/research/{projectSlug}/script.md</div>
                {brief && <div>Brief: workspace/temp/research/{projectSlug}/brief.md</div>}
                {outline && <div>Outline: workspace/temp/research/{projectSlug}/outline.md</div>}
              </div>
            </div>

            {!docUrl && (
              <RunButton
                label={exporting ? "Exporting..." : "Export to Google Docs"}
                onClick={runExport}
                loading={exporting}
                variant="secondary"
              />
            )}

            {docUrl && (
              <a
                href={docUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300"
              >
                Open Google Doc
              </a>
            )}

            {/* Next pipeline actions */}
            <div className="border-t border-slate-700/50 pt-4">
              <div className="text-xs text-slate-400 uppercase tracking-wide mb-2">Next Steps</div>
              <div className="flex flex-wrap gap-2">
                <a
                  href={`/thumbnail?topic=${encodeURIComponent(topic)}`}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-pink-500/20 text-pink-300 border border-pink-500/30 hover:bg-pink-500/30 transition-colors"
                >
                  {"🎨"} Generate Thumbnail
                </a>
                <a
                  href={`/cut?topic=${encodeURIComponent(topic)}`}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-sky-500/20 text-sky-300 border border-sky-500/30 hover:bg-sky-500/30 transition-colors"
                >
                  {"🎬"} Cut Video
                </a>
              </div>
            </div>
          </div>
        </StepCard>
      )}

      {/* Previous projects */}
      {projects.length > 0 && currentStep === 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3">
            Previous Projects
          </h2>
          <div className="space-y-2">
            {projects.map((p) => (
              <div
                key={p.slug}
                className="bg-slate-900/50 border border-slate-800 rounded-lg px-4 py-3 flex items-center justify-between"
              >
                <div>
                  <span className="text-sm text-slate-200">{p.topic || p.slug}</span>
                  <span className="ml-2 text-xs text-slate-500">{p.format}</span>
                  <span className={`ml-2 text-xs px-2 py-0.5 rounded-full ${
                    p.phase === "complete" ? "bg-emerald-400/15 text-emerald-400" : "bg-slate-700 text-slate-400"
                  }`}>
                    {p.phase || "unknown"}
                  </span>
                </div>
                <button
                  onClick={() => resumeProject(p)}
                  className="text-xs text-indigo-400 hover:text-indigo-300"
                >
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
