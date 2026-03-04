# Orchestrator: Auto-Edit Pipeline

This orchestrator coordinates the pipeline to automatically detect and remove
errors and retakes from a raw video.

Two modes are supported:
- **Retake-Only** (`script_mode = false`): retakes detected from transcript patterns alone
- **Script-Guided** (`script_mode = true`): semantic alignment against a user-provided script

The mode is set by the `/cut` command based on user input. It affects only Step 2.

Follow every step in order. Do not skip steps. Do not proceed to the next step if
the current step produces an error.

---

## Pre-Flight Checklist

Before starting, verify:
- [ ] `source_file` exists in `workspace/input/video/` (may be in a dated subfolder)
- [ ] Derive `STEM` = source filename without extension (e.g. `IMG_0171` from `IMG_0171.MOV`)
- [ ] `PROJECT` is set by the `/cut` command (format: `YYYYMMDD_<slug>`, e.g. `20260302_cpf-frs-vs-ers`)
- [ ] `TEMP_DIR` = `workspace/temp/video/<PROJECT>/` — create if not: `mkdir -p workspace/temp/video/<PROJECT>`
- [ ] `workspace/output/video/<PROJECT>/` exists (create if not: `mkdir -p workspace/output/video/<PROJECT>`)
- [ ] If `script_mode = true`: verify `workspace/temp/video/<PROJECT>/script.txt` exists and is non-empty

Use `TEMP_DIR` for all temp file paths throughout this pipeline. This keeps each video's
intermediate files isolated so multiple videos can be processed concurrently without conflict.

If source file is not found: stop immediately.

---

## Step 1 — Transcription

```bash
python3 executors/video/transcribe.py "<source_file_path>" "workspace/temp/video/<PROJECT>/transcript.json" --language en --model small --workers 4
```

If `workspace/temp/video/<PROJECT>/transcript.json` already exists from a previous run, overwrite it —
always re-transcribe to ensure the transcript matches the current source file.

Wait for this to complete. It may take 1–3 minutes depending on video length.

On success: report to the user: "Transcription complete. X segments found."

On failure: show the full error JSON and stop. Common fixes:
- `openai-whisper not installed` → `pip install openai-whisper`
- `ffmpeg not found` → `brew install ffmpeg`

---

## Step 2 — Analyze and Build Cut Spec (Claude's Intelligence Step)

### ⚠️ MUST USE SUBAGENT — Output Token Budget

Transcripts are large (400+ segments, 3000+ lines of JSON). Reading the full transcript
into the main conversation **will exhaust the output token limit** and abort the pipeline.

**Always delegate Step 2 to a subagent** using the Agent tool (`subagent_type: general-purpose`,
`model: "opus"`). Semantic alignment is a high-judgment task that benefits from Opus-level
reasoning. The subagent reads the transcript and script within its own context window,
performs all analysis, writes `cut_spec.json` directly, and returns only a brief summary.

### Subagent prompt template

Provide the subagent with:
1. The file paths: transcript, script (if script_mode), and output cut_spec.json
2. The active mode (`script_mode` true or false)
3. The full rules from `directives/video/auto-edit.md` for the active mode — copy the
   relevant mode section plus the shared rules (output format, within-segment validation,
   Whisper artefacts) into the subagent prompt so it has everything it needs
4. Instructions to write `cut_spec.json` using the Write tool (not print in chat)
5. Instructions to return a brief summary:
   - **Retake-Only**: retakes found, total duration to remove, uncertain segments
   - **Script-Guided**: script sections matched vs unmatched, unmatched section names,
     retakes within matched sections, off-script content removed, total duration to remove

### Output (both modes)

- `workspace/temp/video/<PROJECT>/cut_spec.json`

**Do NOT read the transcript in the main conversation.** The subagent handles it all.

---

## Step 2.5 — Validate Cut Spec (Gap/Overlap Check)

Run the validator immediately after writing `cut_spec.json`:

```bash
python3 executors/video/validate_cut_spec.py "workspace/temp/video/<PROJECT>/transcript.json" "workspace/temp/video/<PROJECT>/cut_spec.json"
```

**If exit code 0** (`valid: true`): proceed to Step 3.

**If exit code 1** (`valid: false`): for each issue in the output:
- `type: "gap"` — a silence gap wider than 0.5s was found inside a keep_segment. Re-examine
  that segment in the transcript and split it at `before_end` / `after_start`. Update
  `cut_spec.json`, then re-run the validator.
- `type: "overlap"` — Whisper produced overlapping segments, which can mask a real stumble.
  Inspect the audio around the reported timestamp and split or trim accordingly. Update
  `cut_spec.json`, then re-run the validator.

Do **not** proceed to Step 3 until the validator reports `valid: true`.

---

## Step 3 — Present the Cut Plan (Auto-Accept)

Show the user a clear summary of the cuts for informational purposes, then **proceed
immediately to Step 4** without waiting for confirmation.

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

Auto-accepting cut plan — proceeding to apply cuts.
```

If `script_mode = true`, also show:

```
SCRIPT COVERAGE:
  Matched:   8/10 sections
  Unmatched: 2 sections
    - Section 4: "The third risk factor is..."
    - Section 9: "In conclusion, the data shows..."
```

Do **not** pause for user confirmation. Proceed directly to Step 4.

---

## Step 4 — Apply Cuts

All outputs go into a per-video folder: `workspace/output/video/<PROJECT>/`.
Create it before running: `mkdir -p workspace/output/<STEM>`.

Run the executor **once**. The command depends on which output mode(s) the user selected in Step 1.5.

**Single joined file only:**
```bash
python3 executors/video/apply_cuts.py "workspace/temp/video/<PROJECT>/cut_spec.json" "workspace/output/video/<PROJECT>/{source_stem}_trimmed{ext}" --temp-dir "workspace/temp/<STEM>" --mode joined
```

**Video project only:**
```bash
python3 executors/video/apply_cuts.py "workspace/temp/video/<PROJECT>/cut_spec.json" "workspace/output/video/<PROJECT>/clips" --temp-dir "workspace/temp/<STEM>" --mode project
```

**Both** (single command — extracts segments once, produces both outputs):
```bash
python3 executors/video/apply_cuts.py "workspace/temp/video/<PROJECT>/cut_spec.json" "workspace/output/video/<PROJECT>/clips" --temp-dir "workspace/temp/<STEM>" --mode both --joined-output "workspace/output/video/<PROJECT>/{source_stem}_trimmed{ext}"
```

For `project` and `both` modes, the positional output argument is the **clips directory**
(not a file). The executor creates it and writes numbered clips inside.

### Reporting by mode

**`joined`**:
```
Trim complete!
Output:  workspace/output/video/20260303_interview/interview_trimmed.mp4
Before:  8m 44s  →  After: 7m 32s  (1m 12s removed)
Size:    245 MB
```

**`project`**:
```
Trim complete! Video project ready:
  Project: workspace/output/video/20260303_interview/clips/interview_project.xml
  Clips:
    1. workspace/output/video/20260303_interview/clips/clip_001.mp4
    2. workspace/output/video/20260303_interview/clips/clip_002.mp4
    3. workspace/output/video/20260303_interview/clips/clip_003.mp4
Before:  8m 44s  →  After: 7m 32s  (1m 12s removed)

Import the .xml file in Premiere Pro via File → Import.
```

**`both`** — combine both reports:
```
Trim complete!

Joined:  workspace/output/video/20260303_interview/interview_trimmed.mp4  (245 MB)
Project: workspace/output/video/20260303_interview/clips/interview_project.xml
  Clips:
    1. workspace/output/video/20260303_interview/clips/clip_001.mp4
    2. workspace/output/video/20260303_interview/clips/clip_002.mp4
    3. workspace/output/video/20260303_interview/clips/clip_003.mp4

Before:  8m 44s  →  After: 7m 32s  (1m 12s removed)

Import the .xml file in Premiere Pro via File → Import.
```

On failure: show the full error JSON from the executor and apply error handling
from `directives/video/auto-edit.md`.

### Timing breakdown

After reporting the mode-specific output, append a timing breakdown. Each executor
returns `elapsed_seconds` in its JSON output — collect these and display:

```
Timing:
  Transcription:   48.1s  (48s)
  Cutting:         15.7s  (16s)
  ─────────────────────────────────
  Total:           63.8s  (1m 4s)
```

Format rule: if under 60s show `Xs` (e.g. `48s`), if 60s or more show `Xm Xs` (e.g. `1m 4s`).

The "Total" is the sum of all executor times.

---

## Post-Processing Note

The `workspace/temp/video/<PROJECT>/` files (transcript.json, cut_spec.json) are kept
in place so the user can review them. Tell the user they can safely delete the
`workspace/temp/video/<PROJECT>/` folder once they're happy with the output.
