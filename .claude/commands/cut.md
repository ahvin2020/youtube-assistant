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

Evaluate `$ARGUMENTS`:

1. **Contains a Google Doc URL** (matches `docs.google.com/document/d/`):
   Set `inline_script = "gdoc"` and store the URL. The script question will be skipped.

2. **Contains non-empty text** that is NOT a Google Doc URL:
   Set `inline_script = "text"` and store the text. The script question will be skipped.

3. **Empty / blank**:
   Set `inline_script = null`. The script question will be asked as usual.

## Step 1 — Identify the Source Video

List the files currently in `workspace/input/` using the Bash tool:
```bash
ls workspace/input/
```

If only one file is present, confirm with the user: **"I found [filename] — is this the file you want to trim?"**

If multiple files are present, ask the user: **"Which video file would you like to trim?"**

## Step 1.5 — Script, Output Mode & Audio Cleanup

### If `inline_script` is set — ask only output mode and audio cleanup

The script was already provided inline, so skip the script question. Ask **two questions** in a single `AskUserQuestion` call:

**Question 1 — Output mode** (`multiSelect: false`):
- **Video project** — Individual clips + an XML project file you can import into Premiere Pro
- **Single joined file** — All kept segments concatenated into one video file
- **Both** — Joined file + video project (single efficient extraction)

**Question 2 — Clean audio** (`multiSelect: false`):
- **Yes (voice preset)** — Clean audio before editing (recommended for raw recordings with room reverb or uneven levels)
- **No** — Skip audio cleanup, use the raw audio as-is

### If `inline_script` is null — ask all three questions

Ask the user **all three questions together** in a single `AskUserQuestion` call:

**Question 1 — Output mode** (`multiSelect: false`):
- **Video project** — Individual clips + an XML project file you can import into Premiere Pro
- **Single joined file** — All kept segments concatenated into one video file
- **Both** — Joined file + video project (single efficient extraction)

**Question 2 — Clean audio** (`multiSelect: false`):
- **Yes (voice preset)** — Clean audio before editing (recommended for raw recordings with room reverb or uneven levels)
- **No** — Skip audio cleanup, use the raw audio as-is

**Question 3 — Script** (`multiSelect: false`):
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
   curl -sL "https://docs.google.com/document/d/<ID>/export?format=txt" -o "workspace/temp/<STEM>/script.txt"
   ```
3. Verify the file was fetched successfully — read the first few lines. If the file is
   empty or contains HTML (e.g. `<!DOCTYPE` or `<html`), tell the user:
   **"The document couldn't be fetched — it may not be publicly shared. Please either
   set sharing to 'Anyone with the link → Viewer' or paste the script text directly."**
   Then re-ask the script question only.
4. On success, set `script_mode = true`.

**If `inline_script = "text"` OR user selected "Paste script text"**:

If the text was provided inline, save it directly to `workspace/temp/<STEM>/script.txt`
using the Write file tool — no need to ask the user to paste again.

Otherwise, wait for the user to paste their script. Once received, save it to
`workspace/temp/<STEM>/script.txt` using the Write file tool.

Set `script_mode = true`.

**If "No script"** (only possible when `inline_script` is null):
Set `script_mode = false`. The pipeline will use retake-only detection.

### Confirmation (when script is provided):
Report: **"Script loaded ([N] words). I'll use this to guide the edit — keeping only
content that matches your script."**

Pass `script_mode` to the orchestrator — it controls which analysis path Step 2 follows.

In Step 4, the executor runs once regardless of mode selection.

The audio cleanup preference is passed to the orchestrator's Step 0 — do not ask again.

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
