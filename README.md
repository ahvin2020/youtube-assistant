# youtube-assistant

A Claude Code-powered YouTube production assistant. Transcribe and cut video, research and write scripts, and design thumbnails — all from your editor via slash commands.

Built on the **DOE (Directive-Orchestrator-Executor)** pattern: Claude reads rules, follows a coordination plan, and calls Python scripts to do the real work.

---

## How It Works

```
You run /command
    │
    ▼
.claude/commands/<name>.md          ← slash command definition
    │
    ▼
directives/<domain>/<task>.md       ← rules and constraints
    │
    ▼
orchestrators/<domain>/<pipeline>.md  ← step-by-step coordination plan
    │
    ▼
executors/<domain>/<script>.py      ← Python scripts that do the actual work
    │
    ▼
workspace/output/<domain>/          ← your files land here
```

---

## Features

| Command | Status | Description |
|---|---|---|
| `/cut` | Built | Transcribe + align + cut video to match a script |
| `/write` | Built | Research topics, outline, and draft scripts with tone matching |
| `/thumbnail` | Built | Cross-niche research + AI thumbnail generation with face replacement |
| `/post` | Stub | Upload to YouTube via Data API v3 |

---

## Prerequisites

- **Python 3.9+**
- **Claude Code** — this assistant runs inside Claude Code
- **ffmpeg** — for audio extraction and video cutting
  ```bash
  brew install ffmpeg
  ```
- **yt-dlp** — for fetching YouTube transcripts and metadata
  ```bash
  brew install yt-dlp
  ```
- **openai-whisper** — local transcription, no API key needed
  ```bash
  pip install openai-whisper
  ```

### For `/write` pipeline
```bash
pip install python-docx google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### For `/thumbnail` pipeline
```bash
pip install Pillow google-genai mediapipe opencv-contrib-python
```

---

## Setup

```bash
git clone https://github.com/ahvin2020/youtube-assistant.git
cd youtube-assistant
brew install ffmpeg yt-dlp
pip install openai-whisper
```

### Credentials

1. Copy the sample file:
   ```bash
   cp credentials.sample.json credentials.json
   ```
2. Fill in your keys from the [Google Cloud Console](https://console.cloud.google.com/):
   - `client_id` and `client_secret` — for Google Docs and Sheets OAuth
   - `gemini_api_key` — for Gemini image generation ([get one here](https://aistudio.google.com/apikey))
3. `credentials.json` is gitignored — it will never be committed

### Channel Profile

On first use of `/thumbnail` or `/write`, the assistant will ask for your YouTube channel URL, analyze your recent videos, and auto-generate a channel profile at `memory/channel-profile.md`. This provides niche terms for research filtering and a tone profile for script writing.

### Workspace

The workspace folders are already scaffolded:

```
workspace/
  input/              ← source media and headshots (gitignored)
  output/             ← final processed files (gitignored)
  temp/               ← intermediate files (gitignored)
  config/             ← cross-niche research config
```

---

## Usage

### `/cut` — Cut video to match a script

1. Drop your raw footage into `workspace/input/video/`
2. Run `/cut` and follow the prompts

Claude will:
- Transcribe your video locally using Whisper
- Align the transcript against your script (by meaning, not exact words)
- Show you a cut plan — which segments to keep, trim, or remove
- Output the edited video to `workspace/output/video/`

### `/write` — Research and write a script

1. Run `/write` with a topic
2. Claude researches YouTube videos on the topic, fetches transcripts, and builds a brief
3. Iterative workflow: Research → Outline → Script draft
4. Final script exported to Google Docs

### `/thumbnail` — Design thumbnails

1. Add headshot photos to `workspace/input/thumbnail/headshots/`
2. Run `/thumbnail` with your video topic

Claude will:
- Run cross-niche competitive research (outlier detection across niches)
- Export scored results to a Google Sheet for browsing
- You pick 5 reference thumbnails from the sheet
- Claude reverse-engineers each reference into a Gemini prompt
- Generates face-replaced thumbnails using your headshots
- Presents a grid for review and iterative refinement

---

## Project Structure

```
.claude/commands/       ← slash command definitions (/cut, /write, /thumbnail)
agents/                 ← persona files loaded for domain-specific sessions
directives/             ← rules and constraints per domain
orchestrators/          ← step-by-step coordination plans
executors/              ← standalone Python scripts that do the actual work
memory/                 ← channel profile (generated per-user, gitignored)
workspace/
  input/                ← source media and headshots (gitignored)
  output/               ← final processed files (gitignored)
  temp/                 ← intermediate files (gitignored)
  config/               ← cross-niche keywords, monitored channels
```

---

## Roadmap

- [ ] `/post` — upload and schedule videos via YouTube Data API v3
