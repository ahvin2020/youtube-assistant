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
| Video edit     | /edit    | directives/video/edit.md           | orchestrators/video/edit.md            | executors/video/transcribe.py, apply_cuts.py, verify_cut.py; executors/enhance/validate_spec.py, prepare_assets.py, render_preview.js, render_final.js |
| Write          | /write   | directives/research/topic.md       | orchestrators/research/pipeline.md     | executors/research/fetch_transcript.py, export_google_doc.py |
| Thumbnail      | /thumbnail | directives/thumbnail/generate.md | orchestrators/thumbnail/generate.md    | executors/thumbnail/research_thumbnails.py, cross_niche_research.py, export_research_sheet.py, replace_face.py, match_headshot.py, composite.py, build_grid.py, generate_background.py, fetch_asset.py |
| Ideas          | /idea  | directives/ideas/discover.md      | orchestrators/ideas/pipeline.md       | executors/ideas/youtube_ideas.py, google_trends_ideas.py, reddit_ideas.py, twitter_ideas.py, export_ideas_sheet.py |
| Analyze        | /analyze | directives/analyze/content-analysis.md | orchestrators/analyze/pipeline.md  | executors/analyze/fetch_channel_data.py, export_analysis_sheet.py |
| Publishing     | /post    | directives/publishing/post.md      | orchestrators/publishing/pipeline.md   | executors/publishing/upload_video.py           |

| Status         | /status  | _(none)_                           | _(none)_                               | _(none — reads state.json files directly)_     |

_(Publishing is a stub — not yet implemented)_

**Cross-pipeline linking**: Projects are linked across pipelines by `content_slug` — a
slug field in each `state.json` (e.g., `ai-stock-picks`). The `/status` command groups
projects by `content_slug` to show pipeline progress. Handoffs (`/idea` → `/write`,
`/write` → `/edit`, `/write` → `/thumbnail`) auto-detect upstream outputs and offer to
pre-populate downstream inputs.

**Shared executor utilities** (`executors/shared/`):
- `youtube.py` — `search_youtube`, `fetch_channel_recent_videos`, `enrich_video`
- `google_sheets.py` — OAuth2 auth, spreadsheet CRUD, tab management
- `parse_profile.py` — `channel-profile.md` parser (niche terms, keywords, channels) + `thumbnail-channels.md` parser

## Workspace Convention

Each workspace folder is organized by domain (`video/`, `research/`, `thumbnail/`, `topics/`),
and each project within a domain uses a dated prefix: `YYYYMMDD_<slug>`.

| Directory                                | Purpose                                      |
|------------------------------------------|----------------------------------------------|
| workspace/input/video/                   | Drop raw video files here (in dated project folders)  |
| workspace/input/thumbnail/headshots/     | Shared headshot assets for all thumbnail projects     |
| workspace/output/\<domain\>/\<PROJECT\>/ | All processed/final files land here                   |
| workspace/temp/\<domain\>/\<PROJECT\>/   | Transcripts, cut specs, intermediate files            |
| workspace/config/                        | System config (scoring rules, filters, thresholds)    |
| memory/channel-profile.md                | Channel identity, niche terms, tone, discovery config, cross-niche keywords, monitored channels |
| memory/thumbnail-channels.md             | Curated channels for thumbnail research (high thumbnail quality) |
| workspace/config/thumbnail_seen.json     | Cross-run seen-video tracking (auto-pruned >1 month) |
| workspace/config/thumbnail_rotation.json | Channel rotation tracking (least-recently-sampled priority) |

**Project naming**: `<PROJECT>` = `YYYYMMDD_<slug>` (e.g. `20260303_cpf-frs-vs-ers`).
The date is auto-set to today when a pipeline starts.

Temp files can be cleared after a pipeline completes. Never delete input/ or output/ contents without confirming with the user.

## Executor Contract
- All executors print **JSON to stdout**
- All executors exit **0 on success, 1 on failure**
- All executors are **runnable standalone**: `python executors/<domain>/<script>.py --help`
- Never reimplement what an executor does — call the script via the Bash tool

## Model Strategy

Three-tier model usage — pick the cheapest model that can do the job well:

| Tier       | Model      | Use for                                                        |
|------------|------------|----------------------------------------------------------------|
| **Haiku**  | `"haiku"`  | Mechanical / deterministic tasks: file lookups, formatting, parsing, simple transforms, data extraction, boilerplate generation |
| **Sonnet** | (default)  | Routine orchestration: following DOE steps, calling executors, file management, research analysis |
| **Opus**   | `"opus"`   | High-judgment tasks requiring deep reasoning, creativity, or nuanced analysis |

**Opus overrides** (specified in orchestrators):

| Step                              | Pipeline    | Why Opus                                      |
|-----------------------------------|-------------|-----------------------------------------------|
| Semantic alignment (cut spec)     | /edit        | Script-guided mode only — matching script↔transcript by meaning. Retake-only mode uses Sonnet (pattern matching is sufficient) |
| Graphics analysis (visual suggestions) | /edit   | Visual storytelling judgment, content-aware enhancement placement |
| Prompt engineering (reverse-engineer thumbnails) | /thumbnail | Analyzing visual composition, generating detailed recreation prompts |
| Script drafting                   | /write      | Creative writing quality, tone matching, narrative structure |
| Topic intelligence (clustering, scoring) | /idea | Sonnet handles both passes (clustering + enrichment) — fast enough for pattern-matching hooks/angles |
| Hook extraction (mining proven hooks) | /analyze | Understanding why hooks work, categorizing language patterns |

**Haiku candidates**: file search/read subagents, JSON parsing, simple data formatting,
template filling, validation checks, extracting structured data from text.
Use `model: "haiku"` explicitly when spawning subagents for these tasks.

Subagents without an explicit `model` parameter inherit the base model (Sonnet).

## Efficiency Principles

### No Wastage — Single Source of Truth
- **Never create duplicate sources of truth.** Before creating a new config file, data
  structure, or helper function, check if one already exists that serves the same purpose.
- **Never write redundant functions.** Before writing a new utility, search the codebase
  for existing functions that do the same thing. Extend or reuse them instead.
- **Consolidate, don't duplicate.** If two files store overlapping information, merge them
  into one and update all references. One canonical location per piece of data.
- **Shared utilities belong in shared modules.** If multiple executors need the same logic
  (e.g., parsing `channel-profile.md`), put it in a shared module and import it — don't
  copy-paste the parser into each executor.

### Parallelism — Run Independent Tasks Concurrently
- **Always look for parallelism.** When multiple executor calls, subagent tasks, or tool
  calls are independent of each other, run them in parallel (multiple tool calls in one
  message, or multiple background agents).
- **Pipeline stages that don't depend on each other should overlap.** For example, in
  /idea, all four data-gathering executors run in parallel before the analysis step.
- **Don't serialize what can be concurrent.** If you're about to run three independent
  searches or three independent executor calls, batch them — don't do them one by one.

### Context Engineering — Every Token Counts
You are a **context engineer**. Every token of context that isn't directly relevant to the
current task makes the response worse. Trim context to precisely what's needed.
- **Use ad-hoc markdown files** (`plan.md`, `notes.md`) as the primary way to persist
  working state. When doing codebase or internet research, write findings into a file.
  When starting a feature, write goals into a `plan.md` and flesh it out before executing.
  When executing, work through the plan you've already written — don't re-derive it.
- **Start fresh conversations often.** Bring new conversations up to speed by reading the
  relevant sections of your markdown files — not by relying on stale conversation history.
- **If context is important, write it down.** Do not trust conversation history to preserve
  critical information; make sure it lives in a markdown file (directive, orchestrator,
  plan, or notes).

### Data Format — Use the Right Format for the Consumer
- **TSV for LLM prompts**: When passing flat/tabular data to subagent prompts, convert to
  TSV (tab-separated, header row first). TSV eliminates repeated key names across rows
  (~50% fewer tokens than JSON arrays of objects). Use the `json_to_tsv` helper defined
  in orchestrators.
- **TOON for nested arrays in LLM prompts**: When passing uniform arrays with nesting
  (e.g., transcript segments, keep_segments) to subagent prompts, use TOON
  (Token-Oriented Object Notation). TOON provides TSV-like token savings (~40-50%)
  while supporting nested structures. Python: `import toon; toon.encode(data)`.
  Reserve for subagent prompts only — code-consumed files stay JSON.
- **JSON for code**: Executor stdout, state files, config files, and any data parsed by
  Python/JS stays JSON. Code needs reliable structure; token cost is irrelevant.
- **JSON for heterogeneous nested data**: Deeply nested structures with non-uniform shapes
  (graphics specs, brand briefs) stay JSON — TOON tabular format requires uniform keys.
- **Markdown for prose**: Research briefs, scripts, outlines stay markdown — not JSON
  with text fields.

## Agent Personas
For domain-specific sessions, load the relevant persona from `agents/`:
- `agents/video-editor.md` — for video editing sessions (cut + graphics pass)
- `agents/research-writer.md` — for research and script writing sessions
- `agents/thumbnail-designer.md` — for thumbnail design sessions
- `agents/idea-finder.md` — for topic discovery sessions
- `agents/content-analyst.md` — for content analysis and hook mining sessions

## Dependencies
- `ffmpeg` 6.0+ (brew install ffmpeg) — must include `arnndn` filter (default in Homebrew builds)
- `faster-whisper` (pip install faster-whisper) — for transcription (CTranslate2 backend, ~4x faster than openai-whisper)
- Python 3.9+
- `yt-dlp` (brew install yt-dlp) — for /write pipeline
- `python-docx` (pip install python-docx) — for Google Docs export in /write pipeline
- `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib` (pip install) — for Google Docs export in /write pipeline and Google Sheets export in /thumbnail pipeline (requires Google Sheets API enabled in GCP project)
- `Pillow` (pip install Pillow) — for thumbnail compositing and grid generation in /thumbnail pipeline
- `google-genai` (pip install google-genai) — for Gemini face replacement and image generation in /thumbnail pipeline
- `mediapipe` (pip install mediapipe) — for face pose detection in /thumbnail pipeline (headshot matching)
- `opencv-contrib-python` (pip install opencv-contrib-python) — required by mediapipe for PnP pose estimation
- `pytrends` (pip install pytrends) — for Google Trends data in /idea pipeline
- `curl_cffi` (pip install curl_cffi) — for X.com GraphQL API scraping in /idea pipeline (Chrome TLS impersonation)
- `XClientTransaction` (pip install XClientTransaction) — generates x-client-transaction-id header required by X.com API
- Node.js 18+ — for Remotion graphics pass rendering in /edit pipeline
- `remotion` (npm — in remotion/ subproject) — for programmatic video graphics rendering
- `playwright` (pip install playwright) — for screenshot capture in /edit graphics pass asset preparation (optional)
- `python-toon` (pip install python-toon) — for TOON encoding when passing nested arrays to subagent prompts (token-efficient alternative to JSON)

## Credentials
- `credentials.json` — Google OAuth2 client credentials file, lives at project root
- **Always reuse `credentials.json`** — when adding new API scopes or services, add them to the existing `credentials.json`. Never create separate credential files.
- Token cache: `~/.cache/youtube-assistant/` (e.g., `google_sheets_token.json`)
- Twitter cookies: `~/.cache/youtube-assistant/twitter_cookies.json`

## Error Handling Philosophy
1. Validate before executing — catch bad inputs before touching files
2. Never overwrite source files in workspace/input/
3. On executor failure: show full stderr output, then apply remediation from the directive
4. On ambiguity: ask the user — do not guess
5. If a workspace/temp/ file already exists from a previous run, overwrite it (it's ephemeral)
