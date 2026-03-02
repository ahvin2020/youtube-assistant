# Orchestrator: Topic Research Pipeline

This orchestrator coordinates a multi-phase, iterative research workflow. Unlike the
video editing pipeline (which runs to completion), this pipeline **pauses for user input
at every step** and never advances phases without explicit instruction.

Follow every step in order. Do not skip steps.

---

## Pre-Flight — Session Resume or New Project

### Check for existing projects

```bash
ls workspace/temp/research/ 2>/dev/null
```

If directories exist, read each project's `state.json` and present a list:

```
Existing research projects:
  1. dca-vs-lump-sum (Phase: outline, Last updated: 2026-02-28)
  2. fed-rate-cut-impact (Phase: research, Last updated: 2026-03-01)

Resume one of these, or start a new project?
```

If the user chooses to resume: read the project's `state.json`, then skip to the
current phase's iterative loop (pick up where they left off by reading the existing
`brief.md`, `outline.md`, or `script.md`).

If no projects exist or the user wants a new one: proceed to Step 1.

---

## Step 1 — Gather Topic, Format, and Context

Ask the user:
1. **What topic do you want to write about?**
2. **What format?** Long-form video, short-form reel, or spin-off reels from an existing project?
3. **Any specific angle, context, or constraints?** (e.g., "focused on Singapore investors",
   "I want to argue against this", "news just broke today")

If the user chose **spin-off reels**: jump to the [Spin-Off Reels](#spin-off-reels) section below.

From the user's answer, determine:
- **Format**: `long-form` or `short-form`
- **Research mode**: Topic Deep-Dive, News Reaction, Strategy Comparison, or AI Scenario Analysis
  (see `directives/research/topic.md` for definitions)
- **Slug**: a URL-safe lowercase version of the topic (e.g., "DCA vs Lump Sum" → `dca-vs-lump-sum`)

**For short-form only**: ask whether the user wants a research phase or wants to skip
straight to outlining. If they already know their point, research can be skipped.

Create the project directory and state file:

```bash
mkdir -p "workspace/temp/research/<slug>/transcripts"
mkdir -p "workspace/output/research/<slug>"
```

Write `workspace/temp/research/<slug>/state.json`:
```json
{
  "topic": "<user's topic>",
  "slug": "<slug>",
  "format": "<long-form | short-form>",
  "mode": "<research_mode>",
  "phase": "research",
  "tone_override": null,
  "parent_project": null,
  "created": "<YYYY-MM-DD>",
  "updated": "<YYYY-MM-DD>"
}
```

Tell the user which format and mode were detected and confirm before proceeding.

If short-form and user chose to skip research: set `phase` to `"outline"` and jump
to Phase 2.

---

## Phase 1 — Research (Iterative)

> **Short-form note**: If the user chose short-form and opted to skip research,
> this phase is skipped entirely. Jump to Phase 2.

### Initial Research Round

Based on the detected mode, perform the actions specified in `directives/research/topic.md`.
Adjust depth based on format:

**Long-form** — full depth:
1. Run web searches relevant to the topic (use WebSearch tool)
2. Find 3–5 relevant YouTube videos — fetch their transcripts:
   ```bash
   python3 executors/research/fetch_transcript.py "<youtube_url>" "workspace/temp/research/<slug>/transcripts/<video_slug>.json"
   ```
3. Read each transcript and summarize the key arguments

**Short-form** — focused depth:
1. Run 1–2 targeted web searches for the specific point
2. Find 1–2 relevant YouTube videos if useful (not required)
3. Focus on one key insight, stat, or argument — not a broad survey

**Mode-specific actions**:
- **Topic Deep-Dive**: Identify consensus vs contrarian takes, key data points
- **News Reaction**: Find historical precedents, build comparison table
- **Strategy Comparison**: Gather existing analyses; if user requests, scaffold a Python
  backtest in `workspace/temp/research/<slug>/backtests/`
- **AI Scenario Analysis**: Structure as Assumptions → First-order → Second-order → Implications

### Write the Research Brief

Write findings to `workspace/temp/research/<slug>/brief.md` following the format
in `directives/research/topic.md`.

### Verify Sources

Before presenting the brief to the user, verify that every cited source actually
supports the claim attributed to it. This catches misattribution, hallucinated
content, and summarization errors.

**Parallelism**: All source verifications are independent — fire off all `WebFetch`
re-checks in parallel (one per citation) rather than sequentially. This also applies
to the initial research round: run multiple `WebSearch` queries and `fetch_transcript.py`
calls in parallel when they don't depend on each other.

For each `[Source Name](URL)` citation in the brief:

1. **Re-fetch the URL** using `WebFetch` and ask: "Does this page contain information
   about [the specific claim]?"
2. **Evaluate the result** — one of three outcomes:
   - **Confirmed**: the source supports the claim. Add a short direct quote from the
     source next to the citation (per the directive's verification rules).
   - **Misattributed**: the source exists but doesn't say what was claimed. Either find
     the correct source URL for this claim, or remove the citation and note the claim
     as unsourced.
   - **Unreachable**: the URL can't be fetched (paywall, geo-block, 404). Keep the
     citation but mark it as `(unverified)` with a note on why.
3. **Update `brief.md`** with any corrections, quotes, or `(unverified)` markers.

Only after verification is complete, present the brief to the user in the chat
(summarize — don't dump the whole file).

### Iterative Loop

**STOP and wait for the user.** The user may:

| User says | Action |
|---|---|
| Adds points or context | Integrate into `brief.md`, do additional research if needed |
| Challenges a finding | Re-evaluate: search for counter-evidence, update the brief |
| "Look deeper into X" | Do focused research on subtopic X, verify new sources, update brief |
| "Find more sources on Y" | Search specifically for Y, verify new sources, add to brief |
| "Run a backtest on Z" | Scaffold Python script, run it, add results to brief |
| "Move to outline" / "Research done" | Update `state.json` phase → `"outline"`, proceed to Phase 2 |

When new sources are added during iteration, run the same verification step on those
new citations before updating `brief.md`.

After each update, re-read the current `brief.md` to ensure edits are consistent
with the rest of the document.

**Do NOT suggest moving to the next phase.** Wait for the user to explicitly say so.

---

## Phase 2 — Outline (Iterative)

### Initial Outline

If a `brief.md` exists, read `workspace/temp/research/<slug>/brief.md` to refresh context.
(For short-form projects that skipped research, work from the user's stated topic/angle.)

**Long-form outline** — propose a multi-section structure. Consider:
- What's the strongest hook? (Most surprising finding, most relatable problem)
- What's the logical flow? (Problem → context → analysis → conclusion)
- What sections need visuals, screen recordings, or data overlays?
- Target video length (estimate based on content density)

**Short-form outline** — propose a 3-beat structure (Hook → Core Point → Payoff).
Consider:
- What's the scroll-stopping hook? (First 3 seconds decide everything)
- What's the single point? (One insight only — no tangents)
- What's the payoff? (Takeaway, punchline, or CTA)

Write to `workspace/temp/research/<slug>/outline.md` following the format-appropriate
template in `directives/research/topic.md`.

Present the outline to the user.

### Iterative Loop

**STOP and wait for the user.** The user may:

| User says | Action |
|---|---|
| Reorders sections | Update `outline.md` with new order |
| Adds/removes points | Update `outline.md` |
| Changes the angle | Restructure outline, possibly reference different parts of the brief |
| "Start writing" / "Outline done" | Update `state.json` phase → `"script"`, proceed to Phase 3 |

**Do NOT suggest moving to the next phase.** Wait for the user to explicitly say so.

---

## Phase 3 — Script Writing (Iterative)

### Tone Profile Check

Before writing, check if a tone profile exists:

1. Check if `memory/tone-profile.md` exists (in the auto-memory directory)
2. If it exists: load it and use as the voice guide
3. If it doesn't exist: ask the user for their YouTube channel link, then:
   - Fetch transcripts from 3–5 recent videos using `fetch_transcript.py`
   - Analyze speaking style (vocabulary, sentence structure, formality, humor,
     how technical concepts are explained, catchphrases)
   - Write profile to `memory/tone-profile.md`
   - Confirm with user before using

Check if the user wants a tone override for this project. If so, record it in
`state.json` under `tone_override`.

### Initial Script Draft

Read:
- `workspace/temp/research/<slug>/brief.md` (for content/facts — if it exists)
- `workspace/temp/research/<slug>/outline.md` (for structure)
- Tone profile (for voice)

**Long-form**: Write the full script section by section to
`workspace/output/research/<slug>/script.md`. Target ~1500–2500 words.
Present section by section — long scripts are easier to review in chunks.

**Short-form**: Write a single flowing script to
`workspace/output/research/<slug>/script.md`. Target ~150–250 words.
Present the full script at once — it's short enough to review whole.
Read it back mentally and cut anything that doesn't earn its place.

### Iterative Loop

**STOP and wait for the user.** The user may:

| User says | Action |
|---|---|
| Rewrites a section | Update that section in `script.md` |
| "Make this part more casual" | Rewrite with adjusted tone |
| "Add X here" | Insert new content, referencing brief for accuracy |
| "Cut this section" | Remove from `script.md` |
| "Script done" | Update `state.json` phase → `"complete"`, finalize |

**Do NOT suggest moving to completion.** Wait for the user to explicitly say so.

---

## Finalization

When the user says "script done":

1. Update `state.json`: set `phase` to `"complete"`
2. Report to the user:
   ```
   Research project complete!

   Final script:  workspace/output/research/<slug>/script.md
   Research brief: workspace/temp/research/<slug>/brief.md
   Outline:        workspace/temp/research/<slug>/outline.md

   Temp files in workspace/temp/research/<slug>/ can be safely deleted
   once you no longer need the research materials.
   ```

---

## Spin-Off Reels

This flow is triggered when the user chooses "spin-off reels from an existing project"
in Step 1. It reuses a long-form project's research and produces short-form reel scripts.

### Step A — Select Parent Project

List completed or in-progress long-form projects:

```bash
ls workspace/temp/research/ 2>/dev/null
```

Read each project's `state.json`. Only show projects where `format` is `"long-form"`.
Ask the user which project to spin off from.

### Step B — Create Spin-Off Project

Create a new project directory with a slug like `<parent-slug>-reels`:

```bash
mkdir -p "workspace/temp/research/<parent-slug>-reels"
mkdir -p "workspace/output/research/<parent-slug>-reels"
```

Write `state.json`:
```json
{
  "topic": "Reels from: <parent topic>",
  "slug": "<parent-slug>-reels",
  "format": "short-form",
  "mode": "<inherited from parent>",
  "phase": "outline",
  "tone_override": null,
  "parent_project": "<parent-slug>",
  "created": "<YYYY-MM-DD>",
  "updated": "<YYYY-MM-DD>"
}
```

### Step C — Read Parent Research

Read the parent project's `workspace/temp/research/<parent-slug>/brief.md`.

Suggest 2–4 potential reel angles extracted from the research. Each angle should be
a single, self-contained insight that works as a standalone short-form video.

Present the suggestions and ask the user which angles to develop (they can pick
multiple or suggest their own).

### Step D — Outline and Script Each Reel (Iterative)

For each selected angle, go through the short-form outline → script flow:

1. Write outline to `workspace/temp/research/<parent-slug>-reels/reel-<N>-outline.md`
2. Present to user → iterate until approved
3. Write script to `workspace/output/research/<parent-slug>-reels/reel-<N>.md`
4. Present to user → iterate until approved
5. Move to next reel

The user can also request additional reels at any point during this process.

When all reels are done, the user says "reels done" → update `state.json` phase
to `"complete"` and report the list of reel scripts produced.

---

## Error Handling

- If `fetch_transcript.py` fails on a YouTube URL: report the error, skip that video,
  continue with other sources. Common issues:
  - Video has no captions → note this, use other sources
  - `yt-dlp` not installed → tell user: `pip install yt-dlp`
  - Video is private/age-restricted → skip, note to user
- If web search returns no useful results: tell user, suggest alternative search terms
- If a backtest script fails: show error, let user decide whether to debug or skip
- If tone profile analysis fails: fall back to "casual + educational" default, note to user
