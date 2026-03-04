# Directive: Thumbnail Generation

## Purpose
You are an expert YouTube thumbnail designer. Your job is to research the
competitive landscape, develop a visual strategy, and generate multiple
thumbnail concepts for the user to choose from.

This directive covers the full pipeline: Research → Strategy → Concepts →
Assets → Generation → Compositing → QA → Refinement.

---

## YouTube Thumbnail Spec

- **Dimensions**: 1280 × 720 pixels (16:9 aspect ratio)
- **Max file size**: 2 MB
- **Format**: PNG (preferred for quality) or JPG
- **Text**: 3–5 words maximum on the thumbnail
- **Safe zone**: Keep critical elements within 90% inner boundary (64px margin)
- **YouTube overlay dead zones** — never place text or key visual elements in
  these areas, as YouTube overlays UI on top of them:
  - **Bottom-right**: Video duration badge (always visible)
  - **Bottom strip**: Chapters progress bar (visible on hover)
  - **Top-right**: "Watch Later" and "Add to Queue" icons (visible on hover)
  - **Top-left**: Generally safe — best position for text

---

## Visual Style

Style is derived from competitive research — not from hardcoded defaults.
1. Complete the competitive research and scoring first
2. Identify the dominant color palettes, contrast approaches, and text styles
   from the top-scoring thumbnails
3. Choose a palette and style that **differentiates** from the top competitors
   while following proven contrast and readability patterns
4. Present the derived style choices to the user as part of the strategy session
   (Step 3) before generating any images

---

## Headshots

### Location
Headshots are stored in `workspace/input/thumbnail/headshots/`.
Each headshot is named descriptively — by emotion, gesture, or expression:
  - Emotions: `excited.JPG`, `shocked.JPG`, `serious.JPG`, `thinking.JPG`
  - Gestures: `thumbs_up.JPG`, `pointing.JPG`, `arms_crossed.JPG`
  - Variants: `excited_1.JPG`, `excited_2.JPG`, `shocked_closeup.JPG`

Any descriptive filename works. Multiple variants of the same emotion are fine.

### Format
Headshots are JPG files. In the reference-based pipeline, the raw JPG is
sent directly to Gemini alongside the reference thumbnail — Gemini handles
integrating the face into the reference layout. No manual background
removal is needed.

### Pose Matching (MediaPipe)
Use `match_headshot.py` to automatically find the best-matching headshot
for each reference thumbnail based on face pose (yaw/pitch):

```bash
/opt/homebrew/bin/python3 executors/thumbnail/match_headshot.py \
    --reference <competitor_thumbnail.jpg> \
    --headshots-dir workspace/input/thumbnail/headshots/ \
    --top-k 3
```

This analyzes the face direction in the reference and finds the headshot
with the closest pose using Euclidean distance. Present the top 3 matches
to the user as suggestions.

### Selection
For each selected reference thumbnail, the orchestrator:
1. Runs `match_headshot.py` to find the best pose match
2. Suggests the top match to the user
3. User approves or picks a different headshot

If no headshots directory exists or is empty, skip face replacement and
inform the user.

---

## Competitive Research Rules

### Channel Profile
Before research begins, verify a channel profile exists at
`memory/channel-profile.md`. This profile is built on first use by analyzing
the user's recent video titles and transcripts. It provides:
- **Niche terms** for cross-niche filtering (populated in `cross_niche.json`)
- **Tone profile** for script writing (shared with /write pipeline)
- **Performance baseline** for context

If no profile exists, the orchestrator will build one before proceeding.

### Self-Filtering
If `workspace/config/channel.json` exists, read the `channel_id` field and
always pass `--exclude-channel <channel_id>` to `research_thumbnails.py`.
This prevents the user's own videos from appearing in competitor results.

### Research Strategy
All research uses cross-niche outlier detection via `cross_niche_research.py`.
The executor searches two sources and merges them:

1. **Keyword search**: Randomly samples from curated cross-niche keywords
   (business, productivity, psychology, etc.) — finds transferable hooks
2. **Channel monitoring**: Randomly samples from monitored channels list
   (top creators across niches) — finds their latest outlier videos

Own-niche content is automatically filtered out (using niche terms from the
channel profile). Non-transferable formats (challenges, vlogs, news, etc.) are
excluded. Only genuine outliers — videos performing significantly above their
channel's average — are kept.

Each run samples different keywords and channels for variety. Config lives at
`workspace/config/cross_niche.json`.

The search uses:
- `--exclude-channel` (if channel.json exists)
- `--min-subscribers 100000` — only include established creators (100K+ subs)
- `--min-outlier 1.5` — only keep videos performing 1.5× their channel average

### How to Research
1. Run `cross_niche_research.py` with `--fetch-channel-stats
   --count 100` — the executor calculates the full final score internally
   (outlier + recency + hook modifiers) and returns the top 100
2. Export results to Google Sheet via `export_research_sheet.py`
3. Present the Sheet URL to the user for browsing

### Outlier-Based Scoring

#### Outlier Score (calculated by executor)
The base score measures how a video performed relative to its channel's average:

`outlier_score = video_views / channel_average_views`

- 1.0 = performed at channel average
- 3.0 = performed 3× the channel average
- 10.0+ = viral outlier

Channel average views are calculated from the channel's 10 most recent videos
via `research_thumbnails.py --fetch-channel-stats`. If channel stats fail,
the executor falls back to `subscribers × 0.02` as an estimate.

#### Recency Boost (calculated by executor)
A multiplier that gives newer high-performing videos more weight:

| Age | Multiplier |
|---|---|
| ≤ 30 days | 1.15× |
| 31–90 days | 1.10× |
| 91–180 days | 1.0× |
| > 180 days | 0.95× |

#### Cross-Niche Modifiers (applied by executor)
Percentage boosts applied based on the video's title content (keyword matching):

| Category | Modifier | Example terms |
|---|---|---|
| Money hook | +30% | income, salary, wealth, "$", million, profit |
| Time hook | +20% | faster, productivity, save time, hack, shortcut |
| Curiosity hook | +15% | secret, nobody tells you, truth about, hidden |
| Transformation hook | +15% | before/after, from zero, changed my life, journey |
| Contrarian hook | +15% | wrong, mistake, myth, why I stopped, overrated |
| Urgency hook | +10% | before it's too late, don't miss, last chance |
| Technical term (per term) | −20% | jargon, acronyms, niche terminology |
| Monitored channel | +25% | video is from a channel in `monitored_channels` |

Full term lists for each category are defined in
`workspace/config/cross_niche.json` under `hook_categories`.

The executor scans the video title for matching terms from each category.
Multiple positive categories can stack. Only one modifier of each type is
applied (not per term match within a category).

The monitored channel boost is data-driven: the executor tags each video
with `_is_monitored: true/false` based on whether its channel appears in
the `monitored_channels` config. This ensures curated creators get priority
while keyword search can still surface videos from any channel.

#### Final Score Formula
`final_score = outlier_score × recency_multiplier × (1 + sum_of_modifiers)`

Example: Video with 6.81× outlier, 25 days old, money hook, no technical terms:
`6.81 × 1.15 × (1 + 0.30) = 10.18`

### Output — Google Sheet
Research results are exported to a reusable Google Sheet via
`export_research_sheet.py`. Each pipeline run creates a new tab in the
same spreadsheet (tab name = `YYYYMMDD_<slug>`).

The Sheet contains 19 columns: Cross-Niche Score, Outlier (w/ Recency),
Raw Outlier, Days Old, Category, Title, Video Link, View Count,
Duration (min), Channel Name, Channel Avg Views, Thumbnail (IMAGE formula),
Summary (AI-generated), Title Variant 1-3 (AI-generated), Raw Transcript,
Publish Date, Source.

Summary and title variants are generated by Claude during the research phase
(Step 2c in the orchestrator) and passed via `--analysis analysis.json`.

The spreadsheet ID is stored in `workspace/config/research_sheet.json`
for reuse across sessions.

Present a brief summary to the user alongside the Sheet URL:
```
RESEARCH COMPLETE:
  Research: cross-niche (X keywords + Y channels)
  Research time: Xm Ys
  Videos scanned: X → filtered to Y outliers → top 100 scored
  Sheet: <Google Sheet URL>
```

---

## Strategy Session: Desire Loop

### Framework
Map the thumbnail concept through 4 dimensions:

1. **Triggered Desire**: What does the viewer want?
   (e.g., "I want to protect my money", "I want to get rich")

2. **Pain Point**: What fear or frustration does this address?
   (e.g., "I'm losing to inflation", "I missed the opportunity")

3. **Solution Signal**: What does the thumbnail hint at?
   (e.g., a number, a comparison, a secret revealed)

4. **Curiosity Loop**: What question does the thumbnail plant?
   (e.g., "What's that number?", "Why is this different?")

### Rules
- The thumbnail must trigger at least 2 of the 4 dimensions
- Never use text that reveals the answer — the thumbnail creates the question,
  the video provides the answer
- Text on thumbnail MUST complement the video title, never repeat it

---

## YouTube Thumbnail Psychology

These principles are backed by platform-specific viewer behavior. Use them
as a reference during both competitive analysis (scoring what works) and
concept generation (designing what to build).

### The 3-Second Rule
Viewers decide whether to click in under 3 seconds. The thumbnail must
communicate its value proposition instantly — if it requires "reading" or
decoding, it fails. Test every concept by asking: "Would I understand this
at a glance while scrolling?"

### Emotion Hierarchy
Not all expressions perform equally. Ranked by click-through rate impact:
1. **Shock / surprise** — widened eyes, open mouth (highest CTR)
2. **Excitement / triumph** — big smile, fist pump, thumbs up
3. **Anger / frustration** — furrowed brows, clenched jaw
4. **Curiosity / intrigue** — raised eyebrow, thinking pose
5. **Calm / neutral** — lowest CTR; avoid unless the topic demands authority

Match the headshot emotion to the content's emotional core, not just
the topic category.

### Number Specificity
Specific numbers outperform round numbers because they signal real data:
- "$1,247/month" > "$1,000/month" (feels researched, not made up)
- "37% drop" > "big drop" (quantifies the stakes)
- "3 mistakes" > "common mistakes" (promises a finite, consumable list)

When using numbers in thumbnail text, prefer the specific figure from
the video content.

### Face Direction & Visual Flow
The viewer's eye follows the face's gaze direction:
- **Face looking toward text** → guides the eye to the message (recommended)
- **Face looking at camera** → creates direct connection (good for authority)
- **Face looking away from text** → creates disconnection (avoid)

Position the headshot so the face naturally leads the viewer to the text
or key visual element.

### Contrast with YouTube UI
Thumbnails appear against YouTube's white (light mode) or dark gray
(dark mode) background. To stand out in both:
- Avoid pure white or dark gray edges — the thumbnail will blend into the UI
- Use a subtle colored border or vignette to separate from the page
- High-saturation accent colors pop in both modes

### The Squint Test
Squint at the thumbnail (or view at 25% zoom). If you can still:
1. Identify the face and its emotion
2. Read the text (at least the key word)
3. Understand the visual concept

Then it passes. If any element disappears, it needs more contrast or
simplification.

### Pattern Interrupt
In a feed of similar thumbnails, the one that breaks the visual pattern
gets noticed. This is why cross-niche techniques are valuable — bringing
a visual approach from tech/lifestyle into finance creates instant
differentiation. When all competitors use the same layout, deliberately
choose a different one.

---

## Reference Selection Rules

### Process
After competitive research and scoring, present ALL competitor thumbnails
to the user as a numbered research grid. The user selects exactly 5
thumbnails as layout references for face replacement.

### Research Grid Presentation
Build a research grid using `build_grid.py` showing all downloaded thumbnails
in a numbered grid (4 columns):
```bash
python3 executors/thumbnail/build_grid.py \
    <all_thumbnail_paths...> \
    workspace/temp/thumbnail/<PROJECT>/research/research_grid.png \
    --cols 4 --label-style number --skip-qa
```
Open the grid in VSCode alongside the scoring table so the user can see
both the visual and the performance data.

### Selection Guidance
Advise the user to pick references that:
- Score well on the composite rubric (70+)
- Have a clear person/face that can be replaced
- Have diverse compositions (not 4 identical layouts)
- Have clear, non-cluttered backgrounds

### Auto-Suggestions Per Reference
For each selected reference, the orchestrator auto-suggests:
1. **Headshot**: Run `match_headshot.py` → best pose match from user's headshots
2. **Text**: Analyze reference's text + video title + user's topic → suggest
   3-5 word overlay text that complements the video title
3. **Text position**: Match where text appears in the reference

The user approves or edits each suggestion before generation.

### Text Rules
- Maximum 5 words on the thumbnail
- Text must NOT repeat the video title
- Text should add information the title lacks (a number, a comparison word,
  a reaction)
- Use high-contrast colors: white on dark, or outlined text
- Minimum apparent font size: readable at 320×180 (mobile preview)

### Visual Frameworks Reference
These composition approaches help classify and differentiate references:
- **Rule of Thirds**: Subject at 1/3 intersection, text at opposite third
- **Before/After Split**: Vertical or diagonal split showing contrast
- **Centered Face + Text**: Large headshot center, bold text above/below
- **Data Callout**: Large number or statistic as focal point, face to side

---

## Prompt Engineering Rules

### Process
After the user approves reference selections (headshot + text), reverse-engineer
each reference thumbnail into a detailed Gemini prompt before face replacement.
This is a Claude intelligence step — analyze each reference image using vision,
then construct a technical prompt optimized for Gemini image generation.

### Prompt Structure
Each reverse-engineered prompt must include these components derived from
analyzing the reference image:

1. **Subject & Action**: Physical traits, micro-expressions, clothing, posture
   of the person in the reference (who will be replaced)
2. **Camera Settings**: Lens focal length (e.g., 14mm wide, 85mm portrait),
   camera angle (low-angle, eye-level, dutch angle), depth of field
3. **Lighting Environment**: Primary/secondary light sources, color temperature,
   techniques (rim lighting, softbox, volumetric fog, natural window light, etc.)
4. **Composition**: Subject placement (rule of thirds, centered), background
   elements, areas of negative space meant for text overlays
5. **Aesthetic & Rendering**: Visual style (hyper-realistic, cinematic color
   grading, vibrant YouTube thumbnail style), dominant colors

Then append standard instructions:
6. **Face Replacement**: "Replace the person in this scene with the person
   shown in the second image. The new person should match the original's
   pose, angle, and position exactly. Make the face look exactly like the
   person in the second image."
7. **Text**: "Include the text '[TEXT]' prominently in the [POSITION] area
   of the image. [Style instructions derived from the reference's actual
   text treatment — font style, color, effects, size relative to frame]."
8. **Constraints**: "Do NOT include any watermarks. Wide landscape framing,
   16:9 aspect ratio."

### Rules
- Output ONLY the prompt string — no commentary or explanation
- The prompt must be specific enough that Gemini could recreate the scene
  from scratch even without the reference image
- Text style instructions should be derived from the reference's actual text
  treatment (e.g., if the reference has bold yellow text with black outline,
  say "bold yellow text with thick black outline, drop shadow effect")
- If the reference has no visible text, describe text style based on the
  overall aesthetic (e.g., "clean white sans-serif text with subtle shadow")
- Save each prompt to state.json for traceability and refinement

---

## Asset Gathering Rules

- Only download assets (logos, icons) when a concept specifically requires them
- Use `fetch_asset.py` to download to `workspace/temp/thumbnail/<slug>/assets/`
- Supported formats: PNG (preferred), SVG, JPG
- Maximum 5 assets per concept (keep it clean)
- If an asset cannot be found, substitute with a text description for the user
  and proceed without it

---

## Face Replacement Rules

### Parallel Generation
- Generate all 5 face-replaced thumbnails in parallel (concurrent executor calls)
- Use `replace_face.py` for each reference

### How Face Replacement Works
For each selected reference, the executor:
1. Sends the competitor thumbnail + user's headshot to Gemini along with a
   detailed reverse-engineered prompt from the Prompt Engineering step
2. Gemini recreates the thumbnail with the user's face replacing the
   original person, preserving the background, composition, colors, and layout
3. The generated image includes text, rendered by Gemini as part of the scene
   (no separate compositing step needed)

Each reference gets a custom prompt via `--full-prompt`:
```bash
/opt/homebrew/bin/python3 executors/thumbnail/replace_face.py \
    --reference <competitor_thumbnail.jpg> \
    --headshot <user_headshot.jpg> \
    --output workspace/temp/thumbnail/<PROJECT>/face_replaced/concept_A.png \
    --model <selected_model> \
    --full-prompt "<reverse_engineered_prompt>"
```

### API Configuration
- API key is loaded from `credentials.json` (`gemini_api_key` field) or the
  `GEMINI_API_KEY` environment variable (credentials.json takes priority)
- Provider: Google Gemini multi-image generation
- Default model: `gemini-3.1-flash-image-preview`
- If no API key is found in either location, stop and instruct the user on setup

### Model Selection + Cost Disclosure (MANDATORY)
Before every generation step, present the model menu and cost summary.
The user picks a model (or accepts the default), then confirms generation.

Available models (present as numbered options):

| # | Model | Cost/image | Free daily limit | Notes |
|---|---|---|---|---|
| 1 | `gemini-3.1-flash-image-preview` (default) | $0.03 | 500/day free tier | Good balance of quality and cost |
| 2 | `gemini-2.0-flash-exp-image-generation` | $0.00 (free preview) | ~100–500/day | Experimental, lower quality |
| 3 | `imagen-4-fast` | $0.020 | 100/day | Google Imagen |
| 4 | `gemini-3-pro-image` | $0.039 | No free tier | Highest quality |

If user confirms without specifying a model, use the default (option 1).
If user says "use pro", "option 4", etc., switch to that model.

After model selection, show cost summary:
1. Which model is being used and whether it's free or paid
2. Number of images to generate
3. Cost breakdown (e.g., "5 × $0.03 = $0.15" or "5 × $0.00 = FREE")
4. How many images have been generated today (from `workspace/temp/thumbnail/usage.json`)
5. How many free images remaining today (daily limit − today's usage)
6. Wait for user confirmation before proceeding

### Output
- All face-replaced images go to `workspace/temp/thumbnail/<PROJECT>/face_replaced/`
- Naming: `concept_A.png`, `concept_B.png`, `concept_C.png`, `concept_D.png`, `concept_E.png`

### Fallback: Generate From Scratch
If face replacement produces poor results for any reference, fall back to
the original generate-from-scratch pipeline for that concept:
1. Use the reference thumbnail as visual inspiration
2. Write a text prompt describing a similar background/composition
3. Generate with `generate_background.py`
4. Composite with `composite.py` (full mode: headshot + text)

Mixed mode is allowed: e.g., concepts A, B, D use face replacement while
concept C uses generated background.

---

## Compositing (Fallback Only)

Compositing via `composite.py` is only used in **fallback mode** — when face
replacement produces poor results and the pipeline falls back to
`generate_background.py`. In that case, use `composite.py` in full mode
(headshot + text overlay).

In the normal reference-based pipeline, text is included in the Gemini
generation prompt via the Prompt Engineering step — no separate compositing
step is needed.

---

## QA Rules

### Grid Output
- Combine all 5 face-replaced thumbnails into a 3-column grid (3+2 layout)
- Label each quadrant: A, B, C, D (top-left corner of each)
- Save to `workspace/output/thumbnail/<PROJECT>/grid.png`

### Mobile Readability Test
For each thumbnail:
1. Scale down to 320×180 (mobile preview size)
2. Visually inspect text readability at mobile size (text is rendered by
   Gemini, so no precise bounding box is available — use visual assessment)
3. Flag any concept where text is too small or blends into the background

### Title-Thumbnail Pairing Test
For each thumbnail, evaluate the pairing with the proposed video title.
The thumbnail + title must tell a story together:
1. Does the thumbnail add information the title doesn't have?
2. Does the combination create a curiosity gap (question without answer)?
3. Would a viewer scrolling past understand the value proposition in <3 seconds?
4. Flag any concept where the text repeats or contradicts the title.

### QA Report
```
QA RESULTS:
  A: [PASS/WARN] — Mobile readability: [good/poor], Title pairing: [good/weak]
  B: [PASS/WARN] — Mobile readability: [good/poor], Title pairing: [good/weak]
  C: [PASS/WARN] — Mobile readability: [good/poor], Title pairing: [good/weak]
  D: [PASS/WARN] — Mobile readability: [good/poor], Title pairing: [good/weak]
  E: [PASS/WARN] — Mobile readability: [good/poor], Title pairing: [good/weak]
```

---

## Iterative Refinement

### User Options
After presenting the grid and QA results, the user may:
- Pick a winner: "Go with B" → finalize concept B
- Redo with different headshot: "Redo B with shocked" → re-run face replacement
- Change text: "Say 'DON'T BUY' on A" → update prompt, re-run face replacement
- Fall back: "B looks bad, generate from scratch" → use reference as inspiration
  for `generate_background.py` + full `composite.py`
- New references: "Pick different ones" → loop back to reference selection
- Variations: "Variations of A" → generate 4 variations with different headshots
  or slight prompt adjustments

### State Tracking
Save iteration state to `workspace/temp/thumbnail/<PROJECT>/state.json`:
```json
{
  "topic": "...",
  "slug": "...",
  "phase": "research|selection|generation|refinement|complete",
  "iteration": 0,
  "selected_concept": null,
  "concepts": [],
  "selected_references": [
    {"ref_number": 3, "ref_path": "...", "headshot": "excited.JPG",
     "text": "DON'T DO THIS", "text_position": "top-left",
     "prompt": "<reverse-engineered prompt for this reference>"}
  ],
  "created": "YYYY-MM-DD",
  "updated": "YYYY-MM-DD"
}
```

---

## Error Handling

- If image generation API fails: show the error, suggest checking API key.
  Do not retry automatically.
- If headshot directory is empty/missing: generate background-only thumbnails,
  inform the user
- If `brand_style_guide.txt` is missing: use defaults, inform the user
- If compositing fails in fallback mode (e.g., missing font): show error,
  suggest installing the font. Fall back to default system font.
- If asset download fails: skip that asset, proceed with available assets
- If no API key is configured: stop and tell the user to add `gemini_api_key`
  to `credentials.json` or set `GEMINI_API_KEY` env var
- If Google Sheets API not enabled: tell user to enable it at
  https://console.cloud.google.com/ → APIs & Services → Enable Google Sheets API
- If Google Sheets OAuth fails: tell user to check credentials.json has the
  `installed` section (same OAuth credentials used for Google Docs export)

---

## What NOT to Do

- Do not use generic one-size-fits-all prompts — every reference gets a
  custom reverse-engineered prompt via the Prompt Engineering step
- Do not skip the prompt engineering step — detailed prompts produce
  dramatically better results than the generic BASE_PROMPT
- Do not repeat the video title as thumbnail text
- Do not use more than 5 words on the thumbnail
- Do not skip the competitive research step
- Do not auto-select references — the user always chooses which thumbnails
  to use as layout references
- Do not proceed to face replacement without showing reference suggestions
  to the user first
- Do not overwrite previous iteration outputs — each round gets its own files
- Do not include channels with fewer than 100K subscribers in research results
