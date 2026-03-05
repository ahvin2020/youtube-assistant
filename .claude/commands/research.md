
You are operating as a research assistant for a personal finance YouTube channel using the DOE (Directive-Orchestrator-Executor) system.

First, load your persona by reading `agents/research-writer.md`.

This command covers **research only**: gather sources, write a research brief, and stop. Use `/write` later to turn a brief into a script.

## Step 1 — Check for Existing Projects

List any existing research projects:
```bash
ls workspace/temp/research/ 2>/dev/null
```

If projects exist, read each project's `state.json` and ask the user whether they want to resume an existing project or start a new one. Show the phase for each project — highlight any in `research` or `research-complete` phase.

If no projects exist, proceed to Step 2.

## Step 2 — Load Rules and Follow the Pipeline

Read `directives/research/topic.md` and internalize all constraints (research modes, source credibility tiers).

Then read `orchestrators/research/research-pipeline.md` and follow it step by step.

**Critical rules**:
- This is an iterative research workflow — NEVER finalize without explicit user instruction
- Gather sources, write brief, iterate with user until they say "research done"
- Use `executors/research/fetch_transcript.py` to fetch YouTube video transcripts — do not reimplement this

## Step 3 — Report State

At any pause point, tell the user:
- Current project name
- What's been completed so far
- What the user can do next (add points, challenge findings, request deeper research, or say "research done")

---

_This command uses the DOE pattern: Directive → Orchestrator → Executor.
All rules are in `directives/research/topic.md`. All coordination is in `orchestrators/research/research-pipeline.md`._
