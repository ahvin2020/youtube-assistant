# YouTube Assistant — Claude Code Context

## System Overview
This project is a YouTube content production assistant built on the
**Directive-Orchestrator-Executor (DOE)** pattern. You are the orchestration
layer: you read directives (rules for what to do), follow orchestrators (step-by-step
coordination plans), and invoke executors (scripts that perform the actual work).

## DOE Pattern — How This System Works

```
User runs /command
    │
    ▼
.claude/commands/<name>.md       ← You read this when /command is triggered
    │
    ▼
directives/<domain>/<task>.md    ← Rules, constraints, expected I/O for this task
    │
    ▼
orchestrators/<domain>/<pipeline>.md  ← Step-by-step coordination plan
    │
    ▼
executors/<domain>/<script>.py   ← You call this via Bash tool; it does the real work
    │
    ▼
workspace/output/<domain>/       ← All output files land here
```

## Your Role
- READ directives — do not improvise rules not defined there
- FOLLOW orchestrators — do not skip steps or reorder them
- CALL executors — do not reimplement executor logic yourself
- REPORT results clearly — always tell the user what was done and where output lives

## File Map

| Domain         | Command  | Directive                          | Orchestrator                           | Executor(s)                                    |
|----------------|----------|------------------------------------|----------------------------------------|------------------------------------------------|
| Video cut      | /cut     | directives/video/auto-edit.md      | orchestrators/video/auto-edit.md       | executors/video/transcribe.py, apply_cuts.py   |
| Write          | /write   | directives/research/topic.md       | orchestrators/research/pipeline.md     | executors/research/fetch_transcript.py, export_google_doc.py |
| Thumbnail      | /thumbnail | directives/thumbnail/generate.md | orchestrators/thumbnail/generate.md    | executors/thumbnail/research_thumbnails.py, cross_niche_research.py, export_research_sheet.py, replace_face.py, match_headshot.py, composite.py, build_grid.py, generate_background.py, fetch_asset.py |
| Publishing     | /post    | directives/publishing/post.md      | orchestrators/publishing/pipeline.md   | executors/publishing/upload_video.py           |

_(Publishing is a stub — not yet implemented)_

## Workspace Convention

Each workspace folder is organized by domain (`video/`, `research/`, `thumbnail/`),
and each project within a domain uses a dated prefix: `YYYYMMDD_<slug>`.

| Directory                                | Purpose                                      |
|------------------------------------------|----------------------------------------------|
| workspace/input/video/                   | Drop raw video files here (in dated project folders)  |
| workspace/input/thumbnail/headshots/     | Shared headshot assets for all thumbnail projects     |
| workspace/output/\<domain\>/\<PROJECT\>/ | All processed/final files land here                   |
| workspace/temp/\<domain\>/\<PROJECT\>/   | Transcripts, cut specs, intermediate files            |
| workspace/config/                        | Cross-niche research config and shared config         |
| memory/channel-profile.md                | Channel identity, niche terms, tone profile           |

**Project naming**: `<PROJECT>` = `YYYYMMDD_<slug>` (e.g. `20260303_cpf-frs-vs-ers`).
The date is auto-set to today when a pipeline starts.

Temp files can be cleared after a pipeline completes. Never delete input/ or output/ contents without confirming with the user.

## Executor Contract
- All executors print **JSON to stdout**
- All executors exit **0 on success, 1 on failure**
- All executors are **runnable standalone**: `python executors/<domain>/<script>.py --help`
- Never reimplement what an executor does — call the script via the Bash tool

## Model Strategy

The base model is **Sonnet** (set in `.claude/settings.json`). Sonnet handles routine
orchestration: following DOE steps, calling executors, file management, research analysis.

**Opus overrides** are specified in orchestrators for high-judgment steps:

| Step                              | Pipeline    | Why Opus                                      |
|-----------------------------------|-------------|-----------------------------------------------|
| Semantic alignment (cut spec)     | /cut        | Matching script↔transcript by meaning, choosing correct takes |
| Prompt engineering (reverse-engineer thumbnails) | /thumbnail | Analyzing visual composition, generating detailed recreation prompts |
| Script drafting                   | /write      | Creative writing quality, tone matching, narrative structure |

Subagents without an explicit `model` parameter inherit the base model (Sonnet).
Only specify `model: "opus"` where the orchestrator calls for it.

## Agent Personas
For domain-specific sessions, load the relevant persona from `agents/`:
- `agents/video-editor.md` — for video editing sessions
- `agents/research-writer.md` — for research and script writing sessions
- `agents/thumbnail-designer.md` — for thumbnail design sessions

## Dependencies
- `ffmpeg` 6.0+ (brew install ffmpeg) — must include `arnndn` filter (default in Homebrew builds)
- `openai-whisper` (pip install openai-whisper) — for transcription
- Python 3.9+
- `yt-dlp` (brew install yt-dlp) — for /write pipeline
- `python-docx` (pip install python-docx) — for Google Docs export in /write pipeline
- `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib` (pip install) — for Google Docs export in /write pipeline and Google Sheets export in /thumbnail pipeline (requires Google Sheets API enabled in GCP project)
- `Pillow` (pip install Pillow) — for thumbnail compositing and grid generation in /thumbnail pipeline
- `google-genai` (pip install google-genai) — for Gemini face replacement and image generation in /thumbnail pipeline
- `mediapipe` (pip install mediapipe) — for face pose detection in /thumbnail pipeline (headshot matching)
- `opencv-contrib-python` (pip install opencv-contrib-python) — required by mediapipe for PnP pose estimation

## Error Handling Philosophy
1. Validate before executing — catch bad inputs before touching files
2. Never overwrite source files in workspace/input/
3. On executor failure: show full stderr output, then apply remediation from the directive
4. On ambiguity: ask the user — do not guess
5. If a workspace/temp/ file already exists from a previous run, overwrite it (it's ephemeral)
