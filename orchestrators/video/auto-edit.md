# Orchestrator: Script-Based Auto-Edit Pipeline

This orchestrator coordinates the pipeline to automatically detect and remove
errors and retakes from a raw video. A script can optionally be provided as
ground truth for semantic alignment; if absent, retakes are detected from
transcript patterns alone.

Follow every step in order. Do not skip steps. Do not proceed to the next step if
the current step produces an error.

---

## Pre-Flight Checklist

Before starting, verify:
- [ ] `source_file` exists in `workspace/input/`
- [ ] Derive `STEM` = source filename without extension (e.g. `IMG_0171` from `IMG_0171.MOV`)
- [ ] `TEMP_DIR` = `workspace/temp/<STEM>/` — create if not: `mkdir -p workspace/temp/<STEM>`
- [ ] `workspace/output/` directory exists (create if not: `mkdir -p workspace/output`)

Use `TEMP_DIR` for all temp file paths throughout this pipeline. This keeps each video's
intermediate files isolated so multiple videos can be processed concurrently without conflict.

If source file is not found: stop immediately.

---

## Step 1 — Transcribe the Video

Run the transcription executor with `language_code=en`:

```bash
python3 executors/video/transcribe.py "workspace/input/<source_file>" "workspace/temp/<STEM>/transcript.json" --language en --model small
```

If `workspace/temp/<STEM>/transcript.json` already exists from a previous run of the same source file,
ask the user: **"Found an existing transcript. Reuse it or re-transcribe?"** and proceed accordingly.

Wait for this to complete. It may take 1–3 minutes depending on video length.

On success: report to the user: "Transcription complete. X segments found."

On failure: show the full error JSON and stop. Common fixes:
- `openai-whisper not installed` → `pip install openai-whisper`
- `ffmpeg not found` → `brew install ffmpeg`

---

## Step 2 — Analyze and Build Cut Spec (Claude's Intelligence Step)

Read `directives/video/auto-edit.md` and apply the matching rules appropriate to the mode:

**If `workspace/temp/<STEM>/script.txt` exists:** use Script Mode — semantic alignment of transcript to script sections.

**If no script exists:** use Script-Free Mode — detect retakes from transcript patterns alone (see directive).

Inputs:
- `workspace/temp/<STEM>/transcript.json`
- `workspace/temp/<STEM>/script.txt` (optional)

Output:
- `workspace/temp/<STEM>/cut_spec.json`

Work through the content section by section. For each section, find all spoken
attempts in the transcript and keep only the final delivery. Remove all earlier
attempts and any off-script content.

---

## Step 3 — Present the Cut Plan for User Review

Show the user a clear summary before applying any edits.

Format the output as:

```
SEGMENTS TO REMOVE:
───────────────────────────────────────────────────────
 #  Start      End        Duration   Reason
───────────────────────────────────────────────────────
 1  00:01:23   00:02:10   0:47       Retake — repeated intro
 2  00:05:33   00:05:58   0:25       Off-script tangent
───────────────────────────────────────────────────────
Total removed: 1m 12s  |  2 retakes detected

SEGMENTS TO KEEP:
 1  00:00:00 → 00:01:23  (Section 1: intro)
 2  00:02:10 → 00:05:33  (Sections 2–4: main content)
 3  00:05:58 → 00:08:44  (Section 5: outro)
```

Then ask:
**"Proceed with these edits? Type yes to apply, no to cancel, or describe any adjustments."**

If the user requests adjustments: update `cut_spec.json` accordingly and show the
revised plan before proceeding.

---

## Step 4 — Apply Cuts

Once the user confirms, run:

```bash
python3 executors/video/apply_cuts.py "workspace/temp/<STEM>/cut_spec.json" "workspace/output/<output_filename>" --temp-dir "workspace/temp/<STEM>"
```

Where `<output_filename>` is: `{source_stem}_trimmed{ext}`
Example: `interview_trimmed.mp4`

On success, report:
```
Trim complete!
Output:  workspace/output/interview_trimmed.mp4
Before:  8m 44s  →  After: 7m 32s  (1m 12s removed)
Size:    245 MB
```

On failure: show the full error JSON from the executor and apply error handling
from `directives/video/auto-edit.md`.

---

## Post-Processing Note

The `workspace/temp/<STEM>/` files (transcript.json, script.txt, cut_spec.json) are kept
in place so the user can review them. Tell the user they can safely delete the
`workspace/temp/<STEM>/` folder once they're happy with the output.
