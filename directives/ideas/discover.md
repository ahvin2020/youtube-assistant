# Directive: Idea Discovery

## Purpose
Identify high-performing content opportunities by cross-referencing signals
from YouTube competitors, Google Trends, Reddit, and Twitter/X.
Score each topic separately for long-form and shorts potential.

---

## Content Format Definitions

### Long-Form (10+ minutes)
- Deep-dive, explainer, comparison, or news reaction format
- Search demand and competitor validation are the strongest signals
- Hook matters but substance drives watch time and subscriber conversion
- Evergreen topics can be published anytime; trending topics need speed

### Shorts (< 60 seconds)
- Quick tip, one stat, hot take, or trend reaction
- Virality and trend velocity are the strongest signals
- First 2 seconds decide everything — hook must be instant
- Platform targets: YouTube Shorts, TikTok, Instagram Reels

---

## Data Source Hierarchy

| Source | Best For | Reliability |
|--------|----------|-------------|
| YouTube (yt-dlp) | Competitor validation, content gaps, outlier detection | High |
| Google Trends (pytrends) | Search demand, trend velocity, rising queries | Medium (rate-limited) |
| Reddit (public API) | Discussion depth, audience pain points, sentiment | High |
| Twitter/X (curl_cffi) | Virality signals, real-time sentiment, breaking news reaction | Medium (rate-limited, cookies can expire) |

**Graceful degradation**: YouTube data is required. All other sources are
optional — if a source fails, proceed with available data and note the gap
in the report.

---

## Scoring Framework

### Long-Form Score (0-10)

| Component | Weight | Source | Scoring Guide |
|-----------|--------|--------|---------------|
| Discussion depth | 30% | Reddit | Specific user pain points and "information gain" (unique perspectives, confusion, unanswered questions) = 9-10; moderate engagement = 5-6; no Reddit presence = 3 |
| Search demand | 25% | Google Trends + YouTube suggestions | Breakout terms on Trends + strong autocomplete presence = 9-10; moderate + stable = 5-6; low/declining = 2-3 |
| Competitor validation | 25% | YouTube competitor outliers | Outlier performance (high views relative to sub count) from multiple channels = 9-10; single competitor = 6-7; no coverage = 3-4 |
| Content gap | 15% | Own channel analysis | Freshness gap: never covered or top results >1 year old = 9-10; covered >90 days ago = 5-6; recently covered (<30 days) = 1-2 |
| Trend momentum | 5% | Twitter | Macro-trend velocity on Twitter = 10 (viral); rising = 7-8; stable = 4-5; declining = 1-2 |

**Long-form score = weighted sum, rounded to 1 decimal.**

### Shorts Score (0-10)

| Component | Weight | Source | Scoring Guide |
|-----------|--------|--------|---------------|
| Trend velocity | 35% | Twitter + Google Trends realtime | Rapid spikes on Twitter and realtime Trends = 9-10; stable = 4-5; declining = 1-2 |
| Virality signal | 25% | Reddit | Polarizing hooks and top-voted comments = 9-10; moderate = 5-6; no presence = 2-3 |
| Hook potential | 20% | Title analysis | Stateable in <2 seconds with emotional punch = 9-10; needs context = 4-5; complex/abstract = 1-3 |
| Shareability | 10% | Reddit + Twitter | Potential for remixes, saves, social shares = 8-10; informational = 4-5 |
| Competitor shorts perf | 10% | YouTube shorts data | Benchmarking visual formats trending in the niche = 9-10; no shorts data = 5 |

**Shorts score = weighted sum, rounded to 1 decimal.**

### Format Recommendation

| LF Score | Shorts Score | Recommendation |
|----------|-------------|----------------|
| >= 6 | >= 6 | **Both** |
| >= 6 | < 6 | **Long** |
| < 6 | >= 6 | **Short** |
| < 6 | < 6 | Include if best available, flag as "Weak" |

### Source Strength

List the platform names that validated the topic, comma-separated:
- e.g. `YouTube, Trends, Reddit` or `YouTube, Twitter` or `Reddit`

Use these platform names: **YouTube**, **Trends**, **Reddit**, **Twitter**.
Topics validated by more sources are stronger signals. Prioritize them in ranking.

---

## Topic Clustering Rules

1. **Merge** topics that share 2+ keywords AND address the same user intent
   - Example: "recession investing" + "bear market strategy" + "investing during downturn" → one cluster
2. **Keep separate** if the angle is fundamentally different
   - Example: "recession investing" vs "recession job loss" — different user intent
3. Use the **most specific and engaging** topic name as the cluster label
4. Evidence from all merged entries aggregates into one topic
5. A topic backed by multiple sources (YouTube + Trends + Reddit) is one cluster, not three separate entries

---

## Content Gap Analysis

Compare each discovered topic against the user's own channel recent videos:
- **Uncovered**: no video on this topic in the last 90 days
- **Partially covered**: related video exists but different angle, or covered >90 days ago
- **Covered**: video on this specific topic within last 30 days

Prioritize **Uncovered** and **Partially covered** topics.

---

## Output Format (ideas_analysis.json)

Each topic in the output array must have these fields:

```json
{
  "topic": "Topic name/theme",
  "lf_score": 7.5,
  "shorts_score": 4.2,
  "format_rec": "Long",
  "trend": "Rising",
  "why_it_works": "2-3 sentences citing specific evidence from sources",
  "suggested_angle": "Channel-specific angle considering audience and tone",
  "hook_ideas": "2-3 title/hook suggestions separated by newlines",
  "sources": "YT, Trends, Reddit",
  "evidence": "Top performing videos/posts with view counts and outlier scores",
  "research_more": "Specific channels, subreddits, search terms to explore",
  "gap_status": "Uncovered"
}
```

---

## Data Freshness

When enriching topics (writing `why_it_works`, `suggested_angle`, or `hook_ideas`),
do NOT reference time-sensitive data from training knowledge (e.g., "with rates at X%",
"after Q3 earnings showed..."). Use only data from the executor results or web-search
for the latest figure. If you cite a number, include "as of [date]".

---

## What NOT to Do

1. Do NOT rank topics solely by one source — cross-reference signals
2. Do NOT include topics the channel just covered (< 30 days)
3. Do NOT oversell weak signals — if a topic is based on one Reddit post, say so
4. Do NOT generate generic topics ("how to save money") without evidence
5. Do NOT ignore declining trends — flag them as declining, don't just omit
6. Do NOT confuse a viral VIDEO with a viable TOPIC — one video going viral
   doesn't make the topic broadly addressable
7. Do NOT score hook potential based on your preference — score based on
   evidence of what hooks work in this niche
