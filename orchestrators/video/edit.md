# Orchestrator: Video Edit Pipeline (Cut + Graphics Pass)

This orchestrator coordinates the full video editing pipeline through two phases:
1. **Phase 1 — Cut**: Detect and remove retakes, produce a clean edit
2. **Phase 2 — Graphics Pass**: Add motion graphics, text overlays, data visualizations, sound effects

The `/edit` command sets `start_phase` to either `"cut"` or `"graphics"`.
- If `start_phase = "cut"`: run Phase 1 then Phase 2
- If `start_phase = "graphics"`: skip Phase 1, run Phase 2 only

Follow every step in order. Do not skip steps. Do not proceed to the next step if
the current step produces an error.

---

## Pre-Flight Checklist

Before starting, verify:
- [ ] `source_file` exists (in `workspace/input/video/` or `workspace/output/video/`)
- [ ] Derive `STEM` = source filename without extension
- [ ] `PROJECT` is set by the `/edit` command (format: `YYYYMMDD_<slug>`)
- [ ] `TEMP_DIR` = `workspace/temp/video/<PROJECT>/` — create if not: `mkdir -p workspace/temp/video/<PROJECT>`
- [ ] `workspace/output/video/<PROJECT>/` exists (create if not)
- [ ] If `script_mode = true`: verify `workspace/temp/video/<PROJECT>/script.txt` exists and is non-empty
- [ ] Remotion dependencies (for Phase 2): `ls remotion/node_modules/remotion 2>/dev/null`
  - If missing: `cd remotion && npm install`

Write initial `state.json` to `workspace/temp/video/<PROJECT>/state.json`:
```json
{
  "phase": "<start_phase>",
  "start_phase": "<cut | graphics>",
  "source_video": "<source_file_path>",
  "script_mode": "<true | false>",
  "output_mode": "<joined | project | both>",
  "content_slug": "<slug>",
  "created": "<YYYY-MM-DD>",
  "updated": "<YYYY-MM-DD>"
}
```

---

# Phase 1 — Cut

> Skip this entire phase if `start_phase = "graphics"`.

## Step 1 — Transcription

**Model and engine selection:**
The transcriber auto-detects the best engine (MLX on Apple Silicon, faster-whisper otherwise)
and defaults to `large-v3` for maximum accuracy. Override with `--engine` and `--model` if needed.

- **Default** (recommended): `--model medium` (auto MLX engine on Apple Silicon, ~1.5GB)
- **Retake-only** (`script_mode = false`): `--model base` is sufficient for detecting repeated takes
- **Fallback**: `--engine faster-whisper --model small --workers 4` (CPU, slower)

```bash
python3 executors/video/transcribe.py "<source_file_path>" "workspace/temp/video/<PROJECT>/transcript.json" --language en
```

Always re-transcribe (overwrite if exists). Wait for completion (1-3 minutes for small, ~1 minute for base).

On success: report "Transcription complete. X segments found."
On failure: show the full error JSON. Common fixes:
- `faster-whisper is not installed` -> `pip install faster-whisper`
- `ffmpeg not found` -> `brew install ffmpeg`

## Step 2 — Analyze and Build Cut Spec (Claude Subagent)

### MUST USE SUBAGENT — Output Token Budget

Transcripts are large (400+ segments, 3000+ lines). **Always delegate Step 2 to a subagent**
using the Agent tool (`subagent_type: general-purpose`).

**Model selection by mode:**
- **Retake-only** (`script_mode = false`): use default model (Sonnet) — retake detection is pattern matching, doesn't need Opus-level reasoning
- **Script-guided** (`script_mode = true`): use `model: "opus"` — semantic alignment between spoken words and written script requires deep reasoning

### Subagent prompt template

Provide the subagent with:
1. The transcript data **converted to TOON format** (not raw JSON). Read
   `transcript.json`, convert with `toon.encode()`, and pass the TOON string
   inline in the subagent prompt. This saves ~50% tokens on 400+ segment transcripts.
   ```python
   import json, toon
   with open(transcript_path) as f:
       data = json.load(f)
   toon_str = toon.encode(data)
   ```
2. The script content (if script_mode) and output path for cut_spec.json
3. The active mode (`script_mode` true or false)
4. The full rules from `directives/video/edit.md` Phase 1 for the active mode — copy the
   relevant mode section plus the shared cut rules into the subagent prompt
5. Instructions to write `cut_spec.json` using the Write tool (output stays JSON)
6. Instructions to return a brief summary:
   - **Retake-Only**: retakes found, total duration to remove, uncertain segments
   - **Script-Guided**: sections matched/unmatched, retakes, off-script removed, total duration

### Output
- `workspace/temp/video/<PROJECT>/cut_spec.json`

**Do NOT read the transcript in the main conversation.**

## ~~Step 2.5 — Validate Cut Spec~~ (DISABLED)

> Skipped. `validate_cut_spec.py` only checks structural issues (gaps, overlaps) which
> the subagent already handles. It has never caught an actionable issue in practice.

## ~~Step 2.7 — Audio-Based Cut Verification~~ (DISABLED)

> Skipped. `verify_cut.py` checks for doubles and missing content using transcript text,
> but the real errors are missing words in Whisper gaps — which it cannot detect. The
> subagent's Step 4b (Script Boundary Alignment) in the directive now handles this
> proactively during cut spec generation. User manual QA catches anything remaining.

## Step 3 — Present Cut Plan (Auto-Accept)

Show a clear summary of cuts, then **proceed immediately to Step 4**.

```
SEGMENTS TO REMOVE:
---
 #  Start      End        Duration   Reason
---
 1  00:01:23   00:02:10   0:47       Retake — repeated intro
 2  00:05:33   00:05:58   0:25       Off-script tangent
---
Total removed: 1m 12s  |  2 retakes detected
```

If `script_mode = true`, also show script coverage (matched/unmatched sections).

Do **not** pause for confirmation.

## Step 4 — Apply Cuts

Run the executor **once**. The command depends on output mode:

**Single joined file only:**
```bash
python3 executors/video/apply_cuts.py "workspace/temp/video/<PROJECT>/cut_spec.json" "workspace/output/video/<PROJECT>/{source_stem}_trimmed{ext}" --temp-dir "workspace/temp/<STEM>" --mode joined
```

**Video project only:**
```bash
python3 executors/video/apply_cuts.py "workspace/temp/video/<PROJECT>/cut_spec.json" "workspace/output/video/<PROJECT>/clips" --temp-dir "workspace/temp/<STEM>" --mode project
```

**Both:**
```bash
python3 executors/video/apply_cuts.py "workspace/temp/video/<PROJECT>/cut_spec.json" "workspace/output/video/<PROJECT>/clips" --temp-dir "workspace/temp/<STEM>" --mode both --joined-output "workspace/output/video/<PROJECT>/{source_stem}_trimmed{ext}"
```

### Report cut results

Show: output file(s), duration before/after, size, timing breakdown.

For project mode, remind: _"Import the .xml file in Premiere Pro via File -> Import."_

### Update state

Update `state.json` phase to `"graphics"`.

---

# Phase 2 — Graphics Pass

## Step 5 — Transcribe for Graphics

The graphics pass needs a transcript with timestamps relative to the video being enhanced.

**If Phase 1 ran** (cut phase completed):
The source for graphics is the trimmed output. Re-transcribe it — the Phase 1 transcript
has raw-video timestamps that don't match the trimmed video:
```bash
python3 executors/video/transcribe.py "<trimmed_video_path>" \
  "workspace/temp/video/<PROJECT>/graphics_transcript.json" \
  --language en --model small --workers 4
```

**If starting directly at graphics** (`start_phase = "graphics"`):
The source is whatever video the user provided. Transcribe it:
```bash
python3 executors/video/transcribe.py "<source_file_path>" \
  "workspace/temp/video/<PROJECT>/graphics_transcript.json" \
  --language en --model small --workers 4
```

**Important**: All graphics timestamps are **0-based** relative to the video being enhanced.

## Step 6 — Graphics Analysis (Opus Subagent)

This is the core creative intelligence step. Delegate to an **Opus** subagent.

Before spawning the subagent, convert `graphics_transcript.json` to **TOON format**
and pass the TOON string inline in the prompt (same `toon.encode()` pattern as Step 2).

The subagent must:
1. Read the script from `workspace/temp/video/<PROJECT>/script.txt`
2. Use the **TOON-encoded transcript** provided inline in the prompt
3. Read the directive from `directives/video/edit.md` (Phase 2: Graphics Pass section)
4. Read the channel profile from `memory/channel-profile.md` (for tone/style context)
5. Read the editing style reference from `memory/editing-style.md` (for visual style, animation presets, color palette, typography, density targets, and do's/don'ts derived from 6 reference channels)

The subagent then:
1. **Splits the script into sections** — identify natural topic breaks, label each
2. **Aligns sections to transcript timestamps** — map to Whisper timestamps
3. **Generates enhancement suggestions** for each section:
   - Enhancement type (from the directive's taxonomy)
   - Precise start/end timestamps (aligned to word boundaries)
   - Full content specification (text, data, animation presets, positions)
   - Rationale for each enhancement
4. **Writes `graphics_spec.json`** to `workspace/temp/video/<PROJECT>/`

The spec must follow the schema defined in `remotion/src/lib/types.ts`.

**Critical fields to populate:**
- `source_video`: absolute path to the video file being enhanced
- `fps`: 30 (or detect via ffprobe)
- `duration_seconds`: from transcript or ffprobe
- `width`/`height`: 1920x1080 (or detect)
- `global_style`: use channel brand colors from `memory/channel-profile.md` if available
- `sections`: with aligned timestamps
- `enhancements`: all suggestions with complete content objects

**Model override**: Use `model: "opus"` — creative visual storytelling judgment required.

## Step 7 — Validate Graphics Spec

```bash
python3 executors/enhance/validate_spec.py \
  "workspace/temp/video/<PROJECT>/graphics_spec.json"
```

If invalid: show issues, have subagent fix, re-validate. Loop until valid.

## Step 8 — User Review

Present the graphics plan as a readable summary:

```
GRAPHICS PLAN — <PROJECT>
===
Video: <duration> | <N> sections | <M> enhancements

SECTION 1: <label> (<start> - <end>)
  [TEXT]    <start>-<end>  "<text>" — <animation>, <position>
  [ZOOM]    <start>-<end>  <zoom_type> <from>x -> <to>x
  [SFX]     <start>        <sfx_id> (vol: <volume>)
  [SOURCE]  <start>-<end>  <source_url>, <position>
  ...
```

Wait for user feedback. Handle modification requests:
- "Remove #enh_003" -> delete from spec
- "Move #enh_002 to 0:04-0:09" -> update timing
- "Add text at 1:30 saying 'Key Insight'" -> add new enhancement
- "Change style to minimal" -> update global_style
- "Looks good" / "Proceed" -> continue to Step 9

Apply modifications directly to `graphics_spec.json`. Re-validate after changes.

## Step 9 — Asset Preparation

```bash
python3 executors/enhance/prepare_assets.py \
  --spec "workspace/temp/video/<PROJECT>/graphics_spec.json" \
  --output-dir "workspace/temp/video/<PROJECT>/assets/"
```

This captures screenshots for `source_overlay` enhancements and verifies SFX IDs.

If assets fail, offer to: remove the enhancement, provide manually, or skip.

## Step 10 — Interactive Editor Preview

```bash
node executors/enhance/render_preview.js \
  --spec "workspace/temp/video/<PROJECT>/graphics_spec.json" \
  --port 3100
```

Tell the user:
**"Editor is running at http://localhost:3100. You can:**
- **Scrub through the timeline to preview enhancements**
- **Select and edit element properties in the sidebar**
- **Tell me to make changes and I'll update the spec (editor auto-refreshes)"**

Interactive loop: user requests changes -> update spec -> editor hot-reloads.

When user says "render", "export", or "done", proceed to Step 11.

## Step 11 — Final Render

```bash
node executors/enhance/render_final.js \
  --spec "workspace/temp/video/<PROJECT>/graphics_spec.json" \
  --output "workspace/output/video/<PROJECT>/<STEM>_final.mp4" \
  --codec h264 --crf 18
```

Report: output file path, size, render time.

## Step 12 — Cleanup

Copy the final spec to the output directory:
```bash
cp "workspace/temp/video/<PROJECT>/graphics_spec.json" \
   "workspace/output/video/<PROJECT>/graphics_spec.json"
```

Update `state.json` phase to `"complete"`.

Report final summary:
- Video: `workspace/output/video/<PROJECT>/<STEM>_final.mp4`
- Spec: `workspace/output/video/<PROJECT>/graphics_spec.json`
- Enhancement count by type
- Sections covered

### Timing breakdown

Collect `elapsed_seconds` from all executor calls and display:

```
Timing:
  Transcription (cut):     48.1s
  Cutting:                 15.7s
  Transcription (graphics): 32.4s
  Rendering:               120.3s
  ---
  Total:                   216.5s  (3m 37s)
```

---

## Post-Processing Note

The `workspace/temp/video/<PROJECT>/` files are kept so the user can review them.
Tell the user they can safely delete the temp folder once satisfied.
