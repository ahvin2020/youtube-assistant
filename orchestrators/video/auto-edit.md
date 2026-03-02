# Orchestrator: Auto-Edit Pipeline

This orchestrator coordinates the pipeline to automatically detect and remove
errors and retakes from a raw video. Retakes are detected from transcript
patterns alone.

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

## Steps 0 & 1 — Audio Cleanup + Transcription

The user's audio cleanup preference was already collected during the `/cut` command setup.
Do **not** ask again.

### If audio cleanup is enabled — analyze, then run cleanup + transcription in parallel

Audio cleanup does not alter timing, so the raw file's Whisper timestamps align perfectly
with the cleaned file. Exploit this by running cleanup and transcription concurrently.

#### Step 0a — Analyze audio (fast, ~2s)

Run the analyzer first to auto-detect the best preset:

```bash
python3 executors/video/clean_audio.py --analyze "workspace/input/<source_file>"
```

Read `recommended_preset` from the JSON output. Use it as the cleanup preset unless the
user explicitly requested a specific preset (e.g. `--preset light`).

Report: "Audio analysis: measured X LUFS, recommended preset: Y"

#### Step 0b — Launch cleanup + transcription in parallel

**Launch both commands at the same time** (use `run_in_background` for one or both):

```bash
# Background: clean the audio (use the analyzed preset)
python3 executors/video/clean_audio.py "workspace/input/<source_file>" "workspace/temp/<STEM>/<STEM>_cleaned<ext>" --preset <recommended_preset>

# Foreground (or also background): transcribe the RAW file
python3 executors/video/transcribe.py "workspace/input/<source_file>" "workspace/temp/<STEM>/transcript.json" --language en --model small
```

**Wait for both to finish** before proceeding.

On cleanup success:
- Report: "Audio cleaned. Preset: \<preset\>. Output: workspace/temp/\<STEM\>/\<STEM\>_cleaned\<ext\>"
- **Update `source_file`** for the cut_spec and apply_cuts steps to use the cleaned file:
  `source_file = workspace/temp/<STEM>/<STEM>_cleaned<ext>`

On cleanup failure: show the full error JSON. Common fixes:
- `ffmpeg not found` → `brew install ffmpeg`

On transcription success: report "Transcription complete. X segments found."

On transcription failure: show the full error JSON and stop. Common fixes:
- `openai-whisper not installed` → `pip install openai-whisper`
- `ffmpeg not found` → `brew install ffmpeg`

If either task fails, stop the pipeline.

The user may also request a different cleanup preset (`light`, `heavy`) or custom options
(e.g. `--no-eq`, `--target-lufs -16`). Pass those through to the executor, overriding
the analyzer's recommendation.

### If audio cleanup is skipped — transcribe only

```bash
python3 executors/video/transcribe.py "workspace/input/<source_file>" "workspace/temp/<STEM>/transcript.json" --language en --model small
```

If `workspace/temp/<STEM>/transcript.json` already exists from a previous run, overwrite it —
always re-transcribe to ensure the transcript matches the current source file.

Wait for this to complete. It may take 1–3 minutes depending on video length.

On success: report to the user: "Transcription complete. X segments found."

On failure: show the full error JSON and stop.

---

## Step 2 — Analyze and Build Cut Spec (Claude's Intelligence Step)

Read `directives/video/auto-edit.md` and apply the retake-detection rules.

Inputs:
- `workspace/temp/<STEM>/transcript.json`

Output:
- `workspace/temp/<STEM>/cut_spec.json`

Work through the transcript chronologically. Group related content into logical
sections. For each section, find all spoken attempts and keep only the final
delivery. Remove all earlier attempts and any off-topic content.

### ⚠️ Output Token Budget — CRITICAL

**Do NOT print or echo `cut_spec.json` contents in the chat response.** Writing it in the
response will exceed the output token limit and abort the pipeline.

Instead:
1. Do your analysis silently (internal reasoning only)
2. Write the result directly to `workspace/temp/<STEM>/cut_spec.json` using the **Write file tool**
3. In the chat, report only a brief summary:
   - Number of retakes / bad takes found
   - Total duration to be removed
   - Any segments you were uncertain about (flag by timestamp only)

Keep all JSON generation inside the Write tool call — never in the response text.

---

## Step 2.5 — Validate Cut Spec (Gap/Overlap Check)

Run the validator immediately after writing `cut_spec.json`:

```bash
python3 executors/video/validate_cut_spec.py "workspace/temp/<STEM>/transcript.json" "workspace/temp/<STEM>/cut_spec.json"
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

Do **not** pause for user confirmation. Proceed directly to Step 4.

---

## Step 4 — Apply Cuts

All outputs go into a per-video folder: `workspace/output/<STEM>/`.
Create it before running: `mkdir -p workspace/output/<STEM>`.

Run the executor **once**. The command depends on which output mode(s) the user selected in Step 1.5.

**Single joined file only:**
```bash
python3 executors/video/apply_cuts.py "workspace/temp/<STEM>/cut_spec.json" "workspace/output/<STEM>/{source_stem}_trimmed{ext}" --temp-dir "workspace/temp/<STEM>" --mode joined
```

**Video project only:**
```bash
python3 executors/video/apply_cuts.py "workspace/temp/<STEM>/cut_spec.json" "workspace/output/<STEM>/clips" --temp-dir "workspace/temp/<STEM>" --mode project
```

**Both** (single command — extracts segments once, produces both outputs):
```bash
python3 executors/video/apply_cuts.py "workspace/temp/<STEM>/cut_spec.json" "workspace/output/<STEM>/clips" --temp-dir "workspace/temp/<STEM>" --mode both --joined-output "workspace/output/<STEM>/{source_stem}_trimmed{ext}"
```

For `project` and `both` modes, the positional output argument is the **clips directory**
(not a file). The executor creates it and writes numbered clips inside.

### Reporting by mode

**`joined`**:
```
Trim complete!
Output:  workspace/output/interview/interview_trimmed.mp4
Before:  8m 44s  →  After: 7m 32s  (1m 12s removed)
Size:    245 MB
```

**`project`**:
```
Trim complete! Video project ready:
  Project: workspace/output/interview/clips/interview_project.xml
  Clips:
    1. workspace/output/interview/clips/clip_001.mp4
    2. workspace/output/interview/clips/clip_002.mp4
    3. workspace/output/interview/clips/clip_003.mp4
Before:  8m 44s  →  After: 7m 32s  (1m 12s removed)

Import the .xml file in Premiere Pro via File → Import.
```

**`both`** — combine both reports:
```
Trim complete!

Joined:  workspace/output/interview/interview_trimmed.mp4  (245 MB)
Project: workspace/output/interview/clips/interview_project.xml
  Clips:
    1. workspace/output/interview/clips/clip_001.mp4
    2. workspace/output/interview/clips/clip_002.mp4
    3. workspace/output/interview/clips/clip_003.mp4

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
  Audio cleanup:   32.4s
  Transcription:   48.1s
  Cutting:         15.7s
  ─────────────────────
  Total:           96.2s
```

If audio cleanup was skipped, omit that line. The "Total" is the sum of all
executor times (they may overlap if cleanup + transcription ran in parallel,
so wall-clock time may be shorter — note this if relevant).

---

## Post-Processing Note

The `workspace/temp/<STEM>/` files (transcript.json, cut_spec.json) are kept
in place so the user can review them. Tell the user they can safely delete the
`workspace/temp/<STEM>/` folder once they're happy with the output.
