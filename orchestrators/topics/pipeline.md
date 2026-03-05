# Orchestrator: Topic Discovery Pipeline

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
  - Also check for an optional `topic_hint` (narrows discovery to a specific area)
- [ ] Derive PROJECT name:
  - `YYYYMMDD_topic-discovery` (or `YYYYMMDD_<hint-slug>` if topic_hint given)
- [ ] Create workspace directories:
  ```
  mkdir -p workspace/temp/topics/<PROJECT>
  mkdir -p workspace/output/topics/<PROJECT>
  ```
- [ ] Write initial `state.json` to `workspace/temp/topics/<PROJECT>/`:
  ```json
  {"phase": "gathering", "format": "<format_flag>", "project": "<PROJECT>"}
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
python3 executors/topics/youtube_topics.py \
  --channel-profile memory/channel-profile.md \
  --channel-id <channel_id> \
  --format <format_flag> \
  --max-channels 15 --max-keywords 10 --days 90 \
  [--topic-hint "<topic_hint>"] \
  --output workspace/temp/topics/<PROJECT>/youtube_data.json
```

Only include `--topic-hint` if a hint was provided. When present, the executor
runs an additional `ytsearch20:<hint>` to find videos specifically about that topic.

### 1b. Google Trends (executor — background)

```bash
/opt/homebrew/bin/python3 executors/topics/google_trends_topics.py \
  --channel-profile memory/channel-profile.md \
  --region SG \
  --output workspace/temp/topics/<PROJECT>/trends_data.json
```

Note: Must use `/opt/homebrew/bin/python3` (pytrends requires Python 3.10+).

### 1c. Reddit (executor — background)

```bash
python3 executors/topics/reddit_topics.py \
  --channel-profile memory/channel-profile.md \
  --timeframe month --max-posts 25 \
  --output workspace/temp/topics/<PROJECT>/reddit_data.json
```

### 1d. Twitter (executor — background)

```bash
/opt/homebrew/bin/python3 executors/topics/twitter_topics.py \
  --channel-profile memory/channel-profile.md \
  --max-tweets 20 --max-terms 10 \
  --output workspace/temp/topics/<PROJECT>/twitter_data.json
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

Before passing data to subagents, trim the raw files to reduce token cost:
- `youtube_data.json`: keep only top 50 videos by outlier score. For each
  video, keep only: `title`, `channel`, `views`, `outlier_score`, `upload_date`,
  `video_id`, `duration`.
- `reddit_data.json`: keep only top 50 posts by score. Drop `url` field.
  Keep `selftext_preview` (titles alone are often too vague for clustering).
- `twitter_data.json`: keep only top 30 tweets by likes. Keep only: `text`,
  `author_handle`, `likes`, `retweets`, `replies`, `days_old`, `search_term`.
- `trends_data.json`: pass as-is (already compact).

### Pass 1 — Cluster & Score (Sonnet subagent)

Spawn a subagent (**no model override** — inherits Sonnet).

Pass the subagent the trimmed data files, channel profile, format flag,
topic hint (if any), and scoring framework from `directives/topics/discover.md`.

> You are a content strategy analyst. Analyze raw data from 4 sources
> and produce a scored topic list.
>
> **Step 2a — Extract topic signals**: From each source, identify distinct
> topic themes. A "topic" is an addressable content idea, not a specific
> video. Multiple videos about the same theme = one topic.
>
> **Step 2b — Cluster similar topics**: Group by user intent. Merge topics
> sharing 2+ keywords and the same intent. Use the most engaging name.
>
> **Step 2c — Score each topic**: Apply the scoring rubric from the
> directive. Calculate both LF score and Shorts score regardless of format
> flag (but rank by the relevant score based on format).
>
> **Step 2d — Lightweight fields only**: For each topic (up to 30):
> - `topic`: cluster label
> - `lf_score`: 0-10
> - `shorts_score`: 0-10
> - `format_rec`: Long / Short / Both
> - `trend`: Rising / Stable / Viral / Declining
> - `sources`: which data sources support this topic (e.g. "YT, Trends, Reddit")
> - `source_strength`: comma-separated platform names
> - `evidence`: 1-line summary of strongest signal (e.g. "3 competitors with 5x+ outlier")
> - `gap_status`: Uncovered / Partially covered / Covered
>
> **Step 2e — Rank**: Sort by:
> 1. Source strength (multi > dual > single)
> 2. Then by format-relevant score
>
> **Output**: Write `topics_scored.json` to the temp directory.

After this subagent completes, verify `topics_scored.json` exists and is valid JSON.

### Pass 2 — Enrich Top Topics (Opus subagent)

Read `topics_scored.json`, take the **top 25 topics** by rank, and spawn
a subagent with **model: "opus"**.

Pass the Opus subagent:
1. The top 25 topics from `topics_scored.json` (with scores and evidence)
2. Channel profile from `memory/channel-profile.md`
3. Format flag

> You are a content strategy analyst. Enrich these pre-scored topics with
> deep analysis. For each of the 25 topics:
>
> - `why_it_works`: 2-3 sentences citing specific evidence
> - `suggested_angle`: tailored to this channel's audience and tone
> - `hook_ideas`: 2-3 title/hook ideas (newline-separated)
>   - If format=longform or both: include long-form titles
>   - If format=shorts or both: include shorts hooks
> - `research_more`: channels, subreddits, search terms to explore further
>
> Keep all existing fields (`topic`, `lf_score`, `shorts_score`, `format_rec`,
> `trend`, `sources`, `source_strength`, `evidence`, `gap_status`) unchanged.
>
> **Output**: Write `topics_analysis.json` to the temp directory with all 25
> enriched topics.

After the subagent completes, verify `topics_analysis.json` exists and contains
valid JSON with all expected fields.

---

## Step 3 — Export to Google Sheet

```bash
python3 executors/topics/export_topics_sheet.py \
  --input workspace/temp/topics/<PROJECT>/topics_analysis.json \
  --credentials credentials.json \
  --sheet-config workspace/config/intelligence_sheet.json
```

On success: capture the sheet URL.
On failure: show error, offer to save `topics_analysis.json` as the final output.

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
  "Deep dive into #3" — Extended research on that specific topic
  "More topics like #2" — Search for adjacent topics
  "Refresh" — Re-run with new random samples
  "Done" — Finalize
```

**STOP and wait for user input.**

---

## Step 5 — Interactive Refinement (Optional)

| User says | Action |
|-----------|--------|
| "Deep dive into #N" | Run targeted WebSearch + fetch 2-3 competitor transcripts for that topic (using `executors/research/fetch_transcript.py`). Re-score with additional context. Present extended analysis. |
| "More topics like #N" | Generate adjacent topic ideas based on that topic's keywords. Run quick YouTube search for those keywords. Score and present as a mini-list. |
| "Refresh" | Re-run Step 1-4 (new random samples from keywords/channels). |
| "Done" | Copy `topics_analysis.json` to `workspace/output/topics/<PROJECT>/`. Update `state.json` phase to "complete". Report final output path. |

After any refinement action, return to Step 4 (summary) and wait again.

---

## Error Handling

| Error | Action |
|-------|--------|
| `youtube_topics.py` fails | **Critical** — cannot proceed. Show stderr. Check yt-dlp installation. |
| `google_trends_topics.py` fails | Non-fatal — note "Trends data unavailable" in report. Proceed with available data. Scoring: Trends-dependent components get neutral score (5). |
| `reddit_topics.py` fails | Non-fatal — note "Reddit data unavailable" in report. Proceed with available data. Scoring: Reddit-dependent components get neutral score (5). |
| `twitter_topics.py` fails | Non-fatal — note "Twitter data unavailable" in report. Proceed with available data. Scoring: Twitter-dependent components get neutral score (5). |
| Sheets export fails | Show error. Offer to save analysis.json locally as fallback. |
| Channel profile missing discovery sections | Ask user for niche keywords, subreddits, adjacent niches. Add sections to `memory/channel-profile.md`. |
| No channel profile | Build first (standard channel profile flow). |
| Opus subagent fails | Retry once. If still fails, fall back to Sonnet for topic intelligence (lower quality but functional). |

---

## State Tracking

Update `workspace/temp/topics/<PROJECT>/state.json` after each phase:

```json
{
  "phase": "gathering | analyzing | exporting | complete",
  "format": "longform | shorts | both",
  "project": "<PROJECT>",
  "sources_succeeded": ["youtube", "trends", "reddit", "twitter"],
  "sources_failed": [],
  "topics_count": 25,
  "sheet_url": "https://docs.google.com/...",
  "iterations": 1
}
```
