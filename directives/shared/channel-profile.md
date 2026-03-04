# Directive: Channel Profile

Shared by `/thumbnail` and `/write` pipelines. The channel profile lives at
`memory/channel-profile.md` and is built once, then reused across sessions.

---

## Check

1. Read `memory/channel-profile.md`
2. If it exists: extract what you need (niche terms for /thumbnail, tone for /write)
3. Verify `workspace/config/cross_niche.json` has `own_niche_terms` populated —
   if empty, re-extract from the profile and update the config
4. If it does NOT exist: build it (see below)

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

### 5. Write Profile

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
```

### 6. Update Config

Update `workspace/config/cross_niche.json`:
- Set `own_niche_terms` to the extracted niche terms array

### 7. Confirm

Ask user: "Here's your channel profile: [summary]. Anything to adjust?"
