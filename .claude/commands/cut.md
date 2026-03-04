---
skip-plan-mode: true
---

You are operating as a video editing assistant using the DOE (Directive-Orchestrator-Executor) system.

First, load your persona by reading `agents/video-editor.md`.

## Step 0 — Parse Inline Arguments

The user may provide inline input after `/cut`:

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
(case-insensitive, searched recursively) in Step 1, skipping the file selection question.

## Step 1 — Identify the Source Video

Find video files in `workspace/input/video/` using the Bash tool:
```bash
find workspace/input/video/ -type f \( -iname "*.mov" -o -iname "*.mp4" -o -iname "*.mkv" -o -iname "*.avi" \) 2>/dev/null
```

This searches recursively — files may be at the root or inside dated project folders
(e.g. `workspace/input/video/20260302_cpf-frs-vs-ers/IMG_0206.mov`).

**If `inline_video` is set**: match it (case-insensitive) against the listing. If a match is
found, use that file silently — no confirmation needed. If no match, tell the user and ask
which file to use.

**If `inline_video` is null**:
- If only one file is present, confirm with the user: **"I found [filename] — is this the file you want to trim?"**
- If multiple files are present, ask the user: **"Which video file would you like to trim?"**

## Step 1.1 — Derive Project Name

After identifying the source video, derive the `PROJECT` name:

1. **STEM** = source filename without extension (e.g. `IMG_0206` from `IMG_0206.mov`)
2. **DATE** = today's date as `YYYYMMDD` (e.g. `20260303`)
3. **If the video is inside a dated folder** (parent folder matches `YYYYMMDD_*`):
   use that folder name as `PROJECT` (e.g. `20260302_cpf-frs-vs-ers`)
4. **Otherwise**: `PROJECT` = `<DATE>_<STEM>` (e.g. `20260303_IMG_0206`). After the
   script is loaded (Step 1.5), if a clearer topic slug can be derived from the script
   content, rename to `<DATE>_<slug>` (e.g. `20260303_cpf-frs-vs-ers`).

Create the project temp directory immediately:
```bash
mkdir -p "workspace/temp/video/<PROJECT>"
mkdir -p "workspace/output/video/<PROJECT>"
```

## Step 1.5 — Script & Output Mode

Determine which questions still need answers based on what was parsed in Step 0.

### If BOTH `inline_script` AND `inline_output_mode` are set

Everything is known — skip straight to handling script input below. No questions needed.

### If `inline_script` is set but `inline_output_mode` is null

Ask **one question** — output mode only:

**Question 1 — Output mode** (`multiSelect: false`):
- **Video project** — Individual clips + an XML project file you can import into Premiere Pro
- **Single joined file** — All kept segments concatenated into one video file
- **Both** — Joined file + video project (single efficient extraction)

### If `inline_output_mode` is set but `inline_script` is null

Ask **one question** — script source only:

**Question 1 — Script** (`multiSelect: false`):
- **Google Doc link** — I have a link to my script
- **Paste script text** — I'll paste my script directly
- **No script** — Detect retakes automatically (no script needed)

### If BOTH are null

Ask **both questions together** in a single `AskUserQuestion` call:

**Question 1 — Output mode** (`multiSelect: false`):
- **Video project** — Individual clips + an XML project file you can import into Premiere Pro
- **Single joined file** — All kept segments concatenated into one video file
- **Both** — Joined file + video project (single efficient extraction)

**Question 2 — Script** (`multiSelect: false`):
- **Google Doc link** — I have a link to my script
- **Paste script text** — I'll paste my script directly
- **No script** — Detect retakes automatically (no script needed)

### Handle script input

**If `inline_script = "gdoc"` OR user selected "Google Doc link"**:

If the URL was provided inline, use it directly. Otherwise ask the user for the URL. Then:
1. Extract the document ID from the URL. Google Doc URLs follow these patterns:
   - `https://docs.google.com/document/d/<ID>/edit`
   - `https://docs.google.com/document/d/<ID>/`
   Extract the `<ID>` portion (the string between `/d/` and the next `/`).
2. Fetch the plain-text export:
   ```bash
   curl -sL "https://docs.google.com/document/d/<ID>/export?format=txt" -o "workspace/temp/video/<PROJECT>/script.txt"
   ```
3. Verify the file was fetched successfully — read the first few lines. If the file is
   empty or contains HTML (e.g. `<!DOCTYPE` or `<html`), tell the user:
   **"The document couldn't be fetched — it may not be publicly shared. Please either
   set sharing to 'Anyone with the link → Viewer' or paste the script text directly."**
   Then re-ask the script question only.
4. On success, set `script_mode = true`.

**If `inline_script = "text"` OR user selected "Paste script text"**:

If the text was provided inline, save it directly to `workspace/temp/video/<PROJECT>/script.txt`
using the Write file tool — no need to ask the user to paste again.

Otherwise, wait for the user to paste their script. Once received, save it to
`workspace/temp/video/<PROJECT>/script.txt` using the Write file tool.

Set `script_mode = true`.

**If "No script"** (only possible when `inline_script` is null):
Set `script_mode = false`. The pipeline will use retake-only detection.

### Confirmation (when script is provided):
Report: **"Script loaded ([N] words). I'll use this to guide the edit — keeping only
content that matches your script."**

Pass `script_mode` to the orchestrator — it controls which analysis path Step 2 follows.

In Step 4, the executor runs once regardless of mode selection.

## Step 2 — Load Rules and Follow the Pipeline

Language is always English (`en`).

Read `directives/video/auto-edit.md` and internalize all constraints.

Then read `orchestrators/video/auto-edit.md` and follow it step by step.

Do not skip steps. This pipeline runs in **auto-accept mode** — do not pause for confirmations. Show the cut plan for informational purposes, then proceed to apply cuts immediately.

## Step 3 — Report Final Results

After the pipeline completes, report based on the output mode:

**All modes:**
- Duration before and after (time saved)
- Number of retakes removed
- Any warnings or segments flagged for manual review

**Script-guided mode (additional):**
- Script sections matched vs unmatched (e.g. "8/10 sections matched")
- List any unmatched script sections by first few words
- Amount of off-script content removed

**Joined mode:** Report the single output file path and size.

**Project mode:** List each clip file path, plus the XML project file path.
Remind the user: _"Import the .xml file in Premiere Pro via File → Import."_

---

_This command uses the DOE pattern: Directive → Orchestrator → Executor.
All rules are in `directives/video/auto-edit.md`. All coordination is in `orchestrators/video/auto-edit.md`._
