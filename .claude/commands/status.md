---
skip-plan-mode: true
---

You are showing the user their content production pipeline status.

## Step 0 — Parse Arguments

```
$ARGUMENTS
```

If `$ARGUMENTS` contains text, store it as `filter_query` (used to filter projects).
If empty, show all projects.

## Step 1 — Scan All Domains

Find all state.json files across all pipeline domains:

```bash
ls workspace/temp/ideas/*/state.json workspace/temp/research/*/state.json workspace/temp/video/*/state.json workspace/temp/thumbnail/*/state.json 2>/dev/null
```

Read each `state.json`. For each project, extract:
- **domain**: derived from the path (`ideas`, `research`, `video`, `thumbnail`)
- **project_slug**: the folder name (e.g., `20260306_ai-stock-picks`)
- **content_slug**: the `content_slug` field if present, otherwise strip the `YYYYMMDD_` prefix from the folder name
- **phase**: the `phase` field
- **topic**: the `topic` field (if present) or humanize the content_slug
- **format**: the `format` field (if present)

Also check for output files:
```bash
ls workspace/output/ideas/ workspace/output/research/ workspace/output/video/ workspace/output/thumbnail/ 2>/dev/null
```

## Step 2 — Group by Content Slug

Group all projects that share the same `content_slug` into **content projects**.

A content project represents a single video idea flowing through the production pipeline.

Map domains to pipeline stages:
- `ideas` → /idea stage
- `research` → /write stage
- `video` → /edit stage
- `thumbnail` → /thumbnail stage

If multiple projects in the same domain share a `content_slug`, use the most recently
updated one.

If `filter_query` is set, filter to content projects whose `content_slug` or `topic`
contains the filter text (case-insensitive).

## Step 3 — Display Pipeline Grid

For each content project, display:

```
"<Topic>" (<content_slug>)
───────────────────────────────────
/idea        DONE       30 ideas, sheet exported
/write       OUTLINE    long-form, strategy comparison
/edit        —          not started
/thumbnail   —          not started
```

**Stage status rules**:
- If no project exists for that domain: show `—` and "not started"
- If `phase` is `"complete"`: show `DONE` with a brief summary
- Otherwise: show the phase name in CAPS with relevant context

**Summary line per stage** (what to show):
- `/idea`: number of topics discovered + whether sheet was exported
- `/write`: format + research mode (or current phase details)
- `/edit`: which phase (cut/graphics) + output mode
- `/thumbnail`: iteration count + current phase

Sort content projects by most recently updated first.

## Step 4 — Suggest Next Actions

For each content project, suggest the logical next step:

| Current State | Suggestion |
|---|---|
| /idea DONE, /write not started | "Run `/write` to start scripting this idea" |
| /write DONE, /edit not started | "Run `/edit` once you've recorded the video" |
| /write at outline+, /thumbnail not started | "Run `/thumbnail` to start thumbnail design" |
| /edit DONE + /thumbnail DONE, /post not started | "Ready to publish — run `/post`" |
| All stages DONE | "Complete!" |

Present suggestions after each content project's grid.

## Step 5 — Summary

At the bottom, show:
- Total content projects found
- How many are in progress vs complete
- If no projects found: "No projects found. Run `/idea` to start discovering content ideas."
