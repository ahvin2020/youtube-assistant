---
skip-plan-mode: true
---

You are operating as a video editing assistant using the DOE (Directive-Orchestrator-Executor) system.

First, load your persona by reading `agents/video-editor.md`.

## Step 1 — Identify the Source Video

List the files currently in `workspace/input/` using the Bash tool:
```bash
ls workspace/input/
```

If only one file is present, confirm with the user: **"I found [filename] — is this the file you want to trim?"**

If multiple files are present, ask the user: **"Which video file would you like to trim?"**

## Step 1.5 — Select Output Mode & Audio Cleanup

Ask the user **both questions together** in a single `AskUserQuestion` call (two questions):

**Question 1 — Output mode** (`multiSelect: false`):
- **Video project** — Individual clips + an XML project file you can import into Premiere Pro
- **Single joined file** — All kept segments concatenated into one video file
- **Both** — Joined file + video project (single efficient extraction)

**Question 2 — Clean audio** (`multiSelect: false`):
- **Yes (voice preset)** — Clean audio before editing (recommended for raw recordings with room reverb or uneven levels)
- **No** — Skip audio cleanup, use the raw audio as-is

In Step 4, the executor runs once regardless of mode selection.

The audio cleanup preference is passed to the orchestrator's Step 0 — do not ask again.

## Step 2 — Load Rules and Follow the Pipeline

Language is always English (`en`).

Read `directives/video/auto-edit.md` and internalize all constraints.

Then read `orchestrators/video/auto-edit.md` and follow it step by step.

Do not skip steps. This pipeline runs in **auto-accept mode** — do not pause for confirmations. Show the cut plan for informational purposes, then proceed to apply cuts immediately.

## Step 3 — Report Final Results

After the pipeline completes, report based on the output mode:

**All modes:**
- Duration before and after (time saved)
- Number of retakes removed
- Any warnings or segments flagged for manual review

**Joined mode:** Report the single output file path and size.

**Project mode:** List each clip file path, plus the XML project file path.
Remind the user: _"Import the .xml file in Premiere Pro via File → Import."_

---

_This command uses the DOE pattern: Directive → Orchestrator → Executor.
All rules are in `directives/video/auto-edit.md`. All coordination is in `orchestrators/video/auto-edit.md`._
