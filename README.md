# youtube-assistant

A Claude Code-powered YouTube production assistant. Drop in a raw video, point it at your script, and it automatically transcribes, aligns, and cuts your footage — all from your editor via slash commands.

Built on the **DOE (Directive-Orchestrator-Executor)** pattern: Claude reads rules, follows a coordination plan, and calls Python scripts to do the real work.

---

## How It Works

```
You run /cut
    │
    ▼
.claude/commands/cut.md        ← slash command definition
    │
    ▼
directives/video/auto-edit.md  ← rules and constraints
    │
    ▼
orchestrators/video/auto-edit.md  ← step-by-step coordination plan
    │
    ▼
executors/video/transcribe.py     ← transcribes video with local Whisper
executors/video/apply_cuts.py     ← cuts video with ffmpeg
    │
    ▼
workspace/output/                 ← your edited video lands here
```

Claude handles the semantic alignment between your transcript and script — matching meaning, not just words — then shows you a cut plan to review before anything is touched.

---

## Features

| Command | Status | Description |
|---|---|---|
| `/cut` | Built | Transcribe + align + cut video to match a script |
| `/research` | Stub | Topic research pipeline |
| `/thumbnail` | Stub | Thumbnail generation |
| `/post` | Stub | Upload to YouTube via Data API v3 |

---

## Prerequisites

- **Python 3.10+**
- **ffmpeg** — for audio extraction and video cutting
  ```bash
  brew install ffmpeg
  ```
- **openai-whisper** — local transcription, no API key needed
  ```bash
  pip install openai-whisper
  ```
  > Downloads ~74MB model on first run.
- **Claude Code** — this assistant runs inside Claude Code

---

## Setup

```bash
git clone https://github.com/ahvin2020/youtube-assistant.git
cd youtube-assistant
pip install openai-whisper
brew install ffmpeg  # if not already installed
```

The workspace folders are already scaffolded:

```
workspace/
  input/    ← drop your raw video files here
  output/   ← edited videos land here
  temp/     ← transcripts and cut specs (ephemeral, safe to delete)
```

---

## Usage

### Cut a video to match a script

1. Drop your raw footage into `workspace/input/`
2. Open the project in Claude Code
3. Run `/cut` and follow the prompts

Claude will:
- Transcribe your video locally using Whisper
- Align the transcript against your script (by meaning, not exact words)
- Show you a cut plan — which segments to keep, trim, or remove
- Ask for your confirmation before applying any cuts
- Output the edited video to `workspace/output/`

---

## Project Structure

```
.claude/commands/       ← slash command definitions (/cut, /post, etc.)
agents/                 ← persona files loaded for domain-specific sessions
directives/             ← rules and constraints per domain
orchestrators/          ← step-by-step coordination plans
executors/              ← standalone Python scripts that do the actual work
prompts/                ← reusable Claude prompt templates
workspace/
  input/                ← source media (gitignored)
  output/               ← final processed files (gitignored)
  temp/                 ← intermediate files (gitignored)
```

---

## Credentials (for future /post)

The `/post` command (YouTube upload) will require Google OAuth 2.0 credentials.

1. Copy the sample file:
   ```bash
   cp credentials.sample.json credentials.json
   ```
2. Fill in your `client_id` and `client_secret` from the [Google Cloud Console](https://console.cloud.google.com/)
3. `credentials.json` is gitignored — it will never be committed

---

## Roadmap

- [ ] `/research` — YouTube transcript fetching and topic research
- [ ] `/thumbnail` — AI-generated thumbnails
- [ ] `/post` — upload and schedule videos via YouTube Data API v3
