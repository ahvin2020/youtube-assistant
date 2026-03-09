# Orchestrator: Idea Discovery Pipeline

Follow every step in order. Do not skip steps.

---

## Pre-Flight Checklist

- [ ] Load channel profile from `memory/channel-profile.md`
  - If missing: ask user for YouTube channel URL, build profile first
  - Extract `channel_id` for own-channel analysis
  - Extract Discovery Keywords, Niche Categories, Community Sources, Region sections
  - If any of those sections are missing: ask user for niche keywords, subreddits, etc. and add them to channel-profile.md
- [ ] Parse `--format` flag from command arguments:
  - `longform` | `shorts` | `both` (default: `both`)
  - Also check for an optional `idea_hint` (narrows discovery to a specific area)
- [ ] Derive PROJECT name:
  - `YYYYMMDD_idea-discovery` (or `YYYYMMDD_<hint-slug>` if idea_hint given)
- [ ] Create workspace directories:
  ```
  mkdir -p workspace/temp/ideas/<PROJECT>
  mkdir -p workspace/output/ideas/<PROJECT>
  ```
- [ ] Write initial `state.json` to `workspace/temp/ideas/<PROJECT>/`:
  ```json
  {"phase": "gathering", "format": "<format_flag>", "project": "<PROJECT>", "content_slug": "<hint-slug or 'broad-discovery'>"}
  ```

---

## Step 1 — Data Gathering (Parallel)

Record start time using Bash:
```bash
date +%s
```
Store the output as `PIPELINE_START` (epoch seconds). This will be used in Step 4 to calculate total elapsed time.

Launch **all 4 data sources in parallel** (independent — no dependencies).

**IMPORTANT — Parallel execution**: Launch all 4 in a **single message** using
Bash tool with `run_in_background: true` for each executor.

All 4 tool calls must be in the **same message** so they run concurrently.
Then collect results from all background tasks before proceeding.

### 1a. YouTube Topics (executor — background)

```bash
python3 executors/ideas/youtube_ideas.py \
  --channel-profile memory/channel-profile.md \
  --channel-id <channel_id> \
  --format <format_flag> \
  --max-channels 15 --max-keywords 10 --days 90 \
  [--topic-hint "<idea_hint>"] \
  --output workspace/temp/ideas/<PROJECT>/youtube_data.json
```

Only include `--topic-hint` if a hint was provided. When present, the executor
runs an additional `ytsearch20:<hint>` to find videos specifically about that topic.

### 1b. Google Trends (executor — background)

```bash
/opt/homebrew/bin/python3 executors/ideas/google_trends_ideas.py \
  --channel-profile memory/channel-profile.md \
  --region SG --max-keywords 15 \
  --output workspace/temp/ideas/<PROJECT>/trends_data.json
```

Note: Must use `/opt/homebrew/bin/python3` (pytrends requires Python 3.10+).

### 1c. Reddit (executor — background)

```bash
python3 executors/ideas/reddit_ideas.py \
  --channel-profile memory/channel-profile.md \
  --timeframe month --max-posts 25 --max-subs 8 \
  --output workspace/temp/ideas/<PROJECT>/reddit_data.json
```

### 1d. Twitter (executor — background)

```bash
/opt/homebrew/bin/python3 executors/ideas/twitter_ideas.py \
  --channel-profile memory/channel-profile.md \
  --max-tweets 20 --max-terms 10 \
  --output workspace/temp/ideas/<PROJECT>/twitter_data.json
```

Note: Must use `/opt/homebrew/bin/python3` (curl_cffi installed there).
Uses Cookie Editor browser export for auth — no browser automation.
Cookies read from `~/.cache/youtube-assistant/twitter_cookies.json`.
If cookies are missing or stale, the executor prints setup instructions to stderr.

**Error handling**: If any source fails (except YouTube), log the error and
continue. YouTube is the only required source.

After all sources complete, report:
```
DATA GATHERING COMPLETE:
  YouTube: X competitor videos from Y channels + Z search suggestions
  Trends: X keywords analyzed, Y rising queries found
  Reddit: X posts from Y subreddits
  Twitter: X tweets from Y search terms
  Time: Xm Ys
```

---

## Step 2 — Topic Intelligence (Two-Pass)

This step uses two passes to minimize Opus token usage.

### Pre-trim raw data

Before passing data to subagents, trim and convert to **TSV** to minimize token
cost (~50% fewer tokens than nested JSON for tabular data).

For each source, load the JSON, sort/filter, then convert to a TSV string
(tab-separated, header row first). Pass the TSV strings directly in the
subagent prompt — do NOT write intermediate TSV files.

```python
import json, csv, io

def json_to_tsv(records: list[dict], columns: list[str]) -> str:
    """Convert a list of dicts to a TSV string with header."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter='\t', lineterminator='\n')
    writer.writerow(columns)
    for r in records:
        writer.writerow([r.get(c, '') for c in columns])
    return buf.getvalue()
```

- **YouTube** — top 50 by `outlier_score`:
  columns: `title`, `channel`, `views`, `outlier_score`, `upload_date`, `video_id`, `duration`
- **Reddit** — top 50 by `score`:
  columns: `title`, `subreddit`, `score`, `selftext_preview`
- **Twitter** — top 30 by `likes`:
  columns: `text`, `author_handle`, `likes`, `retweets`, `search_term`
- **Trends** — pass as-is (already compact, not tabular).

### Pass 1 — Cluster & Score (Sonnet subagent)

Spawn a subagent (**no model override** — inherits Sonnet).

Pass the subagent the trimmed data files, channel profile, format flag,
topic hint (if any), and scoring framework from `directives/ideas/discover.md`.

> You are a content strategy analyst. Analyze raw data from 4 sources
> and produce a scored topic list.
>
> **Step 2a — Extract topic signals**: From each source, identify distinct
> topic themes. A "topic" is an addressable content idea, not a specific
> video. Multiple videos about the same theme = one topic.
>
> **Step 2b — Cluster similar ideas**: Group by user intent. Merge ideas
> sharing 2+ keywords and the same intent. Use the most engaging name.
>
> **Step 2c — Score each topic**: Apply the scoring rubric from the
> directive. Calculate both LF score and Shorts score regardless of format
> flag (but rank by the relevant score based on format).
>
> **Step 2d — Lightweight fields only**: For each topic (up to 50):
> - `topic`: cluster label
> - `lf_score`: 0-10
> - `shorts_score`: 0-10
> - `format_rec`: Long / Short / Both
> - `trend`: Rising / Stable / Viral / Declining
> - `sources`: which data sources support this topic (e.g. "YT, Trends, Reddit")
> - `evidence`: 1-line summary of strongest signal (e.g. "3 competitors with 5x+ outlier")
> - `gap_status`: Uncovered / Partially covered / Covered
> - `hint_related`: true / false (only when topic_hint is provided)
>
> **Step 2e — Classify hint relevance** (only when topic_hint is provided):
> For each topic, set `hint_related: true` if the topic is **directly about**
> the hint subject or a natural sub-angle of it (e.g., hint "graduate
> employment" → "degree ROI", "fresh grad investing", "salary by age" are
> related; "war investing", "market crash", "cost of living" are NOT).
> A topic must share the same **core subject matter** as the hint — not just
> tangentially appeal to a similar audience.
>
> **Step 2f — Filter & Rank**:
> When `topic_hint` is provided, **drop all topics where `hint_related=false`**.
> Only keep hint-related topics — do not include general/unrelated opportunities.
> Sort remaining by source strength then format-relevant score.
>
> When no topic_hint is provided, skip Step 2e and rank all topics together
> by source strength then format-relevant score (no filtering).
>
> **Output**: Write `ideas_scored.json` to the temp directory.

After this subagent completes, verify `ideas_scored.json` exists and is valid JSON.

### Pass 2 — Enrich Top Topics (Parallel Sonnet subagents)

Read `ideas_scored.json`, take the **top 40 ideas** by rank (when a hint was
provided, this may be fewer than 40 since non-relevant topics were dropped in
Step 2f). Split evenly into **4 batches** and spawn **4 subagents in parallel**
(all in a single message, **no model override** — inherits Sonnet).

Convert each batch to **TSV** before passing (same `json_to_tsv` helper):
columns: `topic`, `lf_score`, `shorts_score`, `format_rec`, `trend`, `sources`,
`evidence`, `gap_status` (+ `hint_related` if topic_hint was provided).

Pass each subagent:
1. Its batch of 10 ideas as TSV (with scores and evidence)
2. Channel profile summary (tone, pillars, audience, hook formulas)
3. Format flag

> You are a content strategy analyst. Enrich these pre-scored ideas with
> deep analysis. For each idea in your batch:
>
> - `why_it_works`: 2-3 sentences citing specific evidence
> - `suggested_angle`: tailored to this channel's audience and tone
> - `hook_ideas`: 2-3 title/hook ideas (newline-separated)
>   - If format=longform or both: include long-form titles
>   - If format=shorts or both: include shorts hooks
> - `research_more`: channels, subreddits, search terms to explore further
>
> Keep all existing fields (`topic`, `lf_score`, `shorts_score`, `format_rec`,
> `trend`, `sources`, `evidence`, `gap_status`) unchanged.
>
> **Output**: Write `ideas_batch_N.json` (where N = 1-4) to the temp directory
> with your 10 enriched ideas as a JSON array.

After all 4 subagents complete, merge the 4 batch files into a single
`ideas_analysis.json` in rank order:

```python
import json
batches = []
for i in range(1, 5):
    with open(f'{PROJECT}/ideas_batch_{i}.json') as f:
        batches.extend(json.load(f))
with open(f'{PROJECT}/ideas_analysis.json', 'w') as f:
    json.dump(batches, f, indent=2)
```

Verify `ideas_analysis.json` exists and contains valid JSON with all expected
fields and all 40 ideas.

---

## Step 3 — Export to Google Sheet

Tab naming convention:
- Broad discovery (no hint): `idea_broad`
- Hint-focused: `idea_<hint-slug>` (e.g. `idea_etfs-to-invest-in`)

The hint slug is derived from the idea_hint: lowercase, spaces to hyphens, max 30 chars.

```bash
# With idea_hint:
python3 executors/ideas/export_ideas_sheet.py \
  --input workspace/temp/ideas/<PROJECT>/ideas_analysis.json \
  --credentials credentials.json \
  --sheet-config workspace/config/intelligence_sheet.json \
  --tab-name "idea_<hint-slug>"

# Without idea_hint (broad discovery):
python3 executors/ideas/export_ideas_sheet.py \
  --input workspace/temp/ideas/<PROJECT>/ideas_analysis.json \
  --credentials credentials.json \
  --sheet-config workspace/config/intelligence_sheet.json \
  --tab-name "idea_broad"
```

**Never overwrite another run's tab.** Each run gets its own uniquely named tab.

On success: capture the sheet URL.
On failure: show error, offer to save `ideas_analysis.json` as the final output.

---

## Step 4 — Summary Report

Calculate elapsed time:
```bash
echo $(( $(date +%s) - PIPELINE_START ))
```
Convert to `Xm Ys` format (e.g. `3m 02s`).

Present the results:

```
TOPIC DISCOVERY COMPLETE
========================
Format: <longform|shorts|both>
Sources: YouTube (X channels) + Trends (Y keywords) + Reddit (Z subs) + Twitter (W terms)
Topics found: X raw → Y clustered → Z scored
Discovery time: Xm Ys
Sheet: <Google Sheet URL>

TOP 5 AT A GLANCE:
1. [Topic] — LF: X/10, Shorts: Y/10 — [Trend] — [1-line why]
2. ...
3. ...
4. ...
5. ...

OPTIONS:
  "Write #3" — Start /write pipeline for that topic
  "More ideas like #2" — Search for adjacent topics
  "Refresh" — Re-run with new random samples
  "Done" — Finalize
```

**STOP and wait for user input.**

---

## Step 5 — Interactive Refinement (Optional)

| User says | Action |
|-----------|--------|
| "Write #N" | Hand off topic #N to the `/write` pipeline. Extract `topic`, `suggested_angle`, and `hook_ideas` from `ideas_analysis.json` for that entry. Save to `workspace/temp/ideas/<PROJECT>/idea_handoff_<N>.json`. Then start `/write` with `--idea-context <path>` so the topic and angle are pre-populated — the user doesn't have to re-explain. `/write` runs its own research as normal from there. |
| "More ideas like #N" | Generate adjacent ideas based on that topic's keywords. Run quick YouTube search for those keywords. Score and present as a mini-list. Export to a **separate tab** named `Adjacent: <Topic>` (use `--tab-name` flag). Never overwrite the main ideas tab. |
| "Refresh" | Re-run Step 1-4 (new random samples from keywords/channels). |
| "Done" | Copy `ideas_analysis.json` to `workspace/output/ideas/<PROJECT>/`. Update `state.json` phase to "complete". Report final output path. |

After "More ideas like #N" or "Refresh", return to Step 4 (summary) and wait again.

---

## Error Handling

| Error | Action |
|-------|--------|
| `youtube_ideas.py` fails | **Critical** — cannot proceed. Show stderr. Check yt-dlp installation. |
| `google_trends_ideas.py` fails | Non-fatal — note "Trends data unavailable" in report. Proceed with available data. Scoring: Trends-dependent components get neutral score (5). |
| `reddit_ideas.py` fails | Non-fatal — note "Reddit data unavailable" in report. Proceed with available data. Scoring: Reddit-dependent components get neutral score (5). |
| `twitter_ideas.py` fails | Non-fatal — note "Twitter data unavailable" in report. Proceed with available data. Scoring: Twitter-dependent components get neutral score (5). |
| Sheets export fails | Show error. Offer to save analysis.json locally as fallback. |
| Channel profile missing discovery sections | Ask user for niche keywords, subreddits, adjacent niches. Add sections to `memory/channel-profile.md`. |
| No channel profile | Build first (standard channel profile flow). |
| Opus subagent fails | Retry once. If still fails, fall back to Sonnet for topic intelligence (lower quality but functional). |

---

## State Tracking

Update `workspace/temp/ideas/<PROJECT>/state.json` after each phase:

```json
{
  "phase": "gathering | analyzing | exporting | complete",
  "format": "longform | shorts | both",
  "project": "<PROJECT>",
  "sources_succeeded": ["youtube", "trends", "reddit", "twitter"],
  "sources_failed": [],
  "ideas_count": 40,
  "sheet_url": "https://docs.google.com/...",
  "iterations": 1
}
```
