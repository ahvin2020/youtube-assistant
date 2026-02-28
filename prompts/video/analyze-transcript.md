# Prompt: Analyze Transcript and Build Cut Spec

This prompt has two modes. Read the mode set in the orchestrator and follow only
the relevant section.

---

# MODE A — Script Mode

## Prompt: Analyze Transcript Against Script

You are performing a **semantic alignment** between a video transcript and a script.
Your goal is to produce a `cut_spec.json` that keeps only the final successful delivery
of each script section and removes all retakes, restarts, and off-script content.

---

## Step 1 — Read Both Files

Read the transcript from `workspace/temp/transcript.json`.
Read the script from `workspace/temp/script.txt`.

The transcript contains a `segments` array. Each segment has:
- `start`: timestamp in seconds (float)
- `end`: timestamp in seconds (float)
- `text`: what was spoken in that segment

---

## Step 2 — Break the Script Into Sections

Identify the natural sections of the script. A "section" is typically:
- A paragraph
- A distinct topic or point being made
- A sentence or group of sentences that form a complete idea

Number them: Section 1, Section 2, Section 3, etc.

---

## Step 3 — Semantic Matching (NOT Literal)

For each script section, scan the transcript to find all spoken attempts.

**Matching rule**: A transcript segment MATCHES a script section if the spoken words
convey the SAME MEANING as the script section, even if the exact words differ.

Good match examples:
- Script: "Today we're going to build a YouTube assistant"
  Spoken: "So what we're doing today is building a YouTube assistant" → MATCH ✓

- Script: "First, install the dependencies"
  Spoken: "The first thing you need to do is get your dependencies installed" → MATCH ✓

Not a match:
- Script says nothing about a personal story the speaker tells → NO MATCH (off-script)
- Spoken words are a natural aside/joke between sections → off-script, remove

---

## Step 4 — Identify Retakes

For each script section:
1. List all transcript segments that match it (in chronological order)
2. If there is more than one match → all earlier ones are RETAKES
3. The LAST match is the successful take — KEEP it
4. All earlier matches (retakes) → ADD to removed_segments

Also mark for removal:
- Any transcript segments that don't match any script section
- Sentence fragments immediately followed by the same sentence restarted

---

## Step 5 — Build the Keep List

The `keep_segments` array should contain all NON-retake segments in chronological order.
Use the transcript segment timestamps directly.

Convert seconds to `HH:MM:SS` format:
- `h = int(seconds // 3600)`
- `m = int((seconds % 3600) // 60)`
- `s = seconds % 60`
- Format: `f"{h:02d}:{m:02d}:{s:06.3f}"`

---

## Step 6 — Handle Edge Cases

**Filler words between sections** (e.g., "um, ok, so..."): If these appear as isolated
segments between script sections, remove them. If they're attached to a kept segment,
leave them — don't over-edit natural speech.

**Long silences**: Include the silence with the adjacent kept segment (don't create
a separate cut point for a pause).

**Unclear audio**: If a segment is inaudible or unclear, include it as "kept" and add
a note in the cut_spec. Don't guess at its content.

**Presenter says something not in script but clearly relevant** (a helpful clarification,
a natural transition): Use judgment. If it flows naturally with the kept content around
it and is brief, include it. If it's a major digression, remove it.

---

## Step 7 — Write the cut_spec.json

Write to `workspace/temp/cut_spec.json`:

```json
{
  "source": "<path from transcript.json source field>",
  "keep_segments": [
    {
      "start": "HH:MM:SS.mmm",
      "end": "HH:MM:SS.mmm",
      "note": "Section N: [brief description]"
    }
  ],
  "removed_segments": [
    {
      "start": "HH:MM:SS.mmm",
      "end": "HH:MM:SS.mmm",
      "reason": "[retake of Section N / off-script / fragment]"
    }
  ]
}
```

---

## Step 8 — Sanity Check Before Reporting

Before presenting to the user, verify:
- [ ] `keep_segments` covers the full script content (each section has a kept delivery)
- [ ] No keep_segments overlap each other
- [ ] Segments are in chronological order
- [ ] All timestamps are valid HH:MM:SS format

If any script section has NO matching spoken delivery, note it to the user:
"Warning: Script section [N] ('...') has no matching delivery in the transcript."

---

# MODE B — No-Script Mode

## Prompt: Auto-Detect Errors from Transcript and Silence Data

You are cleaning up a raw video with no reference script. Use the transcript and
silence data to detect and remove errors, dead air, and obvious restarts.

---

## Step 1 — Read Both Files

Read `workspace/temp/transcript.json` — the Whisper transcript.
Read `workspace/temp/silences.json` — silence segments detected by ffmpeg.

The transcript `segments` array: each item has `start` (seconds), `end` (seconds), `text`.
The silences array: each item has `start` (seconds), `end` (seconds), `duration` (seconds).

---

## Step 2 — Mark Silence Gaps for Removal

For each silence in `silences.json`:
- It is already filtered to > 0.5s by the detector
- Add it to `removed_segments` with reason `"silence (Xs gap)"`
- Note: silences may fall between transcript segments or within them

---

## Step 3 — Detect Restarts and Fragments

Scan the transcript segments sequentially. Look for:

1. **Sentence fragment + restart**: A segment that ends mid-sentence (no `.`, `?`, `!`)
   immediately followed by a segment that begins with the same word(s).
   → Mark the fragment as removed, reason: `"restart — fragment before clean delivery"`

2. **Repeated phrase within 30 seconds**: The same sentence or phrase appears twice
   within 30 seconds of each other in the transcript.
   → Mark the earlier occurrence as removed, reason: `"repeated phrase — kept last delivery"`

3. **Filler-only segment**: A segment whose text contains only filler words
   (`um`, `uh`, `okay`, `so`, `alright`, `like`, `right`) with no content words.
   → Mark as removed, reason: `"filler-only segment"`

---

## Step 4 — Build Keep Segments

The keep segments are everything NOT marked for removal, merged into contiguous
ranges where possible.

- Sort all removed intervals chronologically
- The kept intervals are the gaps between removed intervals (plus start-of-video to
  first removal, and last removal to end-of-video)
- Use transcript segment boundaries for precision — align keep/remove boundaries to
  the nearest segment start/end timestamp
- Convert seconds to `HH:MM:SS.mmm` format (same formula as script mode)

---

## Step 5 — Write cut_spec.json

Write to `workspace/temp/cut_spec.json` using the same format as script mode:

```json
{
  "source": "<path from transcript.json source field>",
  "keep_segments": [
    {
      "start": "HH:MM:SS.mmm",
      "end": "HH:MM:SS.mmm",
      "note": "clean speech segment"
    }
  ],
  "removed_segments": [
    {
      "start": "HH:MM:SS.mmm",
      "end": "HH:MM:SS.mmm",
      "reason": "silence (1.2s gap) / restart — fragment / repeated phrase / filler-only"
    }
  ]
}
```

---

## Step 6 — Sanity Check

Before presenting to the user, verify:
- [ ] No keep_segments overlap each other
- [ ] Segments are in chronological order
- [ ] Each segment's end > start
- [ ] Total kept duration < source duration
- [ ] At least one segment is kept
