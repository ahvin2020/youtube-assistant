# Orchestrator: Research-Only Pipeline

This orchestrator coordinates a research-only workflow. It gathers sources, writes a
research brief, and stops. Use `/write` later to turn the brief into a script.

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
  1. 20260228_dca-vs-lump-sum (Phase: research-complete ✓, Last updated: 2026-02-28)
  2. 20260301_fed-rate-cut-impact (Phase: research, Last updated: 2026-03-01)
  3. 20260304_cpf-frs-vs-ers (Phase: outline — use /write to continue, Last updated: 2026-03-04)

Resume one of these, or start a new project?
```

**Phase display rules**:
- `research` → show as "research" (in-progress research)
- `research-complete` → show as "research-complete ✓" (brief is done)
- Any other phase (`outline`, `script`, `complete`) → show phase with note "use /write to continue"

If the user chooses to resume:
- If phase is `research`: read existing `brief.md` (if any) and re-enter the Phase 1 iterative loop
- If phase is `research-complete`: tell user the brief is already done, offer to reopen for further research or just show the brief location
- If phase is `outline`/`script`/`complete`: tell user to use `/write` to continue this project

If no projects exist or the user wants a new one: proceed to Step 1.

---

## Step 1 — Gather Topic and Context

Ask the user:
1. **What topic do you want to research?**
2. **Any specific angle, context, or constraints?** (e.g., "focused on Singapore investors",
   "I want to argue against this", "news just broke today")

From the user's answer, determine:
- **Research mode**: Topic Deep-Dive, News Reaction, Strategy Comparison, or AI Scenario Analysis
  (see `directives/research/topic.md` for definitions)
- **Slug**: a URL-safe lowercase version of the topic (e.g., "DCA vs Lump Sum" → `dca-vs-lump-sum`)
- **PROJECT**: `YYYYMMDD_<slug>` using today's date (e.g., `20260305_dca-vs-lump-sum`)

Create the project directory and state file:

```bash
mkdir -p "workspace/temp/research/<PROJECT>/transcripts"
```

Write `workspace/temp/research/<PROJECT>/state.json`:
```json
{
  "topic": "<user's topic>",
  "slug": "<slug>",
  "format": null,
  "mode": "<research_mode>",
  "phase": "research",
  "tone_override": null,
  "parent_project": null,
  "brand_brief": null,
  "created": "<YYYY-MM-DD>",
  "updated": "<YYYY-MM-DD>"
}
```

Note: `format` is `null` — it will be set later when the user runs `/write`.

Tell the user which mode was detected and confirm before proceeding.

---

## Phase 1 — Research (Iterative)

### Initial Research Round

Based on the detected mode, perform the actions specified in `directives/research/topic.md`.
Always use **full depth** (long-form level) regardless of eventual video format — you're
explicitly choosing to research, so you want thorough coverage:

1. Run web searches relevant to the topic (use WebSearch tool)
2. Find 3–5 relevant YouTube videos — fetch their transcripts:
   ```bash
   python3 executors/research/fetch_transcript.py "<youtube_url>" "workspace/temp/research/<PROJECT>/transcripts/<video_slug>.json"
   ```
3. Read each transcript and summarize the key arguments

**IMPORTANT — Parallelism**: All `fetch_transcript.py` calls (step 2) and
`WebSearch` queries (step 1) are independent. Launch them all in a **single
message** so they run concurrently. Do NOT fetch transcripts one at a time.

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

Before presenting the brief to the user, verify that every cited source actually
supports the claim attributed to it. This catches misattribution, hallucinated
content, and summarization errors.

**IMPORTANT — Parallel execution**: All source verifications are independent —
fire off **all** `WebFetch` re-checks in a **single message** so they run
concurrently. Do NOT verify sources one by one sequentially.

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
| "Research done" | Proceed to Finalization |

When new sources are added during iteration, run the same verification step on those
new citations before updating `brief.md`.

After each update, re-read the current `brief.md` to ensure edits are consistent
with the rest of the document.

**Do NOT suggest finishing.** Wait for the user to explicitly say "research done".

---

## Finalization

When the user says "research done":

1. Update `state.json`: set `phase` to `"research-complete"`, update `updated` date
2. Report to the user:

```
Research complete!

Brief: workspace/temp/research/<PROJECT>/brief.md
Mode:  <research_mode>
Topic: <topic>

To write a script from this research, run /write and resume this project.
```

---

## Error Handling

- If `fetch_transcript.py` fails on a YouTube URL: report the error, skip that video,
  continue with other sources. Common issues:
  - Video has no captions → note this, use other sources
  - `yt-dlp` not installed → tell user: `pip install yt-dlp`
  - Video is private/age-restricted → skip, note to user
- If web search returns no useful results: tell user, suggest alternative search terms
- If a backtest script fails: show error, let user decide whether to debug or skip
