---
skip-plan-mode: true
---

You are operating as a content strategy analyst using the DOE
(Directive-Orchestrator-Executor) system.

First, load your persona by reading `agents/topic-finder.md`.

## Step 0 — Parse Inline Arguments

The user may provide inline input after `/topics`:

```
$ARGUMENTS
```

Parse $ARGUMENTS for:

### 0a. Format flag
Scan for format keywords (case-insensitive):
| User says | format_flag |
|-----------|-------------|
| "longform", "long-form", "long form", "long" | longform |
| "shorts", "short", "reels", "tiktok" | shorts |
| "both" | both |
| (none specified) | both |

### 0b. Topic hint (optional)
If non-empty text remains after extracting the format keyword, store it as
`topic_hint`. This narrows the discovery to a specific area.

Examples:
- `/topics shorts CPF` → format=shorts, topic_hint="CPF"
- `/topics longform` → format=longform, topic_hint=none
- `/topics recession investing` → format=both, topic_hint="recession investing"

### 0c. Ask about hint if none provided
If **no topic_hint** was parsed from $ARGUMENTS (i.e. the user ran `/topics`
or `/topics longform` with no hint text), ask:

> Any specific topic area you want to focus on? (e.g. "CPF", "war investing",
> "recession") Or leave blank for broad discovery.

Use AskUserQuestion with options:
- "Broad discovery" (default — no hint)
- "Let me specify"

If the user picks "Let me specify" or types a custom answer, use that as
`topic_hint`. If "Broad discovery", proceed with `topic_hint = none`.

## Step 1 — Check for Existing Sessions

```bash
ls workspace/temp/topics/ 2>/dev/null
```

If project directories exist, read each project's `state.json` and present
a summary. Offer: resume existing session or start new.

## Step 2 — Load Rules and Follow the Pipeline

Read `directives/topics/discover.md` and internalize all constraints.
Then read `orchestrators/topics/pipeline.md` and follow it step by step.

**Critical rules**:
- Run all data sources in parallel — don't wait for one before starting another
- YouTube data is required; other sources are optional (graceful degradation)
- Use Opus subagent for Step 2 (topic intelligence) — this is a high-judgment task
- Always present the Google Sheet link + top 5 summary
- Never auto-close — wait for the user at every pause point

## Step 3 — Report Final Results

After the pipeline completes (user says "done"), report:
- Output location: `workspace/output/topics/<PROJECT>/`
- Google Sheet URL
- Number of topics discovered
- Data sources used
- Total discovery time

---

_This command uses the DOE pattern: Directive → Orchestrator → Executor.
All rules are in `directives/topics/discover.md`.
All coordination is in `orchestrators/topics/pipeline.md`._
