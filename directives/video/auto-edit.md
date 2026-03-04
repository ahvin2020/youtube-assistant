# Directive: Auto-Edit (Retake Detection + Script Alignment)

## Purpose
You are an expert video editor. Your job is to detect errors and retakes in a raw video
and produce a clean edit ready for post-production.

This directive supports two modes:
- **Retake-Only Mode** (`script_mode = false`) — no script provided; retakes detected from transcript patterns alone
- **Script-Guided Mode** (`script_mode = true`) — user provides a script; semantic alignment determines what to keep

The orchestrator sets the mode. Apply only the rules for the active mode, plus all
shared rules (output format, validation, Whisper artefacts).

---

## Mode: Retake-Only (no script provided)

> Apply this section when `script_mode = false`.

### How to Detect Retakes

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

### Definitions

**Successful take**: The final, clean delivery of a section where the presenter
conveys the content without restarting or breaking off.

**Bad take / retake**: Any of the following:
- The presenter restarts a section they already started ("wait, let me redo that", "ok from the top")
- The presenter stumbles mid-sentence and then restarts the same sentence
- Off-topic tangent, ad-lib commentary unrelated to surrounding content
- A half-finished sentence immediately followed by the same sentence re-delivered cleanly

### Detection Rules

1. Work through the transcript **section by section** (group related content into logical sections)
2. For each section, find **all spoken attempts**
3. Keep **only the FINAL attempt** of each section
4. Any earlier attempts at the same section are **removed**
5. Any speech not related to any surrounding content is **removed**
6. Preserve the **chronological order** of kept segments — do not reorder

---

## Mode: Script-Guided (script provided)

> Apply this section when `script_mode = true`.
> The script file is at `workspace/temp/video/<PROJECT>/script.txt`.

### Step 1 — Parse the Script Into Spoken Sections

Read the script and break it into numbered spoken sections. A "section" is a
paragraph or group of sentences that form a single complete idea.

**Non-spoken content to ignore**: The script may contain elements the presenter does
not say aloud. Strip these before matching:

1. **Markdown headers** — lines starting with `#`, `##`, `###`, etc.
   (e.g. `## Why Gold is Safe`). These are structural labels, not narration.
2. **URLs and hyperlinks** — bare URLs (`https://...`) or markdown links
   (`[text](url)`). The presenter does not read URLs aloud.
3. **Source citations and references** — lines like `Source: Bloomberg`,
   `[1] https://...`, `(Reuters, 2025)`, or any bracketed reference notation.
4. **Stage directions and notes** — text in brackets or parentheses that describe
   actions rather than speech: `[show chart]`, `(pause here)`, `[B-roll: city skyline]`.
5. **Metadata lines** — lines like `Word count: 1500`, `Format: long-form`,
   `Based on: outline.md`, `Tone: casual`.
6. **Blank lines and horizontal rules** — `---`, `***`, empty lines.

**What remains after stripping** is the spoken narration. Number each resulting
paragraph or logical group as Section 1, Section 2, etc.

### Step 2 — Semantic Matching (NOT Literal)

For each script section, scan the transcript chronologically to find all spoken attempts.

**Matching rule**: A transcript segment MATCHES a script section if the spoken words
convey the **same meaning**, even if the exact words differ. Presenters frequently
paraphrase their own script — this is expected and normal.

Good matches:
- Script: "The biggest risk with gold is storage and insurance"
  Spoken: "Now the main risk you face with gold, right, is you gotta store it and insure it" → MATCH

- Script: "DCA outperforms lump sum 30% of the time"
  Spoken: "Dollar cost averaging actually beats lump sum about 30 percent of the time" → MATCH

Not a match:
- Script says nothing about a personal anecdote the speaker tells → off-script
- Spoken words are a natural aside or joke between sections → off-script

**Partial matches**: If the speaker delivers only part of a script section before
restarting, that is a retake of that section, not a match. A match requires the
section's core meaning to be fully conveyed.

### Step 3 — Identify Retakes Within Matched Sections

For each script section:
1. Find ALL transcript segments that match it (chronological order)
2. If multiple matches exist → all earlier matches are **retakes**
3. The **LAST match** is the successful take → KEEP it
4. All earlier matches → add to `removed_segments` with reason `"retake — repeated Section N"`

### Step 4 — Handle Off-Script Content

Any transcript segments that do not match ANY script section are **off-script**.
Remove them with reason `"off-script — does not match any script section"`.

**Exception 1 — brief natural transitions**: If an off-script segment is:
- Less than 3 seconds long, AND
- Sits between two kept segments, AND
- Is a natural transition phrase (e.g. "okay so", "now", "alright", "moving on")

...then KEEP it. These provide natural pacing between sections.

**Exception 2 — garbled script content**: Before classifying ANY segment adjacent to a
keep segment as off-script, check whether it could be a **garbled version** of text that
IS in the script. Whisper frequently garbles:
- Transition words: "but anyway" → "a way", "furthermore" → gibberish,
  "and lastly" → "and finally"
- Opening phrases of the next script section
- Closing phrases of the previous script section

If an adjacent removed segment's meaning (even when garbled) matches text from the
neighbouring script section, it is NOT off-script — it is part of the delivery. KEEP it.

### Step 4b — Verify Opening and Closing Phrases

After determining the keep segments for each script section, verify that the **first few
words** and **last few words** of each script section are actually captured in the audio.

**Opening phrase check:**
For each script section, compare its first 3–6 words against the start of the kept
transcript segment. If the script section opens with words (e.g. "By default", "However",
"But anyway", "In fact", "And lastly", "Furthermore") that are NOT present in the first
transcript segment of the keep range:
1. Check the transcript segment(s) immediately BEFORE the keep range start — the opening
   words may sit in an earlier segment that was excluded
2. If found, extend the keep segment start backward to capture the opening phrase
3. If no transcript segment exists, extend the keep segment start by up to 1.5s — Whisper
   often omits the first word of a segment, but the audio is still there

**Closing phrase check:**
For each script section, compare its last 3–6 words against the end of the kept transcript
segment. If the script section ends with words (e.g. "yourself", "let's find out",
"ho seh bo", "touch wood ah") that are NOT present in the final transcript segment:
1. Check the transcript segment(s) immediately AFTER the keep range end
2. If found, extend the keep segment end forward to capture the closing phrase
3. If no transcript segment exists, extend the keep segment end by up to 1.5s — the
   presenter may have spoken words that Whisper did not transcribe

This step catches phrases that Whisper truncated, garbled, or missed entirely.

### Step 4c — Verify Sentence Completeness

Each keep segment should contain **complete sentences**, not partial ones. If a keep
segment starts or ends mid-sentence:
1. Check whether the missing part is in an adjacent removed segment
2. If so, either include that segment or extend the keep boundary
3. A sentence that the script shows as continuous should not be split across a gap

**Bridging phrases**: When content from the script logically connects two sections
(e.g. "...investing the difference yourself? Let us not waste any time..."), ensure
the connecting words are not lost in the gap between keep segments.

### Step 5 — Handle Unmatched Script Sections

If a script section has NO matching delivery in the transcript:
- Do NOT fabricate content
- Add a warning to the cut plan summary: "Warning: Script section N ('[first few words]...') has no matching delivery in the transcript."
- This may mean the presenter skipped that section or it may indicate a matching failure — flag it for the user

### Retake Detection Still Applies

Even in script-guided mode, apply retake detection within matched sections:
- If the final take of a section contains internal stumbles or restarts, split
  the keep_segment to exclude them (same within-segment validation rules apply)
- The "keep the final take" rule from retake-only mode applies identically here

### Step 6 — Systematic Internal Retake Scan (MANDATORY)

After assembling ALL keep segments, perform a **systematic scan of every keep segment**
for internal retakes. This is the most common source of errors and MUST be done
for every segment, not just ones that "look suspicious".

**For each keep segment:**
1. List every transcript segment that falls within the keep range
2. Read the text of each transcript segment in order
3. Check for ANY phrase of 4+ words that appears more than once within the range
4. Common internal retakes to watch for:
   - Presenter says a phrase, stumbles, then says the same phrase again cleanly
   - Whisper may garble the first attempt (e.g. "top up" → "pop up") making it
     look different, but the meaning is the same — both are retakes
   - The retake may be slightly different wording but convey the same content
5. When an internal retake is found: **split the keep segment** to exclude the
   earlier attempt. Keep only the FINAL delivery of the repeated phrase.

**This scan must cover every keep segment without exception.** A keep segment that
spans more than 10 seconds of transcript is especially likely to contain internal
retakes and deserves extra scrutiny.

### Step 7 — Verify Fixes Don't Introduce New Problems

When extending or adding segments to capture missing content:

1. **Never keep both takes** — if extending a segment to include a missing word (e.g.
   "yourself") means overlapping with the original delivery, REPLACE the original
   with the take that includes the missing word. Do not concatenate both.
2. **After trimming, verify no script content was lost** — after trimming a segment to
   remove a duplicate, re-check that the remaining segment still covers all the
   script content it's supposed to. If trimming removed script content, the trim
   went too far.
3. **After extending, check for internal retakes** — an extended segment may now
   contain a repeated phrase. Re-run the internal retake scan (Step 6) on any
   segment that was modified.

---

## Shared Rules (Both Modes)

### Output Format

Generate `workspace/temp/video/<PROJECT>/cut_spec.json` with this structure:

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

In script-guided mode, the `note` field should read `"Section N: [brief description]"`.

**Executor-applied padding (do not add manually):**
`apply_cuts.py` automatically applies:
- **0.1s start padding** — subtracts 0.1s from each segment start to prevent clipping
  the first phoneme (Whisper timestamps have no pre-roll buffer).
- **0.1s end padding** — adds 0.1s to each segment end so speech trails off naturally.
- **Adjacent-segment clamping** — when padding would cause two consecutive segments
  to overlap, both are clamped back to the original unpadded boundary so no audio
  is duplicated in the output.

Use raw Whisper timestamps in `cut_spec.json`. Do not pre-adjust for padding.

### Within-Segment Validation (MANDATORY — do this BEFORE writing cut_spec.json)

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

3. **Duplicate phrases at segment boundaries** — after assembling all keep segments,
   check every pair of consecutive keep segments for **repeated phrases**. The end of
   segment N and the start of segment N+1 must not contain the same words.

   Common patterns:
   - A false start at the end of segment N repeats the opening of segment N+1
     (e.g. both end/start with "now", "the second", "here", "because", "while the")
   - A retake within a keep segment where the presenter says a phrase, restarts,
     and says it again — only the final delivery should be kept

   **For each pair of consecutive keep segments:**
   - Read the last 1–2 transcript segments in the first keep range
   - Read the first 1–2 transcript segments in the next keep range
   - If they contain the same phrase (even partially), trim the earlier one to
     exclude the duplicate. Favour keeping the later (cleaner) delivery.

   **Also check within each keep segment:** If the same phrase appears twice
   inside a single keep segment (internal retake), split the segment to exclude
   the earlier occurrence.

   **Padding bleed awareness:** The executor adds ±0.1s padding. If two keep segments
   are separated by less than 0.5s, content in the gap may "bleed" into both via
   padding. When segments are this close, check whether the gap contains a false
   start that would be captured by padding, and extend the gap if needed.

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

### Validation Before Writing cut_spec.json

- [ ] All keep segments are non-overlapping
- [ ] Segments are in chronological order
- [ ] Each segment's end > start
- [ ] Total kept duration < source duration
- [ ] At least one segment is being kept
- [ ] Every transcript segment within each kept range has been individually examined
- [ ] No keep_segment bridges a silence gap > 0.5s (split at the gap instead)
- [ ] (Script-guided only) Every script section has at least one kept delivery OR is flagged as unmatched
- [ ] (Script-guided only) Opening phrase of each script section is captured in the keep range (Step 4b)
- [ ] (Script-guided only) Closing phrase of each script section is captured in the keep range (Step 4b)
- [ ] No duplicate phrases exist at consecutive keep segment boundaries (Step within-segment validation #3)
- [ ] No adjacent removed segment contains garbled versions of script content (Step 4 Exception 2)
- [ ] Each keep segment contains complete sentences, not partial ones (Step 4c)

### User Review (Auto-Accept)

Before calling the executor, show the user an informational summary:

1. A table of segments to be REMOVED with columns: Start | End | Duration | Reason
2. A summary: "X retakes found, Y seconds removed"

Then **proceed immediately** to apply cuts — do not wait for confirmation.

If no retakes are detected, tell the user and proceed without edits (produce unchanged output).

### Error Handling

- If the transcript file is missing: stop and tell the user to run the transcription step first
- If a segment's timestamps can't be determined precisely: use the nearest Whisper segment boundary and note the uncertainty to the user
- If the source video file does not exist: stop immediately, do not call any executor
- If the script file is missing when `script_mode = true`: stop and tell the user to provide the script again

### Whisper Transcription Artefacts

Whisper frequently garbles **colloquial, dialect, or code-switched speech** — especially
Singlish expressions like "wah", "sure or not", "lah", "leh", "sia", "hor", "alamak",
"can or not", "ho seh bo", "touch wood", "sibeh", "sian", etc.  These appear as nonsense
text (e.g. "Shion no a go so much" for "wah, sure or not") or are **not transcribed at all**.

**Before classifying any segment as "garbled / off-topic":**

1. Consider context — if it immediately follows a natural reaction (e.g. "wow"), it is
   almost certainly a continuation of that reaction, not random noise.
2. Short segments (< 3 seconds) with nonsense text between two kept segments are more
   likely misheard colloquial speech than genuine off-topic content.
3. When in doubt, **keep the segment** — a few extra seconds of genuine speech is far
   less damaging than cutting off the presenter mid-reaction.

**Untranscribed speech (gaps where Whisper produced nothing):**

Whisper sometimes produces NO transcript segment at all for colloquial expressions.
This creates a silence gap in the transcript, but the audio actually contains speech.

When the **script** contains a colloquial expression (e.g. "ho seh bo", "touch wood ah",
"wah") at the end or start of a section:
1. Check if there is a gap in the transcript at the corresponding point
2. If so, extend the keep segment by up to 2s into the gap to capture the
   untranscribed speech
3. The script is the ground truth for what was said — trust it over Whisper's gaps

**Executor bridge awareness when inserting segments in gaps:**

`apply_cuts.py` automatically bridges gaps < 1.0s between consecutive keep segments
(see `MIN_INTER_SEGMENT_GAP` in the executor). This means if you insert a keep segment
for untranscribed speech and the gap between it and the previous keep segment is < 1.0s,
the executor will bridge the gap — re-including any false starts or retakes you intended
to exclude.

**When adding a segment for untranscribed speech in a gap that also contains a false start:**
1. Place the new segment so its start is at least **1.0s** after the end of the
   previous keep segment. This prevents the executor from bridging and re-including
   the false start.
2. If the untranscribed expression is less than 1.0s after the previous segment,
   you may need to estimate where the false start ends and where the expression
   begins. Set the new segment start after the false start, with ≥ 1.0s gap from
   the previous segment.
3. The gap between the new segment and the NEXT keep segment can be < 1.0s — bridging
   is fine here if the gap only contains silence or natural pauses.

**Example:** Whisper gap from 835.809 to 839.116 contains both a "the second" false
start (~836.0-836.5) and "Touch wood ah" (~837.0-838.3). Previous segment ends at
835.809, next segment starts at 839.116. To capture only "Touch wood ah":
- Set new segment start at 837.000 (gap from 835.809 = 1.191s ≥ 1.0 → no bridge)
- Set new segment end at 838.300
- The gap from 838.300 to 839.116 = 0.816s → bridged (OK, just silence)

**Whisper phantom segments:**

Whisper also generates hallucinated segments — typically 1-second segments at regular
intervals (e.g. every N.821s) containing generic text like "OK", "All right", "Bye",
"Thank you", "Here we go", "I'll see you". These are NOT real speech. Ignore them
when determining segment boundaries. They are artefacts from background music or silence.

---

### What NOT to Do

- Show the cut plan for informational purposes before calling `apply_cuts.py`, but do not wait for confirmation
- Do not reorder segments — the output must maintain the original recording order
- Do not add, create, or generate video content — only extract and remove
- Do not match based on filler words alone ("um", "uh", "so") — look at semantic content
- **Do not merge transcript segments across a gap > 0.5s into a single keep_segment** — always split at the gap
- **Do not assume a silence gap within a kept block is empty** — the transcriber (Whisper) can miss brief utterances
- **Do not classify colloquial/dialect speech as garbled** — Whisper often misheards Singlish; see "Whisper Transcription Artefacts" above
- **(Script-guided only) Do not remove content solely because the wording differs from the script** — match by MEANING, not exact words
- **Do not classify transition phrases that appear in the script as "off-script"** — words like "but anyway", "and lastly", "however", "in fact", "furthermore" are often garbled by Whisper but are part of the actual script. Always check the script before removing.
- **Do not set keep segment boundaries so tightly that opening/closing words are lost** — Whisper timestamps can be late by up to 0.5s for the first word of a segment. Extend boundaries when the script shows words the transcript doesn't capture.
- **Do not leave duplicate phrases at consecutive keep segment boundaries** — if the end of keep segment N and the start of keep segment N+1 contain the same words, trim the earlier one.
