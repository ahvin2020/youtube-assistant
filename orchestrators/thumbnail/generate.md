# Orchestrator: Thumbnail Generation Pipeline

This orchestrator coordinates a multi-phase, iterative thumbnail design
workflow. Like the research pipeline, this pipeline **pauses for user input
at key checkpoints** and supports iterative refinement.

Follow every step in order. Do not skip steps.

---

## Pre-Flight Checklist

Before starting, verify:

- [ ] List `workspace/input/thumbnail/headshots/` — report available emotions (warn if empty)
- [ ] Derive `SLUG` = URL-safe lowercase version of the topic (spaces → hyphens, strip special chars)
- [ ] Derive `PROJECT` = `YYYYMMDD_<SLUG>` using today's date (e.g. `20260303_cpf-frs-vs-ers`)
- [ ] Create temp directories:
      ```bash
      mkdir -p workspace/temp/thumbnail/<PROJECT>/{research,face_replaced,assets}
      ```
- [ ] Create output directory:
      ```bash
      mkdir -p workspace/output/thumbnail/<PROJECT>
      ```
- [ ] Check for Gemini API key: read `credentials.json` and check for `gemini_api_key`,
      or check `$GEMINI_API_KEY` env var. If neither is set, stop and tell the user:
      "Set your Gemini API key in one of:
        1. `credentials.json` → add `\"gemini_api_key\": \"your_key\"`
        2. Environment variable → `export GEMINI_API_KEY=your_key`
      Get a key at https://aistudio.google.com/apikey"

Write initial state:
```bash
cat > workspace/temp/thumbnail/<PROJECT>/state.json << 'EOF'
{
  "topic": "<user's topic>",
  "slug": "<SLUG>",
  "phase": "research",
  "iteration": 0,
  "selected_concept": null,
  "concepts": [],
  "created": "<YYYY-MM-DD>",
  "updated": "<YYYY-MM-DD>"
}
EOF
```

---

## Step 1 — Report Headshots

Report:
```
Headshots available: <list of emotion names>
```

Style will be derived from competitive research — colors, fonts, and visual
approach will be based on what top-performing thumbnails in this space actually
use, with deliberate differentiation. All style decisions are deferred to
Step 3 (strategy session), after research is complete.

If no headshots: "No headshots found. Will generate background-only thumbnails."

---

## Step 1b — Channel Profile Check

Follow `directives/shared/channel-profile.md` to check/build the channel profile.
The thumbnail pipeline needs the **Niche Terms** section (for cross-niche filtering).

---

## Step 2 — Competitive Research (Claude Intelligence Step)

### 2a. Load Channel Identity

Extract `channel_id` from `memory/channel-profile.md` (Identity → Channel ID)
for the `--exclude-channel` flag.

No manual query generation needed — cross-niche research uses config-driven
keyword search + monitored channel scanning.

### 2b. Run Cross-Niche Research

Run a single `cross_niche_research.py` call that searches **two sources**:
keyword search (curated cross-niche keywords) and channel monitoring (recent
videos from monitored channels). Both are merged, filtered, scored (outlier +
recency + hook modifiers), and ranked — all in one step.

**Timing**: Record a wall-clock start time (via `date +%s`) before launching
the search. After the full research phase completes, record the end time and
compute elapsed time. Report it in `Xm Ys` format (e.g., `3m 42s`).

```bash
python3 executors/thumbnail/cross_niche_research.py \
  "workspace/temp/thumbnail/<PROJECT>/research/cross_niche/" \
  --config workspace/config/cross_niche.json \
  --max-keywords 6 --max-channels 8 --count 100 \
  --min-outlier 1.5 \
  --exclude-channel <channel_id> \
```

The executor now calculates the **full final score** internally:
1. `outlier_score` = views / channel average views
2. `recency_multiplier` = time-based boost (1.15× for ≤30 days, etc.)
3. `base_score` = outlier × recency
4. Hook modifiers (title keyword matching against `hook_categories` in config)
5. `final_score` = base_score × (1 + sum of modifiers)

Results are sorted by `final_score` descending, top 100 kept.

On success: report how many thumbnails were downloaded, how many were
filtered out (own niche, format, outlier threshold), keywords searched,
and channels scanned.

On failure:
  - `yt-dlp` not found → tell user: `brew install yt-dlp`
  - All filtered out → try more keywords (`--max-keywords 10`) or lower
    outlier threshold (`--min-outlier 1.0`)
  - No results → note this, proceed without research

### 2c. AI Analysis (Claude Intelligence Step)

For each video in the research results, generate 3 adapted title variants.
This is done by Claude (you) directly — no external API calls needed.

**Process:**
1. Read `metadata.json` to get the video list
2. **Pre-bundle transcripts into batch files** — for each batch of ~10 videos,
   read all transcript files (first 4000 chars) and embed the text directly into
   the batch JSON. This way each subagent needs only 1 Read call instead of 11.
   Save batch files to `batch_0.json`, `batch_1.json`, etc. in the research dir.
3. Launch **parallel subagents** (batches of ~10 videos each, using **Sonnet** model).
   Pass each subagent its batch file path. Each subagent reads one file and generates:
   - **Title variants**: 3 titles adapted to the user's topic, inspired by the
     reference title's hook structure
4. Merge results and save to `analysis.json`:
   ```
   workspace/temp/thumbnail/<PROJECT>/research/cross_niche/analysis.json
   ```

Each entry in `analysis.json`:
```json
{
  "video_id": "abc123",
  "category": "Business",
  "title_variant_1": "...",
  "title_variant_2": "...",
  "title_variant_3": "..."
}
```

Category is auto-classified from the title: Money, Productivity, Creator,
Business, or General. No Claude call needed for this.

On failure: if a subagent fails for some videos, proceed with available data.
Missing analyses will show as empty cells in the Sheet.

### 2d. Export to Google Sheet

Export the scored results + AI analysis to a Google Sheet. Each run creates
a new tab in the same reusable spreadsheet.

```bash
python3 executors/thumbnail/export_research_sheet.py \
  --input "workspace/temp/thumbnail/<PROJECT>/research/cross_niche/metadata.json" \
  --analysis "workspace/temp/thumbnail/<PROJECT>/research/cross_niche/analysis.json" \
  --tab-name "<PROJECT>" \
  --credentials credentials.json \
  --sheet-config workspace/config/research_sheet.json
```

The Sheet has 18 columns: Thumbnail, Thumbnail URL, Title, Final Score,
Outlier Score, Days Old, Video Link, View Count, Duration (min), Channel Name,
Channel Avg Views, Category, Title Variant 1-3, Raw Transcript,
Publish Date, Source.

On success: report the Sheet URL to the user.
On failure:
  - Google Sheets API not enabled → tell user to enable it in GCP console
  - No credentials.json → tell user to set up OAuth credentials
  - First run will open a browser for OAuth consent (token cached afterward)

### 2e. Present Research Summary

Show a brief summary alongside the Sheet link:
```
RESEARCH COMPLETE:
  Research: cross-niche (X keywords + Y channels)
  Research time: Xm Ys
  Videos scanned: X → filtered to Y outliers → top 100 scored
  Sheet: <Google Sheet URL>

  Browse the sheet to review thumbnails, scores, and video links.
  Pick 5 reference thumbnails by row number (or video link) when ready.
```

Update `state.json`: set `phase` to `"selection"`.

**⏸ STOP and wait for the user.**

| User says               | Action                                    |
|-------------------------|-------------------------------------------|
| Picks references        | Proceed to Step 3                         |
| "Search for X instead"  | Re-run research with different query       |
| "Skip research"         | Proceed to Step 3 without research         |

---

## Step 3 — Reference Selection (User Choice Point)

### 3a. User Selects References from Sheet

The user browses the Google Sheet (from Step 2c) and picks 5 reference
thumbnails by row number or video link. They may also provide the
thumbnail link from the Sheet.

Map each selection back to the local thumbnail file in
`workspace/temp/thumbnail/<PROJECT>/research/cross_niche/` using the
video ID extracted from the link or the row number from metadata.json.

List available headshots: all files in `workspace/input/thumbnail/headshots/`

### 3b. Wait for User Selection

Wait for the user to pick 5 references.

### 3c. Auto-Suggest Headshot + Text

For each selected reference, run `match_headshot.py` to find the best
pose match, then suggest text based on the reference + topic:

```bash
# Run all 5 in parallel
/opt/homebrew/bin/python3 executors/thumbnail/match_headshot.py \
    --reference "<reference_thumbnail_path>" \
    --headshots-dir "workspace/input/thumbnail/headshots/" \
    --top-k 3
```

The top-1 result becomes the **primary headshot** (best pose match for
the concept). Additionally, select **2-4 extra headshots** from different
emotion categories to provide Gemini with multiple angles/expressions
of the same person. Pick extras that show variety (e.g. if primary is
`frustrated_12.JPG`, extras could be `confident_3.JPG`, `curious_2.JPG`,
`serious_1.JPG`). Store both `headshot` (primary) and `extra_headshots`
(list) in `state.json`.

For each reference, present:
```
REFERENCE SUGGESTIONS:

  A (ref #3 — "How I retired early"):
    Headshot: worried.JPG (best pose match, distance: 12.3)
    Extra refs: confident_3.JPG, curious_2.JPG, serious_1.JPG
    Text: "WRONG MOVE?" at top-left
    Why: Reference uses fear framing; worried face matches the pose angle

  B (ref #7 — "$500K in 5 years"):
    Headshot: excited.JPG (best pose match, distance: 8.1)
    Extra refs: frustrated_12.JPG, mindblown_11.JPG, serious_2.JPG
    Text: "$XX,000 MORE" at top-left
    Why: Reference uses data callout; excited matches the positive framing

  ...
```

**⏸ STOP and wait for user approval/edits.**

| User says                    | Action                              |
|------------------------------|-------------------------------------|
| Approves all                 | Proceed to Step 3d                  |
| "Use scared for A"           | Update headshot for A, re-present   |
| "Change B text to X"         | Update text for B                   |
| "Pick different references"  | Loop back to 3a                     |

### 3d. Prompt Engineering (Claude Intelligence Step)

After user approves headshot + text, reverse-engineer each reference thumbnail
into a detailed Gemini prompt. This runs automatically — no executor script,
Claude does it directly using vision. Use **Opus** model (`model: "opus"`) for the
prompt engineering subagents — reverse-engineering visual composition requires
strong analytical reasoning.

For each of the 5 selected references:

1. Read the reference thumbnail image using the Read tool (vision)
2. Read the selected headshot image using the Read tool (vision)
3. Analyze the visual composition in detail
4. Generate a Gemini prompt string covering:
   - **Subject (character consistency approach)**: Use "Subject Alpha" framing
     to maintain character consistency. Multiple headshot reference photos (3-5)
     are passed as inline images after the scene reference. Describe Subject
     Alpha's actual appearance from the headshots (glasses, clothing, build,
     hair) so Gemini preserves it faithfully.
     Example: "The first image is a scene/layout reference. The remaining images
     are all reference photos of the same person called Subject Alpha, showing
     them from different angles and expressions. Generate a high-quality image
     of Subject Alpha in this scene. He is a slim Asian man wearing rectangular
     silver-framed glasses and a dark navy t-shirt. Maintain strict facial and
     physical consistency with the provided reference photos of Subject Alpha."
     **IMPORTANT**: Never use terms like "face swap", "replace the face",
     "edit the person", or "replace the person". Always use generative language:
     "generate an image of Subject Alpha", "Subject Alpha is shown doing X".
   - **Pose & Action**: Describe the desired pose from the reference (hands open,
     pointing, etc.) as actions Subject Alpha is performing
   - **Camera Settings**: Focal length, angle, depth of field
   - **Lighting Environment**: Light sources, color temperature, techniques
   - **Composition**: Subject placement, background elements, negative space
   - **Aesthetic & Rendering**: Visual style, color grading, dominant colors
   - **Text**: "Include the text '[TEXT]' prominently in the [POSITION] area.
     [Style instructions derived from reference's text treatment]."
   - **Constraints**: "Do NOT include any watermarks. 16:9 wide landscape framing."

   **Key principle**: Use character consistency framing — describe generating
   a new image *of* Subject Alpha (from the reference photos), not editing or
   swapping. This avoids safety filter rejections and produces better results.

4. Present prompt summary:
```
PROMPT SUMMARY:

  A (ref #3 — "How I Made $1M in 5 Years"):
    Prompt: Dramatic rim lighting, centered face, dark moody background...

  B (ref #7 — "$500K Portfolio at 30"):
    Prompt: Bright studio setup, rule-of-thirds, clean background...

  ...
```

Note: Title variants are pre-generated during the research phase (Step 2c)
and visible in the Google Sheet. No need to generate them here.

### 3e. Save Selections + Prompts

Save to `state.json`:
```json
{
  "phase": "generation",
  "selected_references": [
    {"ref_number": 3, "ref_path": "...", "headshot": "worried.JPG",
     "extra_headshots": ["confident_3.JPG", "curious_2.JPG", "serious_1.JPG"],
     "text": "WRONG MOVE?", "text_position": "top-left",
     "prompt": "<full reverse-engineered prompt>"},
    ...
  ]
}
```

---

## Step 4 — Face Replacement (Parallel)

### 4a. Model Selection + Cost Disclosure (MANDATORY — show before generating)

Present the model menu and cost summary together. Check today's usage by
reading `workspace/temp/thumbnail/usage.json` (if it exists).

```
MODEL SELECTION:
  Which image generation model would you like to use?

  1. gemini-3.1-flash-image-preview (Recommended)
     $0.03/image · free tier 500/day · good quality
  2. gemini-2.0-flash-exp-image-generation
     FREE (preview) · ~100-500/day · experimental
  3. imagen-4-fast
     $0.020/image · 100/day · Google Imagen
  4. gemini-3-pro-image
     $0.039/image · no free tier · highest quality

GENERATION COST:
  Model:       gemini-3.1-flash-image-preview (free tier)
  Generate:    <N> face replacements
  Cost:        <N> × $<price> = $<total> (or FREE)
  Used today:  <X> images
  Free left:   ~<remaining> remaining today

  Proceed? [Y/n / or pick 1-5]
```

**⏸ STOP and wait for user confirmation before generating.**

### 4b. Generate Face-Replaced Images (with Text)

For each selected reference, run in parallel using the reverse-engineered
prompt from Step 3d (which includes text instructions):

```bash
/opt/homebrew/bin/python3 executors/thumbnail/replace_face.py \
    --reference "<reference_thumbnail_path>" \
    --headshot "workspace/input/thumbnail/headshots/<primary_emotion>.JPG" \
    --extra-headshots \
        "workspace/input/thumbnail/headshots/<extra1>.JPG" \
        "workspace/input/thumbnail/headshots/<extra2>.JPG" \
        "workspace/input/thumbnail/headshots/<extra3>.JPG" \
    --output "workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_A.png" \
    --model <selected_model> \
    --full-prompt "<reverse_engineered_prompt_from_state_json>" \
    --color-match
```

The primary headshot is the pose-matched one from Step 3c. Extra headshots
provide Gemini with additional angles/expressions of Subject Alpha for
better facial consistency. Read `extra_headshots` from `state.json`.

Map references to concept letters: first pick = A, second = B, etc.

Create the output directory first:
```bash
mkdir -p "workspace/temp/thumbnail/<PROJECT>/face_replaced"
```

On success: report each generated image with file path.
On failure:
  - No API key → check `credentials.json` or set env var
  - API error → show full error, suggest retrying
  - No image returned → suggest trying a different model or falling back

---

## Step 5 — Grid + QA

### 5a. Build Grid

Build directly from face-replaced images (text is already baked in by Gemini):

```bash
python3 executors/thumbnail/build_grid.py \
    "workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_A.png" \
    "workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_B.png" \
    "workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_C.png" \
    "workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_D.png" \
    "workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_E.png" \
    "workspace/output/thumbnail/<PROJECT>/grid.png" \
    --cols 3
```

### 5b. Present Results

Print the path to the grid so the user can open it themselves (do NOT open it automatically):
```
Thumbnail grid: workspace/output/thumbnail/<PROJECT>/grid.png
```

Read the grid using the Read tool (vision) and present it alongside the
results. Do NOT use markdown links for image paths — show plain text paths
so the user can find them in the file explorer:
```
THUMBNAIL GRID — Generated in <total_elapsed>s

  A: "<text>"
  B: "<text>"
  C: "<text>"
  D: "<text>"
  E: "<text>"

  Files:
    Grid       workspace/temp/thumbnail/<PROJECT>/grid_concepts.png
    Concept A  workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_A.png
    Concept B  workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_B.png
    Concept C  workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_C.png
    Concept D  workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_D.png
    Concept E  workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_E.png

USAGE:
  Model:       <model_name>
  Generated:   <N> images this round
  Cost:        <N> × $<price> = $<total> (or FREE)
  Used today:  <X> images (session total)
  Free left:   ~<remaining> remaining today
```

The `<total_elapsed>` is wall-clock time from when the first generation task
was launched to when the last one completed (since they run in parallel).
Read `usage_today` from the last executor's JSON output, then compute
remaining quota based on the model's daily limit (e.g. 500 for flash).

For mobile QA: read each concept image at the original resolution, visually assess
whether text would be legible at 320×180 mobile size. Flag any concept where text
is too small, low contrast, or blends into the background.

Update `state.json`: set `phase` to `"refinement"`, increment `iteration`.

---

## Step 6 — Iterative Refinement Loop

**⏸ STOP and wait for the user.**

| User says                           | Action                                                     |
|-------------------------------------|-------------------------------------------------------------|
| "Go with A"                         | Set `selected_concept = "A"`, copy A to final output        |
| "Redo B with shocked headshot"      | Re-run prompt engineering + `replace_face.py` for B         |
| "Change text on A to X"             | Update prompt with new text, re-run `replace_face.py` for A |
| "B looks bad, generate from scratch"| Fall back: `generate_background.py` + full `composite.py`   |
| "Pick different references"         | Loop back to Step 3                                         |
| "Variations of A"                   | Generate 4 variations of A with different headshots/prompts |
| "Done"                              | Finalize with current selection                              |

### Text Changes
When the user wants a text tweak:
- Update the reverse-engineered prompt with the new text
- Re-run `replace_face.py --full-prompt` for that concept
- Rebuild grid, present
- (This costs an API call since text is baked into the Gemini output)

### Fallback to Generate-From-Scratch
When face replacement quality is poor for a concept:
1. Analyze the reference thumbnail for visual inspiration
2. Write a background prompt based on the reference's composition
3. Run `generate_background.py` with that prompt
4. Run `composite.py` in full mode (headshot + text)
5. Replace just that concept in the grid

---

## Finalization

When the user selects a final concept:

1. Copy the selected concept image to:
   ```bash
   cp "workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_<LETTER>.png" \
      "workspace/output/thumbnail/<PROJECT>/thumbnail_final.png"
   ```

2. Check file size:
   - If > 2MB: convert to JPG at 95% quality
   - If still > 2MB: reduce quality to 90%

3. Update `state.json`: set `phase` to `"complete"`, `selected_concept` to the letter

4. Print the path to the final thumbnail so the user can open it themselves (do NOT open it automatically):
   ```
   Final thumbnail: workspace/output/thumbnail/<PROJECT>/thumbnail_final.png
   ```

5. Report:
   ```
   Thumbnail complete!

   Final:     workspace/output/thumbnail/<PROJECT>/thumbnail_final.png
   Grid:      workspace/output/thumbnail/<PROJECT>/grid.png
   Size:      <file_size>
   Concept:   <letter> — "<text overlay>" (ref #<number>)
   Rounds:    <iteration_count>

   Temp files in workspace/temp/thumbnail/<PROJECT>/ can be safely deleted.
   ```

---

## Error Handling Summary

| Error                           | Action                                                |
|---------------------------------|-------------------------------------------------------|
| `cross_niche_research.py` fails | Report error, offer to skip research                  |
| Face replacement API error      | Show full error, suggest checking API key or model     |
| No face in reference            | Suggest picking a different reference or generating from scratch |
| Compositing fails               | Show error, check Pillow: `pip install Pillow`        |
| Headshot missing                | Warn user, cannot proceed with face replacement       |
| Brand guide missing             | Use defaults, inform user                             |
| Font not found                  | Fall back to system default, warn user                |
| No `GEMINI_API_KEY`             | Stop pipeline, show setup instructions                |
| `match_headshot.py` fails       | Suggest manual headshot selection, skip pose matching  |
