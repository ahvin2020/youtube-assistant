---
skip-plan-mode: true
---

You are operating as a content performance analyst using the DOE
(Directive-Orchestrator-Executor) system.

First, load your persona by reading `agents/content-analyst.md`.

## Step 0 — Parse Inline Arguments

The user may provide inline input after `/analyze`:

```
$ARGUMENTS
```

Parse $ARGUMENTS for:

### 0a. Mode detection
| User says | Mode |
|-----------|------|
| A YouTube URL (contains youtube.com or youtu.be) | `deep-dive` — analyze that specific video |
| "no transcripts" | `no-transcripts` — skip transcript fetching (faster, title hooks only) |
| (nothing or general text) | `full` — full analysis pipeline |

### 0b. Examples
- `/analyze` → mode=full
- `/analyze https://youtube.com/watch?v=abc123` → mode=deep-dive, video_url=abc123
- `/analyze no transcripts` → mode=no-transcripts

## Step 1 — Check for Existing Sessions

```bash
ls workspace/temp/analyze/ 2>/dev/null
```

If project directories exist, read each project's `state.json` and present
a summary. Offer: resume existing session or start new.

## Step 2 — Load Rules and Follow the Pipeline

Read `directives/analyze/content-analysis.md` and internalize all constraints.
Then read `orchestrators/analyze/pipeline.md` and follow it step by step.

**Critical rules**:
- Fetch transcripts in parallel — don't wait for one before starting another
- Use Opus subagent for hook extraction (high-judgment task)
- Always update hooks.json (merge, never overwrite)
- Track analyzed video IDs to avoid re-processing on subsequent runs
- Present summary + wait for user at every pause point

## Step 3 — Report Final Results

After the pipeline completes (user says "done"), report:
- Output location: `workspace/output/analyze/<PROJECT>/`
- Google Sheet URL
- Hook database stats (total hooks, new this run, pruned)
- Data sources analyzed
- Total analysis time

---

_This command uses the DOE pattern: Directive → Orchestrator → Executor.
All rules are in `directives/analyze/content-analysis.md`.
All coordination is in `orchestrators/analyze/pipeline.md`._
