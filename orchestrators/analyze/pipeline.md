# Orchestrator: Content Analysis Pipeline

Follow every step in order. Do not skip steps.

---

## Pre-Flight Checklist

- [ ] Load channel profile from `memory/channel-profile.md`
  - If missing: ask user for YouTube channel URL, build profile first
  - Extract `channel_id` for own-channel analysis
  - Extract Monitored Channels, Niche Categories, Discovery Keywords
- [ ] Determine mode from command arguments:
  - `full` (default), `deep-dive` (URL given), `no-transcripts`
- [ ] If deep-dive mode: store `video_url` from arguments
- [ ] Derive PROJECT name:
  - Full/hooks-only/no-transcripts: `YYYYMMDD_content-analysis`
  - Deep-dive: `YYYYMMDD_deepdive-<video-slug>`
- [ ] Create workspace directories:
  ```
  mkdir -p workspace/temp/analyze/<PROJECT>/transcripts
  mkdir -p workspace/output/analyze/<PROJECT>
  ```
- [ ] Load existing hook database (if any):
  ```
  cat workspace/config/hooks.json 2>/dev/null
  ```
  Extract `analyzed_videos` set for dedup. If file doesn't exist, note this is first run.
- [ ] Write initial `state.json` to `workspace/temp/analyze/<PROJECT>/`:
  ```json
  {
    "phase": "gathering",
    "mode": "<mode>",
    "project": "<PROJECT>",
    "video_url": null
  }
  ```

---

## Step 1 — Data Gathering (Executor)

Record start time using Bash:
```bash
date +%s
```
Store the output as `PIPELINE_START` (epoch seconds).

### Full / No-Transcripts Mode

```bash
python3 executors/analyze/fetch_channel_data.py \
  --channel-profile memory/channel-profile.md \
  --channel-id <channel_id> \
  --own-count 50 --competitor-count 20 \
  --max-channels 15 --days 180 \
  --output workspace/temp/analyze/<PROJECT>/channel_data.json
```

On success: report data gathering summary (channels scanned, videos found, elapsed time).
On failure: show stderr, check yt-dlp installation.

### Deep-Dive Mode

```bash
python3 executors/analyze/fetch_channel_data.py \
  --channel-profile memory/channel-profile.md \
  --channel-id <channel_id> \
  --video-url "<video_url>" \
  --competitor-count 20 \
  --output workspace/temp/analyze/<PROJECT>/channel_data.json
```

The executor fetches the target video metadata, searches for competitors on the
same topic (using title keywords), and returns a focused comparison dataset.

---

## Step 2 — Transcript Fetching (Parallel, Executor)

**Skip this step if mode is `no-transcripts`.**

Read `channel_data.json`. Identify the top videos for transcript fetching:

### Full Mode
Take the **top 20 videos by outlier_score** from `all_videos_sorted`.
Filter out any video IDs already in `analyzed_videos` (from hooks.json).
This ensures we only fetch transcripts for videos not previously analyzed.

### Deep-Dive Mode
Fetch transcript for the **target video** + **top 5 competitors** by outlier_score.

### Parallel Execution

**IMPORTANT**: Launch all `fetch_transcript.py` calls in a **single message**
using Bash tool with `run_in_background: true` for each.

```bash
python3 executors/research/fetch_transcript.py \
  "https://www.youtube.com/watch?v=<video_id>" \
  "workspace/temp/analyze/<PROJECT>/transcripts/<video_id>.json"
```

Some will fail (no captions) — that is fine, non-fatal. Report how many
succeeded out of how many attempted.

---

## Step 3 — Performance Analysis (Sonnet Subagent)

Read `channel_data.json` and trim to reduce token cost:
- Own-channel: top 30 videos (keep only: title, channel, views, outlier_score,
  engagement_rate, upload_date, duration, days_since_upload, is_own_channel)
- Competitor: top 30 videos by outlier_score (same fields)
- Monthly trends from own-channel data

Spawn a subagent (**no model override** — inherits Sonnet).

Pass the subagent the trimmed data and channel profile.

> You are a content performance analyst. Analyze own-channel vs competitor data.
>
> **3a — Performance Overview**: Rank all videos by outlier_score. Identify:
> - Top 10 own-channel performers with why they outperformed
> - Top 10 competitor performers in the same niche
> - Overall channel health (avg views trend, engagement trend)
>
> **3b — Pattern Detection**: Find patterns across top performers:
> - Topic patterns: what subjects perform best?
> - Format patterns: what durations perform best?
> - Title patterns: what title structures get the most views?
> - Timing patterns: any upload frequency/day correlations?
>
> **3c — Content Gaps**: Compare own-channel topics vs competitor topics.
> Find topics competitors cover successfully that own channel hasn't.
> Score each gap: opportunity_score based on competitor outlier × coverage count.
>
> Write three files to `workspace/temp/analyze/<PROJECT>/`:
> - `performance_overview.json` — ranked video list with fields from the directive
> - `pattern_insights.json` — array of pattern objects
> - `content_gaps.json` — array of gap objects
>
> Follow the schemas in `directives/analyze/content-analysis.md`.

After the subagent completes, verify all three JSON files exist and are valid.

For **deep-dive mode**: the subagent focuses on comparing the target video
against its topic cohort. Where does it rank? What did top competitors do
differently? What patterns emerge from the topic-specific comparison?

---

## Step 4 — Hook Extraction (Opus Subagent)

This is the high-judgment step. Spawn a subagent with **model: "opus"**.

### Prepare input data

1. **Title hooks**: Top 20 video titles (from `channel_data.json`, sorted by outlier_score).
   Include: title, channel, views, outlier_score, engagement_rate.

2. **Opening hooks**: For each video with a fetched transcript, extract the
   first 30 seconds of text from the segments. Include: video_id, title,
   channel, opening_text, opening_seconds.

3. **Existing categories**: The `hook_categories` from `workspace/config/research_config.json`.

4. **Current hooks.json**: Pass the existing hooks (if any) so the subagent
   is aware of what's already been captured and can avoid duplicates.

### Subagent prompt

> You are a hook mining specialist. Extract proven hooks from top-performing videos.
>
> **4a — Title Hook Extraction**: For each top video title:
> - Extract the hook mechanism (what psychological trigger makes someone click?)
> - Categorize into one of the hook categories (money, time, curiosity,
>   transformation, contrarian, urgency) or "other"
> - Calculate performance_score using the formula in the directive
>
> **4b — Opening Hook Extraction**: For each available transcript opening:
> - Read the first 10-30 seconds
> - Extract the opening hook — the sentence/question that keeps viewers watching
> - Categorize it
> - Note the exact seconds it takes to deliver the hook (opening_seconds)
>
> **4c — Pattern Discovery**: Across all extracted hooks:
> - Which categories dominate the top performers?
> - Any hook structures that appear in 3+ videos? (proven patterns)
> - Any new patterns that don't fit existing categories? (suggest new names)
>
> For each extracted hook, output an object with these fields:
> - `text`: the hook text (title text or opening transcript text)
> - `category`: one of the hook_categories or "other"
> - `format`: "title" or "opening"
> - `opening_seconds`: seconds for opening hooks (null for title hooks)
> - `source_video_id`: video ID
> - `source_channel`: channel name
> - `source_channel_id`: channel ID
> - `views`: video view count
> - `outlier_score`: video outlier score
> - `engagement_rate`: video engagement rate
> - `performance_score`: calculated per directive formula
>
> Write the array to `workspace/temp/analyze/<PROJECT>/extracted_hooks.json`.
>
> Also write a brief `hook_patterns.md` to `workspace/temp/analyze/<PROJECT>/`
> summarizing the pattern discovery findings (4c).

After the subagent completes, verify `extracted_hooks.json` exists and is valid JSON.

---

## Step 5 — Update Hook Database (Orchestrator Logic)

This step is done directly by the orchestrator — no executor or subagent needed.

1. Read current `workspace/config/hooks.json` (or create empty structure):
   ```json
   {
     "version": 1,
     "last_updated": "<today>",
     "max_hooks": 200,
     "analyzed_videos": [],
     "hooks": []
   }
   ```

2. Read `workspace/temp/analyze/<PROJECT>/extracted_hooks.json`.

3. For each new hook:
   - Compute `id`: `"h_" + first 8 chars of sha256(text + source_video_id)`
   - Check if `id` already exists in hooks array
   - If exists: update `last_seen` to today, increment `times_seen`
   - If new: add with `date_added` = today, `last_seen` = today, `times_seen` = 1

4. Add all newly analyzed video IDs to `analyzed_videos` set.

5. Re-score all hooks (recalculate performance_score with current data if needed).

6. Sort by effective_score: `performance_score + (times_seen - 1) * 0.3`

7. Keep only top 350 hooks. But protect hooks with `times_seen > 1` from pruning
   unless they're in the bottom 10%.

8. Update `last_updated` to today.

9. Write updated `workspace/config/hooks.json`.

Report to user:
```
HOOK DATABASE UPDATED:
  New hooks added: X (Y title, Z opening)
  Existing hooks updated: N
  Hooks pruned: P
  Total hooks: T / 200
  Top categories: money (40), curiosity (35), contrarian (28), ...
```

---

## Step 6 — Export to Google Sheet (Executor)

The 4 tabs have fixed names (`Performance`, `Hooks`, `Patterns`, `Gaps`) and are
updated in place each run. Each tab shows "Updated: YYYY-MM-DD" in the header row.

```bash
python3 executors/analyze/export_analysis_sheet.py \
  --performance workspace/temp/analyze/<PROJECT>/performance_overview.json \
  --hooks workspace/config/hooks.json \
  --patterns workspace/temp/analyze/<PROJECT>/pattern_insights.json \
  --gaps workspace/temp/analyze/<PROJECT>/content_gaps.json \
  --credentials credentials.json \
  --sheet-config workspace/config/intelligence_sheet.json
```

On success: capture the sheet URL.
On failure: show error, offer to save JSON files as fallback output.

---

## Step 7 — Summary Report

Calculate elapsed time:
```bash
echo $(( $(date +%s) - PIPELINE_START ))
```
Convert to `Xm Ys` format.

Present the results:

```
CONTENT ANALYSIS COMPLETE
=========================
Mode: <full | deep-dive | no-transcripts>
Videos analyzed: X own + Y competitor from Z channels
Transcripts fetched: N/M attempted
Hooks extracted: X new (Y title, Z opening)
Hook database: T total hooks (top 350 kept)
Analysis time: Xm Ys
Sheet: <Google Sheet URL>

TOP INSIGHTS:
1. [Pattern] — [Evidence]
2. [Pattern] — [Evidence]
3. [Pattern] — [Evidence]

TOP NEW HOOKS:
1. "[Hook text]" — [Category] — [Source] — Outlier: X.Xx
2. "[Hook text]" — [Category] — [Source] — Outlier: X.Xx
3. "[Hook text]" — [Category] — [Source] — Outlier: X.Xx

OPTIONS:
  "Dive deeper into [topic]" — Fetch more transcripts for that topic area
  "Analyze [channel name]" — Deep-dive one specific competitor
  "Analyze [video URL]" — Deep-dive one specific video
  "Done" — Finalize
```

**STOP and wait for user input.**

---

## Step 8 — Interactive Refinement (Optional)

| User says | Action |
|-----------|--------|
| "Dive deeper into [topic]" | Fetch additional competitor transcripts for that topic, re-run hook extraction for those videos, update hooks.json |
| "Analyze [channel name]" | Fetch that channel's top 30 videos, extract hooks, add to database |
| "Analyze [video URL]" | Run deep-dive mode for that specific video |
| "Done" | Copy analysis files to `workspace/output/analyze/<PROJECT>/`. Update `state.json` phase to "complete". Report final output path. |

After any refinement action, return to Step 7 (summary) and wait again.

---

## Error Handling

| Error | Action |
|-------|--------|
| `fetch_channel_data.py` fails | **Critical** — cannot proceed. Show stderr. Check yt-dlp installation. |
| `fetch_transcript.py` fails for some videos | Non-fatal — log which failed, proceed with available transcripts. |
| All transcripts fail | Non-fatal — proceed with title-only hook extraction. Note in report. |
| Opus subagent fails (hook extraction) | Retry once. If still fails, fall back to Sonnet (lower quality but functional). |
| Sheets export fails | Show error. Offer to save JSON files as fallback. |
| Channel profile missing sections | Ask user for channel ID, niche keywords, etc. |
| hooks.json corrupted | Back up corrupted file, start fresh with empty database. |

---

## State Tracking

Update `workspace/temp/analyze/<PROJECT>/state.json` after each phase:

```json
{
  "phase": "gathering | transcripts | analyzing | hooks | exporting | complete",
  "mode": "full | deep-dive | no-transcripts",
  "project": "<PROJECT>",
  "video_url": null,
  "channels_scanned": 12,
  "videos_analyzed": 250,
  "transcripts_fetched": 18,
  "hooks_extracted": 34,
  "sheet_url": "https://docs.google.com/...",
  "elapsed_seconds": 180
}
```
