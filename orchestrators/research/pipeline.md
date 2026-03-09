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

If directories exist (format: `YYYYMMDD_<slug>`), read each project's `state.json` and present a list:

```
Existing research projects:
  1. 20260228_dca-vs-lump-sum (Format: long-form, Phase: outline, Last updated: 2026-02-28)
  2. 20260301_fed-rate-cut-impact (Format: long-form, Phase: research, Last updated: 2026-03-01)
  3. 20260304_moomoo (Format: brand-mention, Phase: script, Last updated: 2026-03-04)

Resume one of these, or start a new project?
```

If the user chooses to resume:

- **If phase is `research`** and a `brief.md` exists: ask if they want to continue research
  or move to outline. If continuing research, re-enter Phase 1 iterative loop. If moving
  to outline, update `state.json` phase to `"outline"`, and jump to Phase 2.
- **If phase is `research`** and no `brief.md` exists: re-enter Phase 1 from the start.
- **All other phases**: read the project's `state.json`, then skip to the current phase's
  iterative loop (pick up where they left off by reading the existing `brief.md`,
  `outline.md`, or `script.md`). For brand-mention projects, also reload `brand_brief`
  from `state.json` to restore requirements context.

If no projects exist or the user wants a new one: proceed to Step 1.

---

## Step 1 — Gather Topic, Format, and Context

Ask the user:
1. **What topic do you want to write about?**
2. **What format?** Long-form video, short-form reel, or brand-mention (sponsored segment)?
3. **Any specific angle, context, or constraints?** (e.g., "focused on Singapore investors",
   "I want to argue against this", "news just broke today")

If the user chose **brand-mention**: jump to the [Brand-Mention Requirements Gathering](#brand-mention-requirements-gathering) section below.

From the user's answer (or from `--idea-context` if handed off from `/idea`), determine:
- **Format**: `long-form` or `short-form`
- **Research mode**: Topic Deep-Dive, News Reaction, Strategy Comparison, or AI Scenario Analysis
  (see `directives/research/topic.md` for definitions)
- **Slug**: a URL-safe lowercase version of the topic (e.g., "DCA vs Lump Sum" → `dca-vs-lump-sum`)
- **PROJECT**: `YYYYMMDD_<slug>` using today's date (e.g., `20260303_dca-vs-lump-sum`)
- **Idea context**: if `--idea-context <path>` was provided, read the JSON file. It contains
  `topic`, `suggested_angle`, and `hook_ideas` from the `/idea` pipeline. Skip asking the
  user for topic/angle — use these directly. Store the path in `state.json` under `idea_context`.

**For short-form only**: ask whether the user wants a research phase or wants to skip
straight to outlining. The user can:
- Provide an **existing script or topic** from a previous `/write` project to adapt
- Provide any **source text** (article, notes, talking points) to turn into a short-form script
- Start fresh with just a topic (with or without research)

If the user provides existing material, save it to
`workspace/temp/research/<PROJECT>/source_material.md` and skip research (set phase to `"outline"`).

Create the project directory and state file:

```bash
mkdir -p "workspace/temp/research/<PROJECT>/transcripts"
mkdir -p "workspace/output/research/<PROJECT>"
```

Write `workspace/temp/research/<PROJECT>/state.json`:
```json
{
  "topic": "<user's topic>",
  "slug": "<slug>",
  "content_slug": "<slug>",
  "format": "<long-form | short-form | brand-mention>",
  "mode": "<research_mode | null for brand-mention>",
  "phase": "research",
  "tone_override": null,
  "source_material": "<filename if user provided existing material, else null>",
  "idea_context": "<path to idea_handoff JSON from /idea, or null>",
  "brand_brief": null,
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
   python3 executors/research/fetch_transcript.py "<youtube_url>" "workspace/temp/research/<PROJECT>/transcripts/<video_slug>.json"
   ```
3. Read each transcript and summarize the key arguments

**IMPORTANT — Parallelism**: All `fetch_transcript.py` calls (step 2) and
`WebSearch` queries (step 1) are independent. Launch them all in a **single
message** so they run concurrently. Do NOT fetch transcripts one at a time.

**Short-form** — focused depth:
1. Run 1–2 targeted web searches for the specific point
2. Find 1–2 relevant YouTube videos if useful (not required)
3. Focus on one key insight, stat, or argument — not a broad survey

**Mode-specific actions**:
- **Topic Deep-Dive**: Identify consensus vs contrarian takes, key data points
- **News Reaction**: Find historical precedents, build comparison table
- **Strategy Comparison**: Gather existing analyses; if user requests, scaffold a Python
  backtest in `workspace/temp/research/<PROJECT>/backtests/`
- **AI Scenario Analysis**: Structure as Assumptions → First-order → Second-order → Implications

### Write the Research Brief

Write findings to `workspace/temp/research/<PROJECT>/brief.md` following the format
in `directives/research/topic.md`.

### Verify Sources

Before presenting the brief to the user, verify that cited web sources actually
support the claims attributed to them. This catches misattribution, hallucinated
content, and summarization errors.

**Skip YouTube transcript sources**: Citations from YouTube videos whose transcripts
were fetched via `fetch_transcript.py` do NOT need re-verification — the transcript
was already read directly. Only verify non-YouTube web sources (articles, reports,
blog posts, etc.).

**IMPORTANT — Parallel execution**: All source verifications are independent —
fire off **all** `WebFetch` re-checks in a **single message** so they run
concurrently. Do NOT verify sources one by one sequentially.

For each non-YouTube `[Source Name](URL)` citation in the brief:

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

If a `brief.md` exists, read `workspace/temp/research/<PROJECT>/brief.md` to refresh context.
If a `source_material.md` exists (short-form with existing material), read it as the content source.
(For short-form projects that skipped research with no source material, work from the user's stated topic/angle.)

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

**Brand-mention outline** — read `brand_brief` from `state.json`. Use the
placement-appropriate template from `directives/research/topic.md`:
- **Mid-roll**: Include Transition In / Transition Out sections. If the main video topic
  is not already known, ask the user: "What's the main video about? I need it to write
  natural transitions."
- **Standalone**: Include a Hook section instead of transitions.
- Pick 2–3 key features max from the brief (not all of them — keep it tight)
- The "Personal Touch" section is critical — if the user provided personal experience in
  the brand brief, use it. If not, flag: "Do you have any personal experience with
  <product>? This makes the difference between sounding genuine vs reading an ad."

Write to `workspace/temp/research/<PROJECT>/outline.md` following the format-appropriate
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

Follow `directives/shared/channel-profile.md` to check/build the channel profile.
Load the **Tone Profile** section and use as the voice guide.

Check if the user wants a tone override for this project. If so, record it in
`state.json` under `tone_override`.

### Hook Loading (Optional — Before Script Draft)

If `workspace/config/hooks.json` exists:
1. Read `hooks.json`
2. Spawn a **Haiku subagent** (`model: "haiku"`) to filter hooks relevant to the current topic:
   - Input: all hooks from hooks.json + current topic from `state.json` + outline from `outline.md`
   - Task: select the 15 hooks most relevant to this script's topic and format
   - Output: a filtered list of 15 hooks (text, category, format, performance_score)
3. Store the filtered hooks for use in the script-writing and title-generation steps below

If `hooks.json` doesn't exist: skip this step (no hook reference available — run `/analyze` first).

### Initial Script Draft

Read:
- `workspace/temp/research/<PROJECT>/brief.md` (for content/facts — if it exists)
- `workspace/temp/research/<PROJECT>/outline.md` (for structure)
- Tone profile (for voice)
- Filtered hooks (if loaded above — as reference for the opening hook)

**Delegate to Opus subagent**: Spawn an Agent with `model: "opus"` to write the
script draft — creative writing benefits from Opus-level quality. Pass it all three
inputs (brief content, outline content, tone profile) in the prompt, along with the
format (long-form or short-form), the output format rules from
`directives/research/topic.md`, and any tone override from `state.json`. The subagent
should return the full script text; write it to
`workspace/output/research/<PROJECT>/script.md`.

**Hard formatting rule — include in subagent prompt**: Do NOT use em dashes (—) anywhere
in the script. Scripts are spoken aloud, not read. Use periods, commas, or line breaks
instead. This is a non-negotiable constraint.

If filtered hooks are available, also pass them to the subagent with this instruction:
> **Hook reference**: Here are proven hooks from top-performing videos in this niche,
> filtered to hooks relevant to the current topic. Use these as inspiration for
> the video's opening hook — learn from the patterns, but do not copy verbatim.

**Long-form**: Instruct the subagent to write the full script section by section.
Target ~1500–2500 words. Present section by section — long scripts are easier to
review in chunks.

**Short-form**: Instruct the subagent to write a single flowing script.
Target ~150–250 words. Present the full script at once — it's short enough to review
whole. Tell it to cut anything that doesn't earn its place.

**Brand-mention**: Instruct the subagent to write a sponsored segment script. Pass it:
the `brand_brief` from `state.json`, the outline, the tone profile, and these instructions:
- Placement type determines structure (mid-roll has transitions, standalone has hook)
- Word count target from `brand_brief.word_count_target`
- Must include ALL mandatory phrases verbatim (do not paraphrase these)
- Must mention the product name, promo code, and link
- Must NOT violate any items in the `donts` list
- Tone must match the channel's existing sponsor integration style — conversational,
  genuine recommendation, not a hard sell
- If personal experience was provided, weave it in naturally
- The subagent should return the full script text WITH the requirements checklist
  (all items checked or unchecked based on whether the script covers them)

Write output to `workspace/output/research/<PROJECT>/script.md`.

### Source URL Verification (After Every Draft)

After writing the script (initial draft or any revision that adds/changes sources),
verify every `[Source: ...]()` URL in the script before presenting it to the user:

1. Extract all source URLs from the script
2. Fetch each URL to confirm it returns 200 (not 404, redirect to homepage, etc.)
3. For any broken URL, search the web for the correct link to the same data/report
4. Fix broken URLs in `script.md` before presenting the draft

**Why**: Subagents hallucinate URLs. The brief may contain correct URLs, but the
subagent may mangle them or invent new ones. Always verify after writing.

### Requirements Validation (Brand-Mention Only)

After the initial draft and after each subsequent revision, validate the script against
the `brand_brief` requirements:

1. **Mandatory phrases**: Search the script text for each phrase in `mandatory_phrases`.
   Each must appear verbatim (case-insensitive match is acceptable).
2. **Product name**: Must be mentioned at least once.
3. **Promo code / link**: Must appear in the script.
4. **Key features**: At least 2 of the listed features must be covered (semantic check —
   paraphrasing is fine).
5. **Don'ts check**: Scan the script for any violations of the `donts` list (semantic check).
6. **Word count**: Verify the script body (excluding checklist and metadata) is within
   the target range.

Update the Requirements Checklist in `script.md` — mark each item as `[x]` (met) or
`[ ]` (not met). If any items are not met, report them to the user:

```
Requirements check:
  [x] Product name mentioned: Moomoo
  [x] Promo code included: KELVIN88
  [ ] Mandatory phrase missing: "commission-free trades"
  [x] Key features covered: fractional shares, real-time data
  [x] No don'ts violations

1 item needs attention. Want me to revise, or will you handle it?
```

### Iterative Loop

**STOP and wait for the user.** The user may:

| User says | Action |
|---|---|
| Rewrites a section | Delegate rewrite to subagent with current script + instructions, update `script.md` |
| "Make this part more casual" | Delegate rewrite to subagent with tone adjustment, update `script.md` |
| "Add X here" | Delegate to subagent with brief context + insertion instructions, update `script.md` |
| "Cut this section" | Remove from `script.md` (no subagent needed — just edit) |
| "Add title and description" | Move to Phase 4 — Title & Description (not applicable for brand-mention) |
| "Check requirements" | Run requirements validation (brand-mention only), report results |
| "The brand sent updated requirements" | Re-gather brand brief, update `brand_brief` in `state.json`, re-validate script |
| "Script done" | Update `state.json` phase → `"complete"`, finalize |

**Delegation for rewrites**: For any action that involves writing or rewriting
script text, spawn a subagent with the current `script.md` content, the relevant
section of `brief.md` (if needed for accuracy), the tone profile, the formatting
rules from `directives/research/topic.md` (including the em dash ban), and specific
instructions for what to change. Apply the returned text to `script.md`.

**Do NOT suggest moving to the next phase.** Wait for the user to explicitly say so.

---

## Phase 4 — Title & Description

Triggered when the user says "add title and description" (or similar: "title and description",
"work on title").

Update `state.json`: set `phase` to `"title"`.

### Step 1 — Title Options

Read `workspace/output/research/<PROJECT>/script.md` and
`workspace/temp/research/<PROJECT>/outline.md`.

If filtered hooks were loaded in Phase 3 (from `hooks.json`), also reference the
title-format hooks as inspiration. Present them alongside the title options:
> **Proven title hooks in this niche**: These title patterns performed well on
> similar content. Use these structures (not exact text) as inspiration.

Draft **5 title variations** for the video. Mix styles:
- Curiosity gap (e.g., "Why X Is Changing Everything")
- Direct / factual (e.g., "X Explained in 10 Minutes")
- Number-driven (e.g., "3 Reasons X Matters for Your Portfolio")
- Question (e.g., "Is X the Biggest Risk to Your Money?")
- Bold claim (e.g., "X Will Define the Next Decade")

All titles must be **under 70 characters**. No clickbait that the script cannot back up.

Present the 5 options and ask the user to pick one, modify one, or provide their own.

### Step 2 — Video Description

Once the title is selected, draft the full video description block:

1. **Links placeholder** — blank lines the user fills in later
2. **Description body** — 2–4 sentence summary of the video, written in the channel's tone
3. **Timestamps** — derived from outline section headers, using `MM:SS` placeholder times
   (user fills in real times after editing the video)
4. **Disclaimer** — fixed text, never modify:
   ```
   None of this is meant to be construed as investment advice. It's for
   information purposes only. Links above include affiliate commission or
   referrals. I'm part of an affiliate network and I receive compensation
   from partnering websites.
   ```

Present the full description for the user to review.

### Step 3 — Append to Script

Once the user approves (or after iterating), append the title and description to the
bottom of `script.md` under a `---` separator. See the directive for the exact format.

### Iterative Loop

**STOP and wait for the user.** The user may:

| User says | Action |
|---|---|
| "Change the title to ..." | Update the selected title in `script.md` |
| "Rewrite the description" | Rewrite description body |
| "Update timestamps" | Adjust timestamp labels or order |
| "Script done" | Move to Finalization |

**Do NOT suggest moving to completion.** Wait for the user to explicitly say so.

---

## Finalization

When the user says "script done":

1. Update `state.json`: set `phase` to `"complete"`
1b. **Final Requirements Validation (Brand-Mention Only)**:
    Run the requirements validation one last time. If any items are unchecked,
    warn the user: "These requirements are not met: [list]. Finalize anyway?"
    Only proceed if the user explicitly confirms.
2. **Google Docs Export (Optional)**:
   Ask the user: "Would you like to export the script to a Google Doc?"

   **If yes**:
   - Determine the document title: use the project topic from `state.json`
     (e.g., `"Script: <topic>"`)
   - Run the executor:
     ```bash
     /opt/homebrew/bin/python3 executors/research/export_google_doc.py "workspace/output/research/<PROJECT>/script.md" --title "Script: <topic>"
     ```
   - Parse the JSON output
   - If successful: include the Google Doc URL in the completion summary (see below)
   - If it fails with a credentials error: tell the user how to set up credentials
     (copy `credentials.sample.json` to `credentials.json`, fill in from Google Cloud Console,
     enable Google Drive API), then proceed with normal completion
   - If it fails with any other error: show the error message and proceed with normal
     completion (the script file is still available locally)

   **If no**: proceed to step 3.

3. Report to the user:
   ```
   Research project complete!

   Final script:  workspace/output/research/<PROJECT>/script.md
   Google Doc:     <doc_url>        ← only if export was successful
   Research brief: workspace/temp/research/<PROJECT>/brief.md
   Outline:        workspace/temp/research/<PROJECT>/outline.md

   Temp files in workspace/temp/research/<PROJECT>/ can be safely deleted
   once you no longer need the research materials.
   ```

   For brand-mention projects, the report is:
   ```
   Brand mention script complete!

   Final script:  workspace/output/research/<PROJECT>/script.md
   Google Doc:    <doc_url>        ← only if export was successful
   Requirements:  All met ✓       ← or list any unmet items the user chose to skip
   Outline:       workspace/temp/research/<PROJECT>/outline.md

   Temp files in workspace/temp/research/<PROJECT>/ can be safely deleted.
   ```

---

## Brand-Mention Requirements Gathering

This flow is triggered when the user chooses "brand-mention" in Step 1. It replaces
the research phase with a structured brand requirements intake.

### Step A — Determine Placement and Product

Ask the user:
1. **Is this a mid-roll segment** (part of a longer video) **or a standalone sponsored short?**
2. **What product or brand is this for?**

Record the placement type: `mid-roll` or `standalone`.

### Step B — Gather Brand Brief

Ask the user for whatever information they have. Present this as a flexible intake —
some brands provide detailed briefs, others just give a product name:

```
I need whatever info you have from the brand. This could include any of:

1. **Product/service name** (required)
2. **What it does** — one-line description
3. **Key features to highlight** — which ones matter most?
4. **Promo code or link** — any specific code/URL to include?
5. **Mandatory phrases** — exact wording the brand requires?
6. **Dos and don'ts** — anything they specifically want included or avoided?
7. **Target audience angle** — how should this connect to your viewers?
8. **Your personal experience** — have you actually used it? Any genuine opinion?

Share whatever you have — even if it's just a product name, we can work with that.
```

**Do NOT require all fields.** The user may paste a full brief document, give bullet
points, or just say "it's for Moomoo, promo code KELVIN88". Adapt to whatever they provide.

### Step C — Parse and Confirm Requirements

From the user's input, build the `brand_brief` object. Parse whatever format they
provided (free text, bullet points, pasted brief document) into structured fields:

```json
{
  "placement": "<mid-roll | standalone>",
  "product_name": "<name>",
  "product_description": "<what it does — null if not provided>",
  "key_features": ["<feature 1>", "<feature 2>"],
  "promo_code": "<code or null>",
  "promo_link": "<URL or null>",
  "mandatory_phrases": ["<exact phrase 1>"],
  "dos": ["<do 1>"],
  "donts": ["<don't 1>"],
  "target_angle": "<how to connect to audience — null if not provided>",
  "personal_experience": "<creator's genuine opinion — null if not provided>",
  "word_count_target": "<100-200 for mid-roll, 150-250 for standalone>"
}
```

Present a summary back to the user:

```
Here's what I've captured for the <product_name> brand mention:

Placement:     <mid-roll / standalone>
Product:       <product_name> — <product_description>
Key features:  <feature 1>, <feature 2>, ...
Promo code:    <code>  |  Link: <link>
Must include:  <mandatory phrases>
Dos:           <list>
Don'ts:        <list>
Audience angle: <angle>
Your experience: <experience>

Anything to add or correct?
```

**STOP and wait for the user.** Let them correct, add, or confirm. Fields the user
did not provide are set to `null` (strings) or `[]` (arrays). Only `product_name`
and `placement` are truly required.

### Step D — Create Project and Set State

Once confirmed, create the project. Derive the slug from the product name
(e.g., "Moomoo" → `moomoo`):

```bash
mkdir -p "workspace/temp/research/<PROJECT>"
mkdir -p "workspace/output/research/<PROJECT>"
```

Write `workspace/temp/research/<PROJECT>/state.json` with `brand_brief` populated:

```json
{
  "topic": "Brand mention: <product_name>",
  "slug": "<product-slug>",
  "format": "brand-mention",
  "mode": null,
  "phase": "outline",
  "tone_override": null,
  "parent_project": null,
  "brand_brief": { ... },
  "created": "<YYYY-MM-DD>",
  "updated": "<YYYY-MM-DD>"
}
```

Note: `phase` starts at `"outline"` — research is skipped entirely.

Proceed to Phase 2 (Outline) with brand-mention branching.

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
