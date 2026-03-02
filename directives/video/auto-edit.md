# Directive: Auto-Edit (Retake Detection)

## Purpose
You are an expert video editor. Your job is to detect errors and retakes in a raw video
and produce a clean edit ready for post-production.

Retakes are detected from transcript patterns alone — no script is used.

---

## How to Detect Retakes

Identify bad takes by looking for these patterns in the transcript:

1. **Explicit restart cues** — presenter says "ok", "wait", "let me redo that", "from the top",
   "actually", "no wait", or similar, then repeats what they just said → remove all but the final delivery

2. **Half-finished sentence immediately re-delivered** — a sentence breaks off mid-way, then the
   same sentence begins again (even with different wording) → keep only the clean re-delivery

3. **Repeated passages** — any block of 8+ words spoken more than once → keep only the final occurrence

4. **Off-topic tangents** — extended speech clearly unrelated to the surrounding content
   (e.g. talking to someone off-camera, personal remarks mid-take) → remove

The transcript itself is the guide. Work through it chronologically.
Group obviously related content into logical sections, then apply the retake-detection
rules: keep only the final clean delivery of each section.

---

## Definitions

**Successful take**: The final, clean delivery of a section where the presenter
conveys the content without restarting or breaking off.

**Bad take / retake**: Any of the following:
- The presenter restarts a section they already started ("wait, let me redo that", "ok from the top")
- The presenter stumbles mid-sentence and then restarts the same sentence
- Off-topic tangent, ad-lib commentary unrelated to surrounding content
- A half-finished sentence immediately followed by the same sentence re-delivered cleanly

---

## Detection Rules

1. Work through the transcript **section by section** (group related content into logical sections)
2. For each section, find **all spoken attempts**
3. Keep **only the FINAL attempt** of each section
4. Any earlier attempts at the same section are **removed**
5. Any speech not related to any surrounding content is **removed**
6. Preserve the **chronological order** of kept segments — do not reorder

---

## Output Format

Generate `workspace/temp/<source_stem>/cut_spec.json` with this structure:

```json
{
  "source": "workspace/input/video.mp4",
  "keep_segments": [
    {
      "start": "HH:MM:SS",
      "end": "HH:MM:SS",
      "note": "brief description of what this segment contains"
    }
  ],
  "removed_segments": [
    {
      "start": "HH:MM:SS",
      "end": "HH:MM:SS",
      "reason": "retake — repeated [section name]"
    }
  ]
}
```

Timestamps must be in `HH:MM:SS` or `HH:MM:SS.ms` format, taken from the Whisper
transcript's `segments[].start` and `segments[].end` values.

**Executor-applied padding (do not add manually):**
`apply_cuts.py` automatically applies:
- **0.1s start padding** — subtracts 0.1s from each segment start to prevent clipping
  the first phoneme (Whisper timestamps have no pre-roll buffer).
- **0.1s end padding** — adds 0.1s to each segment end so speech trails off naturally.
- **Adjacent-segment clamping** — when padding would cause two consecutive segments
  to overlap, both are clamped back to the original unpadded boundary so no audio
  is duplicated in the output.

Use raw Whisper timestamps in `cut_spec.json`. Do not pre-adjust for padding.

## Within-Segment Validation (MANDATORY — do this BEFORE writing cut_spec.json)

After identifying a candidate kept range, **examine every individual transcript segment that falls
within that range**. Do not treat merged blocks as automatically clean.

**Check each segment inside a kept range for:**

1. **False starts of the next sentence** — a segment whose text begins the following
   sentence but does not finish it (e.g. "and the allocated" before "and the
   allocated gold is fully insured..."). These are stumbles; remove them by splitting
   the kept range so the stumble gap falls between two separate keep_segments.

2. **Silence gaps > 0.5 seconds between consecutive transcript segments** — large gaps
   may contain brief speech that Whisper failed to transcribe (e.g. a single word
   like "meanwhile" or "new maribank" said then restarted). For any gap > 0.5s within
   a candidate kept range, **split the range at the gap boundaries** so the gap is
   excluded from both keep_segments. Do not assume a gap is truly silent.

**Rule of thumb:** If you merged segments A → B with a gap of G seconds between them,
and G > 0.5s, always split into two separate keep_segments ending at A and starting at B.
Never bridge a gap > 0.5s inside a keep_segment.

**Example (correct):**
```json
{ "start": "00:01:29.389", "end": "00:01:48.035", "note": "...Le Freeport here in Singapore" },
{ "start": "00:01:50.266", "end": "00:01:54.543", "note": "and the allocated gold..." }
```
NOT:
```json
{ "start": "00:01:29.389", "end": "00:01:54.543", "note": "merged block — gap at 48-50s not checked" }
```

---

## Validation Before Writing cut_spec.json

- [ ] All keep segments are non-overlapping
- [ ] Segments are in chronological order
- [ ] Each segment's end > start
- [ ] Total kept duration < source duration
- [ ] At least one segment is being kept
- [ ] Every transcript segment within each kept range has been individually examined
- [ ] No keep_segment bridges a silence gap > 0.5s (split at the gap instead)

## User Review (Auto-Accept)

Before calling the executor, show the user an informational summary:

1. A table of segments to be REMOVED with columns: Start | End | Duration | Reason
2. A summary: "X retakes found, Y seconds removed"

Then **proceed immediately** to apply cuts — do not wait for confirmation.

If no retakes are detected, tell the user and proceed without edits (produce unchanged output).

## Error Handling

- If the transcript file is missing: stop and tell the user to run the transcription step first
- If a segment's timestamps can't be determined precisely: use the nearest Whisper segment boundary and note the uncertainty to the user
- If the source video file does not exist: stop immediately, do not call any executor

## Audio Cleanup (Pre-Processing)

When the user opts for audio cleanup (Step 0 in the orchestrator):

- **Auto-detect preset** — run `--analyze` first and use the `recommended_preset` from the output
- `voice` — suitable for most talking-head recordings (moderate denoise)
- `light` — recording environment is already good (minor level tweaks only)
- `heavy` — significant background noise or reverb (aggressive denoise)
- The user can override the auto-detected preset by explicitly requesting one
- The cleaned file goes to `workspace/temp/<STEM>/`, NOT `workspace/output/`
- The original input file is **NEVER modified**
- All subsequent pipeline steps (transcription, cuts) use the cleaned file as the source
- The cleaned audio is an intermediate artifact — the final output from `apply_cuts.py` inherits the cleaned audio

### Pipeline Stages
The executor uses a multi-stage pipeline:
1. Extract audio to 48kHz mono WAV
2. Process: highpass → arnndn (RNNoise ML denoiser) → deesser → compressor → limiter
3. Two-pass loudnorm: measure loudness, then apply linear normalization
4. Mux processed audio back with original video (`-c:v copy`)

### Denoise Backends
- **arnndn** (default) — RNNoise neural model built into ffmpeg. Auto-downloads a 3MB model on first use to `~/.cache/clean_audio/cb.rnnn`
- **afftdn** (fallback) — basic FFT denoiser. Used automatically if arnndn model download fails
- Override with `--denoise-backend arnndn|afftdn`

### Analyze Mode
Run `--analyze` to inspect audio before cleaning:
```
python3 executors/video/clean_audio.py --analyze <input>
```
Returns loudness measurements and a recommended preset without processing the file.

---

## Whisper Transcription Artefacts

Whisper frequently garbles **colloquial, dialect, or code-switched speech** — especially
Singlish expressions like "wah", "sure or not", "lah", "leh", "sia", "hor", "alamak",
"can or not", etc.  These appear as nonsense text (e.g. "Shion no a go so much" for
"wah, sure or not").

**Before classifying any segment as "garbled / off-topic":**

1. Consider context — if it immediately follows a natural reaction (e.g. "wow"), it is
   almost certainly a continuation of that reaction, not random noise.
2. Short segments (< 3 seconds) with nonsense text between two kept segments are more
   likely misheard colloquial speech than genuine off-topic content.
3. When in doubt, **keep the segment** — a few extra seconds of genuine speech is far
   less damaging than cutting off the presenter mid-reaction.

---

## What NOT to Do

- Show the cut plan for informational purposes before calling `apply_cuts.py`, but do not wait for confirmation
- Do not reorder segments — the output must maintain the original recording order
- Do not add, create, or generate video content — only extract and remove
- Do not match based on filler words alone ("um", "uh", "so") — look at semantic content
- **Do not merge transcript segments across a gap > 0.5s into a single keep_segment** — always split at the gap
- **Do not assume a silence gap within a kept block is empty** — the transcriber (Whisper) can miss brief utterances
- **Do not classify colloquial/dialect speech as garbled** — Whisper often misheards Singlish; see "Whisper Transcription Artefacts" above
