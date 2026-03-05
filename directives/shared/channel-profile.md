# Directive: Channel Profile

Shared by `/thumbnail` and `/write` pipelines. The channel profile lives at
`memory/channel-profile.md` and is built once, then reused across sessions.

---

## Check

1. Read `memory/channel-profile.md`
2. If it exists: extract what you need (niche terms for /thumbnail, tone for /write).
   Niche terms live in the profile's `## Niche Terms` section — executors read them
   directly via `--channel-profile` (no duplication in research_config.json).
3. If it does NOT exist: build it (see below)

---

## First-Time Build

### 1. Get Channel Identity

Ask the user for their YouTube channel URL or handle.

### 2. Fetch Recent Video Metadata

```bash
yt-dlp "https://www.youtube.com/channel/<channel_id>/videos" \
  --flat-playlist --dump-json --no-download --playlist-items 1:20
```

Extract: titles, view counts, upload dates, durations.

### 3. Fetch Transcripts

Fetch transcripts from 3-5 recent videos:

```bash
python3 executors/research/fetch_transcript.py "<video_url>" \
  "workspace/temp/thumbnail/_profile/"
```

### 4. Analyze (Claude Intelligence Step)

From the video titles and transcripts, determine:

- **Niche**: Primary topic area and specific sub-topics
- **Niche terms**: 40-80 keywords/phrases that define this channel's niche
  (these become `own_niche_terms` for cross-niche filtering — anything matching
  these terms gets excluded from cross-niche research results)
- **Content pillars**: The 3-5 main themes the channel covers
- **Tone**: Vocabulary level, sentence structure, humor, formality, catchphrases,
  how technical concepts are explained
- **Performance baseline**: Average views, top-performing topics
- **Niche categories**: Identify the channel's own niche category and 2-3
  adjacent niche categories (use category names from
  `workspace/config/research_config.json` when they match)

### 5. Generate Cross-Niche Keywords

Based on the adjacent niche categories identified in Step 4, generate 30-40
YouTube search queries that:
- Target content from adjacent niches (NOT the channel's own niche)
- Use hooks and angles that overlap with the channel's audience (e.g., money
  angles for a finance channel, productivity angles for a business channel)
- Mix broad ("how to build a business") and specific ("cognitive biases that
  cost you money") queries
- Cover each adjacent niche category roughly evenly

### 6. Generate Monitored Channels

Build a list of high-profile YouTube channels to monitor for cross-niche
research. For each category:
- **Adjacent niche categories** (from Step 4): 5-10 channels each — prioritize
  channels with 500K+ subscribers and consistent outlier content
- **Universal categories** (always include): `mega_creators`,
  `storytelling_explainers`, `creator_economy` — 3-8 channels each
- **Optional categories** (include if relevant to audience):
  `science_education`, `health_mindset`, `commentary_opinion`,
  `leadership_communication`, `philosophy_ideas`, `tech_consumer`

To find channel IDs, use yt-dlp:
```bash
yt-dlp "https://www.youtube.com/@ChannelHandle" --print channel_id --playlist-items 0
```

Present the full list to the user for review before writing to the profile.

### 7. Write Profile

Write the combined profile to `memory/channel-profile.md`:

```markdown
# Channel Profile

## Identity
- Channel: <name>
- Handle: <handle>
- Channel ID: <id>

## Niche
- Primary: <niche description>
- Content pillars: <pillar 1>, <pillar 2>, ...

## Niche Terms
<comma-separated list of 40-80 terms for cross-niche filtering>

## Tone Profile
- Vocabulary: <description>
- Style: <description>
- Formality: <level>
- Humor: <description>
- Catchphrases: <any recurring phrases>

## Performance Baseline
- Average views: ~X,XXX
- Top-performing topics: <list>
- Typical video length: <range>

## Audience Signals
<observations about audience demographics and engagement>

## Region
<two-letter country code>

## Discovery Keywords
<comma-separated niche keywords for topic discovery>

## Niche Categories
- Own: <own_niche_category>
- Adjacent: <adjacent_1>, <adjacent_2>, ...

## Community Sources
- Subreddits: <comma-separated list>
- Twitter search terms: <comma-separated list>

## Cross-Niche Keywords
<comma-separated list of 30-40 YouTube search queries for adjacent niches>

## Monitored Channels

### <category_name>
- <Channel Name> (<channel_id>)
- ...

### <another_category>
- ...
```

### 8. Confirm

Ask user: "Here's your channel profile: [summary]. Anything to adjust?"
