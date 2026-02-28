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
workspace/output/                ← All output files land here
```

## Your Role
- READ directives — do not improvise rules not defined there
- FOLLOW orchestrators — do not skip steps or reorder them
- CALL executors — do not reimplement executor logic yourself
- REPORT results clearly — always tell the user what was done and where output lives

## File Map

| Domain         | Directive                          | Orchestrator                           | Executor(s)                                    |
|----------------|------------------------------------|----------------------------------------|------------------------------------------------|
| Video cut      | directives/video/auto-edit.md      | orchestrators/video/auto-edit.md       | executors/video/transcribe.py, apply_cuts.py   |
| Research       | directives/research/topic.md       | orchestrators/research/pipeline.md     | executors/research/fetch_transcript.py         |
| Thumbnail      | directives/thumbnail/generate.md   | orchestrators/thumbnail/generate.md    | executors/thumbnail/generate_thumbnail.py      |
| Publishing     | directives/publishing/post.md      | orchestrators/publishing/pipeline.md   | executors/publishing/upload_video.py           |

_(Research, Thumbnail, Publishing are stubs — not yet implemented)_

## Workspace Convention
| Directory          | Purpose                                      |
|--------------------|----------------------------------------------|
| workspace/input/   | Drop source media files here before editing  |
| workspace/output/  | All processed/final files land here          |
| workspace/temp/    | Transcripts, cut specs, intermediate clips   |

Temp files can be cleared after a pipeline completes. Never delete input/ or output/ contents without confirming with the user.

## Executor Contract
- All executors print **JSON to stdout**
- All executors exit **0 on success, 1 on failure**
- All executors are **runnable standalone**: `python executors/<domain>/<script>.py --help`
- Never reimplement what an executor does — call the script via the Bash tool

## Agent Personas
For domain-specific sessions, load the relevant persona from `agents/`:
- `agents/video-editor.md` — for video editing sessions

## Error Handling Philosophy
1. Validate before executing — catch bad inputs before touching files
2. Never overwrite source files in workspace/input/
3. On executor failure: show full stderr output, then apply remediation from the directive
4. On ambiguity: ask the user — do not guess
5. If a workspace/temp/ file already exists from a previous run, overwrite it (it's ephemeral)
