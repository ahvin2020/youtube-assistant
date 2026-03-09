---
skip-plan-mode: true
---

You are operating as a video editing assistant using the DOE (Directive-Orchestrator-Executor) system.

First, load your persona by reading `agents/video-editor.md`.

## Step 0 — Parse Inline Arguments

The user may provide inline input after `/edit`:

```
$ARGUMENTS
```

Parse `$ARGUMENTS` for **three** things — script source, output mode, and video filename:

### 0a. Script source

1. **Contains a Google Doc URL** (matches `docs.google.com/document/d/`):
   Set `inline_script = "gdoc"` and store the URL. The script question will be skipped.

2. **Contains non-empty text** that is NOT a Google Doc URL and NOT an output-mode keyword:
   Set `inline_script = "text"` and store the text. The script question will be skipped.

3. **Empty / blank**:
   Set `inline_script = null`. The script question will be asked as usual.

### 0b. Output mode

Scan `$ARGUMENTS` (case-insensitive) for output-mode keywords:

| User says (examples)                          | `inline_output_mode` |
|-----------------------------------------------|----------------------|
| "1 file", "single file", "joined", "single"  | `joined`             |
| "project", "xml", "premiere"                  | `project`            |
| "both"                                        | `both`               |
| _(none of the above)_                         | `null`               |

If a keyword is found, set `inline_output_mode` accordingly. The output-mode question will be skipped.

### 0c. Video filename

If `$ARGUMENTS` contains a recognizable video filename (e.g. `IMG_0206.mov`, `clip.mp4`),
store it as `inline_video`. This will be matched against files in `workspace/input/video/`
and `workspace/output/video/` (case-insensitive, searched recursively) in Step 1.

## Step 1 — Identify the Source Video

Find video files in `workspace/input/video/` and `workspace/output/video/`:
```bash
find workspace/input/video/ workspace/output/video/ -type f \( -iname "*.mov" -o -iname "*.mp4" -o -iname "*.mkv" -o -iname "*.avi" \) 2>/dev/null
```

This searches recursively — files may be at the root or inside dated project folders.

**If `inline_video` is set**: match it (case-insensitive) against the listing. If a match is
found, use that file silently — no confirmation needed. If no match, tell the user and ask
which file to use.

**If `inline_video` is null**:
- If only one file is present, confirm with the user: **"I found [filename] — is this the file you want to edit?"**
- If multiple files are present, ask the user: **"Which video file would you like to edit?"**

## Step 1.1 — Derive Project Name

After identifying the source video, derive the `PROJECT` name:

1. **STEM** = source filename without extension (e.g. `IMG_0206` from `IMG_0206.mov`)
2. **DATE** = today's date as `YYYYMMDD` (e.g. `20260303`)
3. **If the video is inside a dated folder** (parent folder matches `YYYYMMDD_*`):
   use that folder name as `PROJECT` (e.g. `20260302_cpf-frs-vs-ers`)
4. **Otherwise**: `PROJECT` = `<DATE>_<STEM>` (e.g. `20260303_IMG_0206`). After the
   script is loaded (Step 1.5), if a clearer topic slug can be derived from the script
   content, rename to `<DATE>_<slug>` (e.g. `20260303_cpf-frs-vs-ers`).

Create the project directories immediately:
```bash
mkdir -p "workspace/temp/video/<PROJECT>"
mkdir -p "workspace/output/video/<PROJECT>"
```

## Step 1.2 — Determine Starting Phase

Ask the user which phase to start from:

**Question** (`multiSelect: false`):
- **Raw video (full edit)** — Start from scratch: cut retakes first, then add graphics
- **Already cut (graphics pass only)** — Video is already trimmed, skip straight to graphics pass

If "Raw video": set `start_phase = "cut"`.
If "Already cut": set `start_phase = "graphics"`.

## Step 1.5 — Script & Output Mode

Determine which questions still need answers based on what was parsed in Step 0.

### Auto-detect script from /write pipeline

Before building the question list, check for completed research projects:

```bash
ls workspace/temp/research/*/state.json 2>/dev/null
```

For each `state.json` where `phase` is `"complete"`:
- Check if `workspace/output/research/<PROJECT>/script.md` exists
- Read the `topic` field from `state.json`
- Derive `content_slug` (from `content_slug` field, or strip `YYYYMMDD_` prefix)

Store these as `available_scripts` (list of `{project, topic, script_path, content_slug}`).

If `available_scripts` is non-empty AND `inline_script` is null:
- Add these as options in the script question below (one per completed script)
- Format: **"Use script: '<topic>'"** (from /write pipeline)

If the user selects a /write script:
- Read the `script.md` file and save it to `workspace/temp/video/<PROJECT>/script.txt`
- Set `script_mode = true`
- Inherit the `content_slug` from the research project

### Questions to ask

Build the question list based on what's missing:

**Output mode question** (skip if `inline_output_mode` is set or `start_phase = "graphics"`):
- **Video project** — Individual clips + an XML project file you can import into Premiere Pro
- **Single joined file** — All kept segments concatenated into one video file
- **Both** — Joined file + video project (single efficient extraction)

**Script question** (skip if `inline_script` is set):
- **Google Doc link** — I have a link to my script
- **Paste script text** — I'll paste my script directly
- **No script** — Detect retakes automatically (no script needed) _(only show this option if `start_phase = "cut"`)_

Ask all needed questions in a single `AskUserQuestion` call.

### Handle script input

**If `inline_script = "gdoc"` OR user selected "Google Doc link"**:

If the URL was provided inline, use it directly. Otherwise ask the user for the URL. Then:
1. Extract the document ID from the URL (the string between `/d/` and the next `/`).
2. Fetch the plain-text export:
   ```bash
   curl -sL "https://docs.google.com/document/d/<ID>/export?format=txt" -o "workspace/temp/video/<PROJECT>/script.txt"
   ```
3. Verify the file was fetched successfully — read the first few lines. If the file is
   empty or contains HTML (e.g. `<!DOCTYPE` or `<html`), tell the user:
   **"The document couldn't be fetched — it may not be publicly shared. Please either
   set sharing to 'Anyone with the link -> Viewer' or paste the script text directly."**
   Then re-ask the script question only.
4. On success, set `script_mode = true`.

**If `inline_script = "text"` OR user selected "Paste script text"**:

If the text was provided inline, save it directly to `workspace/temp/video/<PROJECT>/script.txt`
using the Write file tool — no need to ask the user to paste again.

Otherwise, wait for the user to paste their script. Once received, save it to
`workspace/temp/video/<PROJECT>/script.txt` using the Write file tool.

Set `script_mode = true`.

**If "No script"** (only possible when `start_phase = "cut"`):
Set `script_mode = false`. The pipeline will use retake-only detection.

### Confirmation (when script is provided):
Report: **"Script loaded ([N] words). Starting [phase description]."**

## Step 2 — Load Rules and Follow the Pipeline

Language is always English (`en`).

Read `directives/video/edit.md` and internalize all constraints.

Then read `orchestrators/video/edit.md` and follow it step by step, starting from the
appropriate phase based on `start_phase`.

Do not skip steps. The cut phase runs in **auto-accept mode** — do not pause for confirmations
on the cut plan. The graphics pass phase pauses for user review of the enhancement plan.

## Step 3 — Report Final Results

After each phase completes, report results:

### After Cut Phase:
- Duration before and after (time saved)
- Number of retakes removed
- Script sections matched vs unmatched (script-guided mode)
- Output file path

### After Graphics Pass:
- Number of enhancements created, grouped by type
- Sections covered
- Editor URL (if preview server is running)
- Output file path (if rendered)

## Step 4 — Resume Support

When the command starts, check for existing projects:
```bash
ls workspace/temp/video/*/state.json 2>/dev/null
```

If a project exists at phase "graphics" (cut already completed), offer to resume:

**Question** (`multiSelect: false`):
- **Resume <PROJECT>** — Continue from graphics pass (cut phase already done)
- **Start new project** — Begin a fresh edit

If resuming, load the state.json and skip to the graphics pass phase.

---

_This command uses the DOE pattern: Directive -> Orchestrator -> Executor.
All rules are in `directives/video/edit.md`. All coordination is in `orchestrators/video/edit.md`._
