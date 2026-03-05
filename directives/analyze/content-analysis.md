# Directive: Content Analysis & Hook Mining

## Purpose
Analyze own-channel and competitor content to identify performance patterns,
extract proven hooks (title + transcript opening), and build a curated hook
database that feeds back into the `/write` pipeline.

---

## Modes

### Full Analysis (default)
Scan own channel + all monitored competitors. Extract hooks from top performers.
Generate performance report and update hook database.

### Deep-Dive (video URL provided)
Analyze one specific video in depth. Fetch its transcript, extract hooks,
compare performance against competitor videos on the same topic.

### No Transcripts
Skip transcript fetching. Only extract title hooks (not opening hooks).
Faster but misses the spoken hook — the first 10-30 seconds of the video.

---

## Hook Definitions

### Title Hook
The video title as a clickability mechanism. What makes someone click?
Extracted directly from the title text.

### Opening Hook
The first 10-30 seconds of what the creator says on camera. What makes someone
keep watching past the intro? Extracted from transcript segments.

---

## Hook Categories

Use the categories from `workspace/config/research_config.json` → `hook_categories`:

| Category | What it triggers | Example |
|----------|-----------------|---------|
| money | Financial aspiration/fear | "This $500K mistake nobody talks about" |
| time | Speed/efficiency desire | "I saved 10 hours a week with this" |
| curiosity | Information gap | "The real reason your savings aren't growing" |
| transformation | Before/after narrative | "How I went from $0 to $100K in 2 years" |
| contrarian | Challenges conventional wisdom | "Why I stopped investing in index funds" |
| urgency | Time pressure | "Before it's too late: what's happening to CPF" |
| other | Doesn't fit existing categories | Note the pattern for potential new category |

If a hook doesn't fit any category, label it `"other"` and describe the pattern.
If 3+ hooks share the same "other" pattern, suggest a new category name.

---

## Performance Scoring

### Outlier Score
`outlier_score = video_views / channel_average_views`

An outlier score of 2.0 means the video got 2x the channel's average views.
This is the primary signal — it normalizes for channel size.

### Engagement Rate
`engagement_rate = (likes + comments) / views`

Higher engagement = the content resonated beyond passive viewing.

### Hook Performance Score (0-10)
Composite score for ranking hooks in the database:

```
performance_score = (
    normalize(outlier_score, 0-10) * 0.6 +
    normalize(engagement_rate, 0-0.15) * 0.2 +
    recency_bonus * 0.2
)
```

Where:
- `normalize(outlier_score)`: 1.0x = 2, 2.0x = 4, 3.0x = 6, 5.0x = 8, 10.0x+ = 10
- `normalize(engagement_rate)`: 0.01 = 2, 0.03 = 4, 0.05 = 6, 0.08 = 8, 0.12+ = 10
- `recency_bonus`: < 30 days = 10, 30-90 = 7, 90-180 = 4, > 180 = 2

---

## Hook Database Rules (`workspace/config/hooks.json`)

1. **Max 350 hooks** — pruned after each run by performance_score
2. **Dedup by ID** — `id = "h_" + first 8 chars of sha256(text + video_id)`
3. **Merge, never overwrite** — existing hooks get `times_seen++` and `last_seen` updated
4. **Repeat bonus** — hooks seen across multiple runs from different videos are stronger signals.
   For ranking/pruning only: effective_score = performance_score + (times_seen - 1) * 0.3
5. **Track analyzed videos** — `analyzed_videos` set prevents re-processing the same video
6. **Format field** — `"title"` or `"opening"` (opening hooks also store `opening_seconds`)

---

## Analysis Output Schemas

### performance_overview.json
```json
[
  {
    "rank": 1,
    "title": "Video Title",
    "channel": "Channel Name",
    "is_own_channel": false,
    "views": 150000,
    "outlier_score": 4.2,
    "engagement_rate": 0.065,
    "like_view_ratio": 0.045,
    "duration": 612,
    "upload_date": "20260301",
    "days_since_upload": 4
  }
]
```

### pattern_insights.json
```json
[
  {
    "pattern": "Curiosity gap titles with numbers outperform direct titles 3:1",
    "category": "hook",
    "evidence": "Top 5 by outlier: 4/5 use curiosity + number pattern",
    "strength": "strong",
    "actionable_insight": "Lead titles with a number + curiosity gap: '3 reasons nobody talks about X'"
  }
]
```

### content_gaps.json
```json
[
  {
    "topic": "CPF investment options",
    "competitor_coverage": 4,
    "own_coverage": 0,
    "gap_type": "Uncovered",
    "opportunity_score": 7.8,
    "suggested_angle": "Comparison angle — which CPF investment option beats the rest?"
  }
]
```

### extracted_hooks.json
Array of hook objects matching the `hooks.json` schema (see orchestrator).

---

## What NOT to Do

1. Do NOT extract hooks from low-performing videos (outlier < 1.5)
2. Do NOT copy hooks verbatim into scripts — they're patterns to learn from
3. Do NOT over-categorize — if it's ambiguous between two categories, pick the dominant one
4. Do NOT count the same hook pattern twice from the same video (one title hook + one opening hook per video max)
5. Do NOT prune hooks that have been seen across multiple runs (times_seen > 1) unless they're in the bottom 10% by score
6. Do NOT include hooks from excluded formats (see `exclude_formats` in research_config.json)
