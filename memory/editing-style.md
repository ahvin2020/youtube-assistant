# Editing Style Reference

**Dataset**: 18 videos across 6 channels (3 per channel)
**Channels**: @ZietInvests, @NewMoneyYouTube, @DamienTalksMoney, MagnatesMedia, James Jani, Johnny Harris
**Purpose**: Guide the Opus subagent in /edit graphics pass to generate professional, on-brand Remotion enhancement specs

---

## Part 1: Technique Catalog

### text_overlay

Text overlays are the most frequently deployed enhancement across all 6 channels. They serve distinct roles depending on context.

**Use cases and recommended styles:**

| Use Case | Style | Properties | Source Channels |
|----------|-------|------------|-----------------|
| Key statistic callout | `kinetic_pop` | `font_size: 48-72`, `color: "#FFFFFF"`, bold, `animation_in: scale_bounce`, `position: { x: "center", y: "center" }` | ZietInvests, Damien, NewMoney |
| Keyword emphasis on b-roll | `highlight` | `font_size: 36-48`, `color: "#FFFFFF"` with yellow highlight behind key word, `animation_in: slide_up`, `position: { x: "center", y: "center" }` | ZietInvests, James Jani |
| Quote or statement | `fade` | `font_size: 28-36`, `color: "#FFFFFF"`, italic, `animation_in: fade`, centered, hold 4-6s | James Jani, NewMoney |
| Chapter/section label | `slide_in` | `font_size: 24-32`, `color: "#FFFFFF"`, ALL-CAPS condensed, `animation_in: slide_right`, `position: { x: "left", y: "top_third" }` | All 6 channels |
| Dramatic single word | `kinetic_pop` | `font_size: 72-100`, `color: accent_color`, ALL-CAPS, `animation_in: pop`, hold 2-3s | MagnatesMedia, Damien |

**Universal patterns:**
- White text on dark backgrounds is the default across all 6 channels — never use light text on light backgrounds
- ALL-CAPS for headings and labels; sentence case for explanatory text
- Bold/extra-bold weight for emphasis; regular weight for supporting text
- Maximum two text overlays visible simultaneously (universal rule — no channel exceeds this)
- Text overlays on b-roll should darken the background to ~40-50% brightness for legibility (ZietInvests, James Jani)

**Timing:**
- `animation_in` duration: 0.3-0.5s (15-20 frames at 30fps)
- Hold: 3-8s depending on text length (budget ~250ms per word)
- `animation_out: fade` at 0.3s is the universal safe default
- Never let text linger after the narrator has moved on — sync exit to narration beat

**Best defaults:**
```json
{
  "style": "highlight",
  "font_size": 36,
  "color": "#FFFFFF",
  "animation_in": "slide_up",
  "animation_out": "fade",
  "position": { "x": "center", "y": "top_third" }
}
```

---

### lower_third

Lower thirds are used sparingly across all channels. Most channels (ZietInvests, NewMoney, MagnatesMedia, James Jani) never use lower thirds for the host — only for external speakers or interview subjects.

**When to use:**
- Identifying an interviewee or expert (Johnny Harris, Damien, James Jani)
- Labeling an external news clip speaker (Damien's yellow name labels)
- Never for the host/narrator — this is a universal pattern across all 6 channels

**Best practices:**
- `position: "bottom_left"` is dominant (5 of 6 channels place name cards bottom-left)
- Stacked format: bold name on top, lighter title/role below
- `animation_in: slide_up` with 0.3s duration — clean and professional
- `animation_out: slide_down` or `fade` at 0.3s
- Hold for 4-6 seconds minimum — long enough to read both lines
- Re-show the lower third each time the same speaker reappears after a cutaway (Johnny Harris pattern)

**Best defaults:**
```json
{
  "name": "Speaker Name",
  "title": "Title / Organization",
  "position": "bottom_left",
  "animation_in": "slide_up",
  "animation_out": "fade"
}
```

**Damien's yellow name label variant:** For identifying people in external clips, a bold black name on a bright yellow (#FFE500) background pill is highly readable and distinctive. Consider this for external clip attributions.

---

### data_viz

Data visualization is a core strength across all 6 channels. Each channel has a distinct approach, but clear patterns emerge.

#### Bar Charts (`chart_type: "bar"`)
- **Dark background** (#1E2228 to #2A2A2A) is universal for data charts (Damien, NewMoney, MagnatesMedia)
- **Color coding**: red (#FF3B30) for negative values, cyan/teal (#66FFFF or #5AC8FA) for positive values, yellow-orange (#F5A623) as primary data color (Damien's signature)
- **Animation**: `animation_in: build_up` — bars grow from the zero line outward, sequentially left-to-right
- One key takeaway annotation per chart (Damien's dark annotation bubble pattern)
- **Benchmark bar**: style one bar differently (gray or neutral) as the reference point (Damien)
- Source citation in bottom-right corner, small gray text

**Best defaults for bar chart:**
```json
{
  "chart_type": "bar",
  "title": "Chart Title",
  "data": [
    { "label": "Category A", "value": 100, "color": "#5AC8FA" },
    { "label": "Category B", "value": -50, "color": "#FF3B30" }
  ],
  "position": { "x": "center", "y": "center" },
  "scale": 0.85,
  "animation_in": "build_up",
  "animation_out": "fade"
}
```

#### Comparison Charts (`chart_type: "comparison"`)
- Side-by-side panels with a clean vertical divider (NewMoney)
- Logo or flag headers to identify each side
- Maximum 3-4 data points per side to prevent overload
- `animation_in: build_up` with left panel appearing before right (0.3s stagger)
- Bold ALL-CAPS labels for category names

#### Pie Charts (`chart_type: "pie"`)
- Rarely used across all 6 channels — only NewMoney uses donut/ring variants
- When used, keep to 3-5 segments maximum with a key statistic displayed in the center
- Never use for small differences — only when proportions are dramatically different
- Prefer bar charts over pie charts in almost all cases

#### Timelines (`chart_type: "timeline"`)
- Dark purple/magenta background with film grain texture (Johnny Harris)
- White tick marks with year labels in sans-serif
- Left-to-right sweep reveal animation
- Enlarged anchor years at key moments (~28-36pt bold)
- Orange/amber glow (#D4A040) at the "present" or focal marker
- `animation_in: wipe` for the progressive reveal

#### Flowcharts (`chart_type: "flowchart"`)
- Dark navy/charcoal background (James Jani)
- Flat-design icons for entities (silhouettes for people, rounded rectangles for systems)
- Neon glow connection lines between nodes (#00FF00 for positive flow, #E91E63 for negative)
- Left-to-right flow direction
- Sequential build animation — nodes appear one by one following the flow
- `animation_in: build_up` with staggered element reveals

#### Tables (`chart_type: "table"`)
- Avoid when possible — all 6 channels prefer visual alternatives to tables
- When necessary: dark background, minimal gridlines, alternating row opacity
- Highlight the key row with a color accent (yellow highlight for ZietInvests, neon green for Damien)
- Maximum 4-5 rows visible at once

**Universal data presentation rules:**
- Each graphic carries ONE key takeaway — never overload with data (universal across all channels)
- Numbers are the focal point — always the largest element on screen (NewMoney, Damien)
- Round numbers for impact in callouts; precise numbers only in chart axes (NewMoney)
- Color-code values semantically: green = positive/growth, red = negative/danger, yellow = emphasis/neutral
- Source citation on every data graphic without exception (universal)

---

### number_counter

Number counters create dramatic reveals for key statistics. Used heavily by MagnatesMedia (count-up tickers), Damien (price callouts), and Johnny Harris (persistent altitude/year counters).

**Use cases:**
| Use Case | Properties | Source |
|----------|-----------|--------|
| Revenue/price reveal | `font_size: 56-72`, `prefix: "$"`, `color: "#FFFFFF"`, `animation_in: fade` | Damien, NewMoney |
| Percentage stat | `font_size: 48-64`, `suffix: "%"`, `color: "#FF3B30"` (red for alarm) or `"#4ADE4A"` (green for growth) | Damien, ZietInvests |
| Year counter (persistent) | `font_size: 28-36`, no prefix/suffix, `position: { x: "left", y: "top" }`, maintained across shots | Johnny Harris |
| Frame-filling impact number | `font_size: 96-120`, centered, minimal decoration, `color: accent_color` | James Jani, NewMoney |

**Best practices:**
- Count from 0 to the target value over 1-2 seconds (never instant)
- Use `prefix` for currency symbols ("$", "RM", "£") — place before the number
- Use `suffix` for units ("%", "K", "M", "B") — place after
- `title` above the number for context, `subtitle` below for comparison/change
- Frame-filling numbers (font_size 72+) work best when the number IS the entire point — no competing elements
- For persistent counters (Johnny Harris style), keep font_size small (28-36) and pin to a corner

**Best defaults:**
```json
{
  "from": 0,
  "to": 1000000,
  "prefix": "$",
  "suffix": "",
  "title": "Total Revenue",
  "font_size": 56,
  "color": "#FFFFFF",
  "position": { "x": "center", "y": "center" },
  "animation_in": "fade",
  "animation_out": "fade"
}
```

---

### source_overlay

Source overlays are critical for credibility. Every channel in the dataset treats source material as visual evidence, not decoration.

**When to use:**
- Showing a news article, SEC filing, research paper, or financial document
- Displaying a tweet, Reddit post, or social media embed
- Presenting a website screenshot or data table from an external source

**Treatment styles (ranked by production quality):**

1. **Cinematic evidence** (James Jani, NewMoney): Screenshot with perspective tilt (~5 degrees), warm color grade, drop shadow, slow drift animation. `animation_in: fade`, `scale: 0.7-0.85`.

2. **Canvas-mounted evidence** (ZietInvests): Screenshot centered on a light (#F2F2F2) or dark (#0D0D0D) canvas background with grid texture. `position: { x: "center", y: "center" }`, `scale: 0.65-0.75`.

3. **Highlighted document** (all channels): Screenshot with `highlight_regions` marking key passages. Use yellow (#FFFF00) for factual highlights, cyan (#00E5FF) for secondary highlights.

**Universal rules:**
- Always include a source attribution (pair with a `text_overlay` showing "Source: [Name]" in the top-right or bottom-right corner)
- Never show raw, ungraded screenshots — always apply at minimum a subtle color grade
- Slow Ken Burns zoom (`zoom_effect` with `push_in`, `from_scale: 1.0`, `to_scale: 1.15`) on documents to guide attention
- Hold for 5-15 seconds depending on text density — give the viewer time to read highlighted passages
- `highlight_regions` should mark ONLY the narratively critical phrases — surgical precision, not broad strokes (James Jani)

**Best defaults:**
```json
{
  "screenshot_path": "/path/to/screenshot.png",
  "headline": "Article Title",
  "highlight_regions": [{ "x": 120, "y": 200, "width": 400, "height": 30 }],
  "position": { "x": "center", "y": "center" },
  "scale": 0.75,
  "animation_in": "fade",
  "animation_out": "fade"
}
```

---

### callout_box

Callout boxes provide the narrator's editorial voice within data-heavy sequences. Damien's "dark annotation bubble" pattern is the gold standard.

**Style recommendations:**

| Style | Use Case | Visual Treatment |
|-------|----------|-----------------|
| `"insight"` | Key takeaway from a chart or data point | Dark semi-transparent background (#1A1D24 at 80% opacity), white text, positioned near relevant data |
| `"quote"` | Direct quote from a person or document | Cream/parchment background (#E8E0D0), serif font, with red keyword highlights (James Jani parchment card) |
| `"warning"` | Financial disclaimer, risk callout | Red-tinted border, white text on dark background, exclamation icon |
| `"tip"` | Actionable advice or practical insight | Green-tinted border or accent, clean sans-serif |

**Best practices:**
- Position near the relevant data point, never overlapping critical chart elements (Damien)
- One callout per chart — never stack multiple callout boxes
- `animation_in: fade` with a slight `scale_bounce` (0.95 to 1.0) for subtle entrance
- Hold for 4-8 seconds (match narration duration)
- Maximum 15-20 words per callout — this is a takeaway, not a paragraph

**Best defaults:**
```json
{
  "text": "Key takeaway text here",
  "style": "insight",
  "position": { "x": "right", "y": "bottom_third" },
  "animation_in": "fade",
  "animation_out": "fade"
}
```

---

### animated_list

Animated lists are used for multi-point explanations, feature breakdowns, and sequential reveals. NewMoney's section cards and Damien's bullet points exemplify best practices.

**When to use:**
- Listing 3-5 key points or features
- Breaking down a process into steps
- Comparing multiple items in a category

**Reveal styles:**

| Style | When | Properties |
|-------|------|-----------|
| `"sequential"` | Narrating each point individually | `stagger_frames: 90` (3s at 30fps per item) — each item appears as narrator reaches it |
| `"cascade"` | Quick overview of all points | `stagger_frames: 15` (0.5s between items) — rapid but readable |
| `"all_at_once"` | Recap or summary | All items appear together for reference |

**Best practices:**
- Maximum 5 items per list — beyond that, split into multiple lists or use a different format
- Include `icon` for each item when possible — icons improve scanability
- Bold/colored first word of each item for quick parsing
- `animation_in: slide_right` for sequential reveals; `animation_in: fade` for cascade
- `position: { x: "center", y: "center" }` for full-screen lists; `{ x: "right", y: "center" }` when alongside a visual

**Best defaults:**
```json
{
  "items": [
    { "text": "First point", "icon": "dollar" },
    { "text": "Second point", "icon": "chart" },
    { "text": "Third point", "icon": "check" }
  ],
  "reveal_style": "sequential",
  "stagger_frames": 90,
  "position": { "x": "center", "y": "center" },
  "animation_in": "slide_right",
  "animation_out": "fade"
}
```

---

### icon_accent

Icon accents add visual context without competing with the main content. Used by all channels in different ways — from ZietInvests' company logos to MagnatesMedia's floating brand badges.

**When to use:**
- Alongside a number counter (currency icon, chart icon)
- Marking a company or brand being discussed (logo)
- Signaling a concept (lock = security, globe = international, warning triangle = risk)
- Paired with text overlays for visual anchoring

**Best practices:**
- `size: 48-64` for standalone icons; `size: 24-32` when paired with text
- Position icons to the left of or above their associated text element
- `animation: pop` or `scale_bounce` for entrance — icons should feel snappy
- Use the video's `accent_color` for icon tint; white for neutral contexts
- Never use more than 2 icons visible simultaneously
- Flat/outline style icons only — no 3D, no photorealistic, no emoji

**Best defaults:**
```json
{
  "icon": "trending_up",
  "position": { "x": "center", "y": "center" },
  "size": 48,
  "animation": "pop",
  "color": "#FFFFFF"
}
```

---

### section_divider

Section dividers create structural rhythm. Every channel uses them, but approaches vary from minimal bars to full cinematic title cards.

**Style recommendations:**

| Style | When | Visual Treatment |
|-------|------|-----------------|
| `"minimal_bar"` | Subtle topic shift within a section | Thin horizontal line (2-4px) with label text, `position: "full_width_center"` |
| `"full_card"` | Major chapter/part transition | Full-screen dark background with large numbered label, hold 2-4s |

**Best practices (full_card):**
- `number` + `total_sections` creates "Part 2 of 5" format (NewMoney's listicle structure)
- Large number displayed prominently, label text below in condensed ALL-CAPS
- Dark background (#0A0A0A to #1E2228) with accent color on the number or a decorative element
- `animation_in: fade` with 0.5s duration — section dividers should feel deliberate, not flashy
- Hold for 2-4 seconds — enough to register the transition, not so long it stalls momentum
- Pair with a `sound_effect` (subtle whoosh or low tone) for added impact

**Best practices (minimal_bar):**
- Thin line spanning 60-80% of frame width, centered
- Small label text above or below the line
- `animation_in: wipe` from left to right
- Hold for 1.5-2 seconds

**Best defaults:**
```json
{
  "label": "The Evidence",
  "number": 2,
  "total_sections": 5,
  "style": "full_card",
  "position": "full_width_center"
}
```

---

### zoom_effect

Zoom effects add subtle camera motion to static content. The Ken Burns effect on documents and screenshots is universal across all 6 channels.

**Use cases:**

| Zoom Type | When | Properties |
|-----------|------|-----------|
| `"ken_burns"` | Documents, screenshots, archival photos | `from_scale: 1.0`, `to_scale: 1.1-1.15`, `easing: "ease_in_out"` |
| `"push_in"` | Dramatic emphasis on a key element | `from_scale: 1.0`, `to_scale: 1.3-1.5`, `focal_point` on the key element |
| `"push_out"` | Revealing context after a close-up | `from_scale: 1.3`, `to_scale: 1.0`, `easing: "ease_out"` |
| `"pan_left"` / `"pan_right"` | Scanning across a wide document or infographic | Maintain scale, shift focal point |

**Best practices:**
- Ken Burns is the default for any static visual held longer than 5 seconds — it prevents the frame from feeling dead
- `from_scale` and `to_scale` difference should be subtle (0.1-0.15) — dramatic zooms feel amateurish on documents
- `focal_point` should target the highlighted or narratively important area of the source material
- `easing: "ease_in_out"` for Ken Burns (smooth start and stop); `"ease_out"` for push_in (decelerating for impact)
- Duration matches the hold time of the underlying element — don't zoom faster or slower than the content display

**Best defaults:**
```json
{
  "zoom_type": "ken_burns",
  "from_scale": 1.0,
  "to_scale": 1.12,
  "focal_point": { "x": "center", "y": "center" },
  "easing": "ease_in_out"
}
```

---

### split_screen

Split screens are used sparingly across all channels — they appear for direct comparisons only, never as a layout crutch.

**When to use:**
- A/B comparison of two entities (countries, products, time periods)
- Before/after scenarios
- Bilingual or dual-market content (ZietInvests' English/Chinese search results)

**Best practices:**
- 50/50 split is standard; 60/40 only when one side has significantly more content
- `divider_style: "vs"` for competitive comparisons; `"line"` for neutral side-by-side; `"arrow"` for cause-effect
- Each side needs a clear header (logo, flag, name) — never leave the viewer guessing which side is which
- Color-code the two sides differently (e.g., left = cyan, right = red) and maintain those colors consistently if the comparison recurs
- `animation_in: slide_left` + `slide_right` (panels enter from opposite sides) — the canonical split-screen entrance (NewMoney)
- Hold for 5-10 seconds — comparisons need reading time
- Maximum once per 3-4 minutes of video — overuse dilutes impact

**Best defaults:**
```json
{
  "left": { "label": "Option A", "value": "$1.2M", "color": "#5AC8FA" },
  "right": { "label": "Option B", "value": "$800K", "color": "#FF3B30" },
  "divider_style": "vs",
  "animation_in": "slide_right",
  "animation_out": "fade"
}
```

---

### progress_tracker

Progress trackers orient the viewer within a multi-step process or long-form argument. NewMoney's chapter numbering system and MagnatesMedia's part labels serve this function narratively.

**When to use:**
- Multi-step tutorials or processes
- Video with clear chapter structure (3+ sections)
- Investment analysis with sequential evaluation criteria

**Best practices:**
- `style: "numbered"` for chapter-based content; `"dots"` for process steps; `"bar"` for timeline progress
- Position at top of frame (`position: { x: "center", y: "top" }`) to avoid competing with main content
- Small, unobtrusive — this is structural furniture, not a focal element
- `animation_in: fade` — progress trackers should appear without fanfare
- Update at each step transition, hold briefly (2-3s), then fade
- Only show when the structure adds clarity — videos with 2 sections don't need a tracker

**Best defaults:**
```json
{
  "steps": [
    { "label": "Research", "completed": true },
    { "label": "Analysis", "completed": true },
    { "label": "Verdict", "completed": false }
  ],
  "current_step": 2,
  "style": "numbered",
  "position": { "x": "center", "y": "top" },
  "animation_in": "fade",
  "animation_out": "fade"
}
```

---

### map_highlight

Map highlights are a specialty of Johnny Harris (maps as primary storytelling medium) and ZietInvests (regional data). Used for geographic context in geopolitical, economic, or infrastructure content.

**When to use:**
- Showing where a company/event/policy is located geographically
- Comparing regions or countries
- Illustrating trade routes, supply chains, or territorial changes

**Best practices:**
- Use a pre-rendered map image (`image_path`) with topographic texture — flat vector maps look cheap (Johnny Harris)
- `highlights` array to mark specific regions with colored overlays and labels
- Color-code regions using flag-derived desaturated tones (e.g., India: #D08040, China: #C04060) (Johnny Harris)
- Labels positioned at actual geographic locations of the regions they describe
- `animation_in: fade` for the base map, then sequential highlight reveals
- Source citation ("SOURCE: [Name]") in lower-left corner, white ALL-CAPS sans-serif (Johnny Harris)
- Full-bleed composition — maps fill the entire frame edge-to-edge

**Best defaults:**
```json
{
  "image_path": "/path/to/map.png",
  "highlights": [
    { "x": 200, "y": 150, "width": 100, "height": 80, "label": "Region A", "color": "#D08040" },
    { "x": 400, "y": 200, "width": 120, "height": 90, "label": "Region B", "color": "#C04060" }
  ],
  "position": { "x": "center", "y": "center" },
  "scale": 1.0,
  "animation_in": "fade",
  "animation_out": "fade"
}
```

---

### transition

Transitions are minimal across all 6 channels. Hard cuts dominate. Creative transitions are reserved for major structural shifts.

**When to use:**
- Between major video sections/chapters (not between individual shots)
- Entering or exiting a data-heavy sequence
- Marking a significant narrative shift (past to present, setup to evidence)

**Transition hierarchy (most to least used):**

| Type | Frequency | When |
|------|-----------|------|
| Hard cut (no transition) | 85-90% of all cuts | Default — between any two shots |
| `"dissolve"` | 5-8% | Between major sections, presenter to graphic |
| `"wipe"` | 2-3% | Entering a data sequence or timeline |
| `"zoom_through"` | 1-2% | Dramatic reveals only (MagnatesMedia) |
| `"whip"` / `"swish"` | <1% | Almost never — too flashy for this tier |

**Best practices:**
- Default to NO transition (hard cut). Only add a transition when there is a specific structural reason.
- `"dissolve"` with `speed: "normal"` is the safe choice for any section boundary
- `"wipe"` with `direction: "right"` for entering timelines or progressive data reveals
- Never use `"whip"` or `"swish"` in analytical/documentary content — these belong in entertainment edits
- Fade-to-black (1-2s of pure black) is a powerful narrative punctuation used by James Jani and MagnatesMedia between story chapters — implement as a `"dissolve"` to a black frame

**Best defaults:**
```json
{
  "transition_type": "dissolve",
  "direction": "right",
  "speed": "normal"
}
```

---

### sound_effect

Sound effects are paired with visual elements to reinforce impact. Used selectively — audio clutter is worse than visual clutter.

**Pairing rules:**

| Visual Element | Recommended SFX | Volume | Timing |
|----------------|-----------------|--------|--------|
| `section_divider` (full_card) | `"whoosh_soft"` or `"low_tone"` | 0.3-0.4 | Synced with entrance |
| `number_counter` (large reveal) | `"impact_hit"` | 0.3-0.5 | On final number landing |
| `text_overlay` (dramatic stat) | `"impact_hit"` or `"bass_drop"` | 0.2-0.4 | On text appearance |
| `data_viz` (bar growth) | `"rising_tone"` | 0.15-0.25 | During animation |
| `callout_box` (warning) | `"alert_tone"` | 0.2-0.3 | On entrance |
| `transition` (section break) | `"whoosh_soft"` | 0.3 | During transition |
| Generic entrance | `"pop"` or `"click"` | 0.15-0.2 | On element appearance |

**Best practices:**
- Volume should NEVER exceed 0.5 — sound effects support, they don't dominate
- SFX leads the visual by 2-3 frames (human auditory processing is faster than visual)
- Maximum 1 sound effect per enhancement — never stack audio
- Silence is powerful. Not every graphic needs a sound. Reserve SFX for key moments.
- All 6 channels use animation and sound purposefully, not decoratively — this is the most important principle

**Best defaults:**
```json
{
  "sfx_id": "whoosh_soft",
  "volume": 0.3
}
```

---

### image_overlay

Image overlays display pre-rendered graphics, logos, photos, or illustrations on top of the video. Used for company logos, product images, portrait photos, and custom illustrations.

**When to use:**
- Company/brand logo alongside a discussion about that entity
- Person photo when discussing someone not on screen
- Custom illustration or infographic element
- Physical prop or evidence image

**Best practices:**
- `width` and `height` should maintain aspect ratio — never stretch images
- `position: { x: "right", y: "top_third" }` for logos alongside presenter; `{ x: "center", y: "center" }` for full-frame images
- Slight drop shadow or dark border for images on varied backgrounds
- `animation_in: fade` for most cases; `scale_bounce` for logo reveals
- `animation_out: fade` at 0.3s
- Hold for 3-8 seconds — same as text overlay timing
- For "photo card on canvas" effect (ZietInvests): slight rotation (~2-5 degrees), drop shadow, on a textured background
- For portrait gallery layouts (James Jani, MagnatesMedia): metallic or decorative frame, dark textured background, evenly spaced

**Best defaults:**
```json
{
  "image_path": "/path/to/image.png",
  "position": { "x": "center", "y": "center" },
  "width": 400,
  "height": 300,
  "animation_in": "fade",
  "animation_out": "fade"
}
```

---

## Part 2: Design System

### Color Palette

**Recommended accent colors (observed across all 6 channels):**

| Color | Hex | Role | Used By |
|-------|-----|------|---------|
| Signal Red | `#FF3B30` | Negative values, danger, alarm, emphasis | Damien, MagnatesMedia, NewMoney |
| Growth Green | `#4ADE4A` | Positive values, gains, success | Damien, MagnatesMedia |
| Neon Green | `#39FF14` | Highlight segments, key periods | Damien (signature) |
| Highlight Yellow | `#FFFF00` | Document highlights, evidence marking | ZietInvests, James Jani |
| Brand Gold | `#FFD700` | Premium accent, brand elements | NewMoney, ZietInvests |
| Cyan/Teal | `#5AC8FA` | Data lines, positive values, tech | Damien, NewMoney, James Jani |
| Deep Red/Crimson | `#CC0000` | Key word emphasis, ribbon banners | NewMoney, MagnatesMedia |
| Warm Amber | `#D4A040` | Warm accents, historical elements | Johnny Harris, James Jani |

**Color pairing rules:**
- Maximum 2 accent colors per graphic element (NewMoney rule — applies universally)
- Dark backgrounds (#1E2228 to #0A0A0A) get white text ONLY — never colored body text on dark
- Light backgrounds (#F2F2F2 to #F5F0E8) get black/dark text ONLY
- Red + cyan is the universal positive/negative pair for financial data
- Yellow is for highlighting/emphasis only — never as a primary data color
- One accent color should dominate per video (Johnny Harris' single-accent discipline)

**Semantic color rules (universal patterns):**
- Green = growth, positive, protagonist, info
- Red = decline, negative, danger, antagonist
- Yellow/Gold = emphasis, highlight, evidence, premium
- Cyan/Teal = data, neutral information, technology
- White = editorial voice, narrator's annotation
- Gray = source citations, secondary info, benchmarks

**Dark mode vs. light mode:**
- Dark mode (#1E2228 or darker) for data visualization, narrative graphics, dramatic moments
- Light mode (#F2F2F2 or #F5F0E8) for structural elements (section cards, educational explainers, definition cards)
- Never mix modes within a single graphic — pick one per element
- ZietInvests and NewMoney both use dual-mode systems with clear purpose separation

---

### Typography

**Font recommendations:**
- **Primary (headings, labels, data)**: Clean geometric sans-serif — Inter, DM Sans, Montserrat, or Barlow. Used by 5 of 6 channels.
- **Condensed variant (titles, section dividers)**: Barlow Condensed, Oswald, or Bebas Neue. ALL-CAPS always.
- **Serif (rare — definition cards, editorial quotes)**: Playfair Display or EB Garamond. Used by NewMoney and James Jani for specific card types only.
- **Monospace (tech/terminal contexts only)**: JetBrains Mono or similar. Reserved for code, hacking, or technical UI mockups (MagnatesMedia, James Jani).

**Size hierarchy at 1080p (font_size values for Remotion):**

| Level | font_size | Weight | Case | Usage |
|-------|-----------|--------|------|-------|
| Display / Impact | 72-120 | 900 (Black) | ALL-CAPS | Frame-filling statistics, dramatic reveals |
| H1 / Primary | 48-64 | 700 (Bold) | ALL-CAPS | Chart titles, section headings, key figures |
| H2 / Secondary | 32-42 | 600 (Semi-bold) | Title Case or ALL-CAPS | Subheadings, data labels, name plates |
| Body | 20-28 | 400 (Regular) | Sentence case | Explanatory text, callout box content |
| Caption | 14-18 | 400 (Regular) | Sentence case | Source citations, axis labels, disclaimers |
| Micro | 10-12 | 400 (Regular) | Sentence case | Legal disclaimers, fine print |

**Weight usage rules:**
- Bold (700+) for ALL headings, labels, and numbers — never use regular weight for emphasis elements
- Regular (400) for body text and supporting information ONLY
- No thin/light weights anywhere in video graphics — they are illegible on screens
- Extra-bold (800-900) reserved for display-level statistics and dramatic moments

**Emphasis techniques (ranked by frequency across channels):**
1. Color shift on keywords — red or accent_color for the key term within a white heading (NewMoney, Damien)
2. Yellow background highlight behind key phrases in documents (ZietInvests, James Jani)
3. ALL-CAPS for headings, sentence case for body — the case difference itself creates hierarchy
4. Size contrast — key number 3-5x larger than its label (universal)

---

### Animation DNA

**Preferred entrance animations per element type:**

| Element | animation_in | Duration | Easing |
|---------|-------------|----------|--------|
| text_overlay | `slide_up` or `fade` | 0.3-0.5s | `ease_out` |
| lower_third | `slide_up` | 0.3s | `ease_out` |
| data_viz (bars) | `build_up` | 1.0-2.0s | `ease_out` |
| data_viz (lines) | `wipe` | 1.5-3.0s | `linear` |
| number_counter | `fade` | 0.3s (then count 1-2s) | `ease_out` |
| source_overlay | `fade` | 0.5s | `ease_in_out` |
| callout_box | `fade` + subtle scale (0.95-1.0) | 0.4s | `ease_out` |
| animated_list | `slide_right` (sequential) | 0.3s per item | `ease_out` |
| section_divider | `fade` | 0.5s | `ease_in_out` |
| icon_accent | `pop` or `scale_bounce` | 0.2-0.3s | `spring` |
| image_overlay | `fade` | 0.4s | `ease_in_out` |
| split_screen | `slide_left` / `slide_right` | 0.4s | `ease_out` |

**Exit animations:**
- `fade` at 0.3s is the universal safe exit for ALL element types
- Hard cuts (no exit animation) are also acceptable — NewMoney and James Jani both use hard cuts to exit graphics
- Never use bouncy/spring exits — they feel unserious in analytical content
- Exit should never draw more attention than the entrance

**Timing conventions:**

| Metric | Value | Notes |
|--------|-------|-------|
| Entrance duration | 0.3-0.5s | 10-15 frames at 30fps |
| Hold (text) | 3-8s | ~250ms per word minimum |
| Hold (data viz) | 5-15s | Complex charts need reading time |
| Hold (section divider) | 2-4s | Just enough to register |
| Exit duration | 0.2-0.3s | Quick — don't linger |
| Gap between enhancements | 0.5-1.0s | Brief breathing room |

**Easing preferences:**
- `ease_out` for entrances (elements decelerate into position — feels natural and weighty)
- `ease_in_out` for slow camera moves (Ken Burns, gentle pans)
- `spring` for icon_accent and pop-in elements ONLY — never for text or data
- `linear` for line-draw animations on charts (constant speed feels like real drawing)
- Never use `ease_in` for entrances — elements that accelerate into view feel clunky

**Stagger patterns for multi-element reveals:**
- `stagger_frames: 10-15` (0.3-0.5s) between related elements (e.g., bars in a chart)
- `stagger_frames: 6-8` (0.2-0.3s) for cascading list items
- Build order: background/container first, then primary data, then annotations/callouts last (Damien's pattern)

---

### Layout System

**Screen zone map:**

```
+--------------------------------------------------+
|  SOURCE CITATION          |     SOURCE CITATION   |
|  (top-left, rare)         |     (top-right)       |
|                                                    |
|        TEXT OVERLAYS / SECTION DIVIDERS            |
|        (top_third: y = 25-35%)                    |
|                                                    |
|                                                    |
|            MAIN CONTENT ZONE                       |
|      (center: data_viz, image_overlay,            |
|       source_overlay, split_screen)               |
|                                                    |
|                                                    |
|        CALLOUT BOXES / NUMBER COUNTERS            |
|        (bottom_third: y = 65-75%)                 |
|                                                    |
|  LOWER THIRDS            |     ICON ACCENTS       |
|  (bottom_left)           |     (flexible)         |
+--------------------------------------------------+
```

**Safe zones (never cover):**
- Presenter's face: typically center frame, y = 20-50% in medium close-up
- When presenter is visible, place overlays in upper-left, upper-right, or lower corners ONLY
- Bottom 10% of frame: reserved for subtitles/captions — no enhancements here
- Top 5% of frame: may be cropped by some players — keep critical content below

**Full-frame graphic convention (universal across all 6 channels):**
- Graphics and presenter NEVER share the frame in complex compositions
- The video alternates: full-frame presenter → full-frame graphic → full-frame presenter
- Exception: small overlays on presenter (price callout, icon accent) positioned in safe corners — maximum 1-2 per video
- This strict separation creates clear cognitive rhythm: "explanation mode" vs "evidence mode" (ZietInvests)

**Margin conventions:**
- Content centered with ~10-15% margin on each side for full-frame graphics
- Source citations: 20-30px from frame edges
- Chart elements: 15% left margin, 10% right margin, 10% top/bottom margin
- Text overlays: never extend past 70% of frame width to maintain readable line lengths

**Layering rules:**
- Maximum 3 simultaneous visual layers: (1) background/video, (2) primary graphic, (3) annotation/callout
- Never stack more than 2 text-based elements simultaneously
- Source citation is always the top layer (never obscured by other graphics)

---

### Enhancement Density

**Target density by video section:**

| Section | Enhancements per 30s | Hold Duration | Notes |
|---------|---------------------|---------------|-------|
| Hook (0-30s) | 2-3 | 3-5s each | Front-load visual interest to retain viewers |
| Intro (30s-2min) | 1-2 | 4-6s each | Establish the topic, introduce key visual language |
| Body (data segments) | 2-4 | 5-15s each | Dense graphics clusters during evidence/data (Damien, ZietInvests) |
| Body (narrative segments) | 0-1 | 5-8s | Let b-roll and presenter carry the weight (James Jani, Johnny Harris) |
| Conclusion | 0-1 | 4-6s | Presenter-heavy, minimal graphics (universal) |

**Overall targets (based on channel averages):**
- 1 custom graphic element every 45-90 seconds (Damien and ZietInvests pace)
- Graphics occupy 30-50% of total screen time (NOT 80-100% — that's MagnatesMedia's no-presenter format which doesn't apply to our pipeline)
- Talking head with zero overlays should occupy 20-30% of screen time (breathing room)
- B-roll without overlays should occupy 15-25% of screen time

**Distribution pattern:**
- Graphics cluster in data/evidence segments (3-5 consecutive graphic frames)
- Clean talking-head breathing room between clusters (2-4 unadorned shots)
- Conclusion is presenter-heavy, data argument is front-loaded (Damien pattern)
- Never run more than 90 seconds of continuous graphics without a presenter or b-roll break

**Hold duration guidelines by element type:**

| Element | Min Hold | Max Hold | Sweet Spot |
|---------|----------|----------|------------|
| text_overlay | 2s | 8s | 3-5s |
| lower_third | 4s | 8s | 5-6s |
| data_viz | 5s | 20s | 8-12s |
| number_counter | 2s | 5s | 3s |
| source_overlay | 5s | 15s | 8-10s |
| callout_box | 3s | 8s | 5-6s |
| section_divider | 2s | 4s | 2.5-3s |
| animated_list | 4s | 15s | Depends on item count: 3s per item |
| split_screen | 5s | 12s | 7-8s |
| image_overlay | 3s | 10s | 5-6s |

---

### Sound Design (Based on Spectrogram Analysis of 60 Videos)

Sound design data derived from spectral analysis of 10 videos each from ZietInvests,
NewMoney, DamienTalksMoney, MagnatesMedia, James Jani, and Johnny Harris.

#### SFX Density Spectrum (events/minute)

| Channel | Avg SFX/min | Hook (0-30s) | Body | Style |
|---------|-------------|-------------|------|-------|
| ZietInvests | ~0 | 0 | 0 | Zero SFX — voice + music bed only |
| Damien | 1.5-2 | 5-7 | 1-1.5 | Whoosh-dominant, silence-transition rhythm |
| NewMoney | 2-3 | 3-4 | 1.5-2 | Strategic silence, minimal discrete SFX |
| James Jani | 2-3 | varies | 2-3 | Music-driven, cold opens from silence |
| MagnatesMedia | 4-7 | 8-10 | 3-4 | Highest density, dramatic stingers |
| Johnny Harris | 6-10 | 8-12 | 4-6 | Cinematic layering, 3-4 audio layers |

**Recommended target for our channel: 2-4 SFX/min** (matches the finance/explainer
sweet spot between Damien and MagnatesMedia). Higher in hooks (4-6/min), lower in
body sections (1.5-3/min).

#### Signature Audio Techniques (Observed Across All 6 Channels)

1. **Continuous music bed** (6/6 channels) — Background music runs start to finish
   in every video analyzed. Never drops out completely during body sections. Duck
   -6dB under narration, surface in speech gaps.

2. **Silence as SFX** (5/6 channels) — Deliberate 0.5-5s full audio dropouts used
   as dramatic punctuation. Most powerful before reveals.
   - NewMoney: "NewMoney Pause" — 2-4s silence after provocative hook statement (8/10 videos)
   - MagnatesMedia: 1-5s silence gap → broadband stinger hit (10/10 videos)
   - James Jani: Cold opens with up to 25s silence (6/10 videos)
   - Damien: "Speech → silence → whoosh → speech" rhythm at every section boundary

3. **Front-loaded SFX density** (5/6 channels) — Hook section (0-30s) has 2-4x
   the SFX density of body sections. Multiple rapid SFX in the first 10-15 seconds.

4. **Outro music swell** (5/6 channels) — Music bed increases in volume and spectral
   richness in the final 30-60s for a strong close.

5. **Genre-matched music beds** (3/6 channels) — MagnatesMedia, James Jani, and
   Johnny Harris use different music moods per video topic (dark for crime,
   modern/pulsing for tech, warm for positive stories, tension for geopolitics).

6. **Pull-back-to-hit** (Johnny Harris signature) — 0.5-2s energy dip immediately
   before key reveals, then a full-spectrum impact hit.

7. **Energy wave pattern** (James Jani signature) — Music bed intensity follows
   2-4 minute tension-release cycles aligned with narrative chapter arcs.

#### SFX Pairing Rules (Updated with Real Data)

| Enhancement Type | SFX Trigger | Recommended sfx_id | Volume |
|-----------------|-------------|-------------------|--------|
| section_divider (full_card) | On entrance | `"whoosh"` | 0.3 |
| section_divider (minimal_bar) | On entrance | `"whoosh_soft"` | 0.2 |
| number_counter (big reveal) | When counter lands | `"impact"` | 0.35 |
| text_overlay (dramatic) | On text appearance | `"impact"` | 0.25 |
| text_overlay (info) | On text appearance | `"pop"` | 0.15 |
| data_viz (bar chart) | During bar growth | `"whoosh_soft"` | 0.2 |
| data_viz (line chart) | During line draw | None — silence | 0 |
| callout_box (warning) | On entrance | `"notification"` | 0.25 |
| callout_box (insight) | On entrance | `"ding"` | 0.2 |
| icon_accent | On pop-in | `"pop"` | 0.15 |
| transition (any) | During transition | `"swoosh"` | 0.25 |
| source_overlay | On entrance | `"whoosh_soft"` or None | 0.15 |
| animated_list (per item) | On each item reveal | `"click"` | 0.1 |
| split_screen | On entrance | `"whoosh"` | 0.25 |

**When to use silence instead of SFX:**
- Before a major reveal: 1-3s silence gap, then `"impact"` on the reveal
- Source overlays showing articles/documents: no SFX (let the content speak)
- Data viz line charts: silence — the visual is enough
- Between closely-spaced overlays (< 2s apart): skip SFX on the second one

#### Timing Rules

- SFX should trigger 2-3 frames BEFORE the visual element appears (audio primes attention)
- One SFX per enhancement maximum — never layer multiple sounds on one element
- Minimum 1.5 seconds between consecutive SFX events in body sections
- In hooks (first 15s), SFX can be as close as 0.5s apart
- Background music should duck -6dB when SFX fires
- Silence gaps: place at section boundaries, 0.5-2s duration, followed by a transition SFX

#### Volume Guidelines

- SFX should NEVER be louder than the narration voice
- Range: 0.1 (barely perceptible) to 0.5 (prominent accent)
- Most SFX: 0.15-0.25 (supportive, not distracting)
- `"impact"` on major reveals: 0.35-0.5
- `"pop"` and `"click"` on list items/small reveals: 0.1-0.15
- Music bed: 0.15-0.25 under narration, 0.3-0.4 during transitions/intros

#### Music Bed Guidelines

Based on analysis of all 60 videos, music bed usage is universal and follows
consistent patterns:

- **Always present**: Continuous background music from start to finish
- **Style**: Low-energy ambient/cinematic instrumental (warm pads, subtle strings,
  lo-fi electronic). Should not compete with narration.
- **Frequency range**: Primarily 100-500Hz, with some mid-range warmth up to 2kHz
- **Dynamic mixing**: Louder in hook (first 15-30s) and outro (last 30-60s), quiet
  in body sections, surface in speech gaps
- **Mood matching**: Adapt music cue to topic tone:
  - Financial analysis: neutral ambient pad
  - Investigative/scandal: dark, tension-building drone
  - Growth/success stories: warm, slightly melodic
  - Geopolitical: restrained tension with sub-bass presence
- **Section transitions**: Music swells 3-5s at section boundaries before settling
  into the next section's mood

#### SFX Library Requirements

Based on spectrogram analysis, these are the specific sound categories needed.
Each row describes the sound character observed across the reference channels:

| Category | Priority | Variants | Character Description |
|----------|----------|----------|----------------------|
| **Whoosh/swoosh** | Critical | 3 (soft, medium, reverse) | Clean broadband sweep, 0.3-0.5s. Primary transition SFX. Damien's most-used sound. |
| **Impact/hit** | Critical | 3 (light, medium, cinematic) | Full-spectrum transient < 0.3s. For reveals, emphasis. MagnatesMedia/Harris signature. |
| **Pop/click** | High | 2 (pop, click) | Ultra-short burst. For text appearances, list items, small reveals. |
| **Music beds** | Critical | 5+ moods | Ambient/cinematic loops (2-5 min). Neutral, tension, warm, dark, upbeat. Must duck cleanly under speech. |
| **Tension riser** | High | 2 (short 2s, long 5s) | Upward frequency sweep building anticipation. Used before reveals. |
| **Ding/chime** | Medium | 2 (bright, warm) | Clean tonal hit at specific frequency, decays. For positive emphasis, data reveals. |
| **Sub-bass drone** | Medium | 2 (tension, neutral) | Sustained low-frequency (30-100Hz) atmospheric layer. Harris/MagnatesMedia use. |
| **Swoosh/transition** | Medium | 2 (fast, slow) | Section-change sound, broader than whoosh. For scene breaks. |
| **Musical stinger** | Medium | 3 (dramatic, neutral, upbeat) | Short (1-2s) musical phrase. For major section transitions. |
| **Notification/alert** | Low | 1 | Bright tonal ping. For callout boxes, warnings. |
| **Silence/room tone** | Low | 1 | Very subtle ambient hum for "silence" sections (not true digital silence). |

**Total minimum SFX library: ~25-30 individual sound files across 11 categories.**

---

## Part 3: Remotion Defaults

### Recommended GlobalStyle

```json
{
  "font_family": "Inter",
  "accent_color": "#5AC8FA",
  "secondary_color": "#FF3B30",
  "text_color": "#FFFFFF",
  "background_opacity": 0.85
}
```

**Notes:**
- `accent_color` and `secondary_color` should be adjusted per video to match the topic's tone. The defaults above work for financial/analytical content.
- For investigative/scandal content: `accent_color: "#FF3B30"`, `secondary_color: "#FFD700"`
- For growth/positive content: `accent_color: "#4ADE4A"`, `secondary_color: "#5AC8FA"`
- For geopolitical content: `accent_color: "#D03050"`, `secondary_color: "#D4A040"`
- `background_opacity: 0.85` provides readable dark overlays while keeping some video texture visible

---

### Default Properties Per Enhancement Type

#### text_overlay
```json
{
  "text": "",
  "style": "highlight",
  "position": { "x": "center", "y": "top_third" },
  "font_size": 36,
  "color": "#FFFFFF",
  "animation_in": "slide_up",
  "animation_out": "fade"
}
```

#### lower_third
```json
{
  "name": "",
  "title": "",
  "position": "bottom_left",
  "animation_in": "slide_up",
  "animation_out": "fade"
}
```

#### source_overlay
```json
{
  "screenshot_path": "",
  "headline": "",
  "highlight_regions": [],
  "position": { "x": "center", "y": "center" },
  "scale": 0.75,
  "animation_in": "fade",
  "animation_out": "fade"
}
```

#### zoom_effect
```json
{
  "zoom_type": "ken_burns",
  "from_scale": 1.0,
  "to_scale": 1.12,
  "focal_point": { "x": "center", "y": "center" },
  "easing": "ease_in_out"
}
```

#### sound_effect
```json
{
  "sfx_id": "whoosh_soft",
  "volume": 0.3
}
```

#### section_divider
```json
{
  "label": "",
  "style": "full_card",
  "position": "full_width_center"
}
```

#### data_viz
```json
{
  "chart_type": "bar",
  "title": "",
  "data": [],
  "position": { "x": "center", "y": "center" },
  "scale": 0.85,
  "animation_in": "build_up",
  "animation_out": "fade"
}
```

#### icon_accent
```json
{
  "icon": "",
  "position": { "x": "center", "y": "center" },
  "size": 48,
  "animation": "pop",
  "color": "#FFFFFF"
}
```

#### callout_box
```json
{
  "text": "",
  "style": "insight",
  "position": { "x": "right", "y": "bottom_third" },
  "animation_in": "fade",
  "animation_out": "fade"
}
```

#### animated_list
```json
{
  "items": [],
  "reveal_style": "sequential",
  "stagger_frames": 90,
  "position": { "x": "center", "y": "center" },
  "animation_in": "slide_right",
  "animation_out": "fade"
}
```

#### number_counter
```json
{
  "from": 0,
  "to": 0,
  "prefix": "",
  "suffix": "",
  "title": "",
  "font_size": 56,
  "color": "#FFFFFF",
  "position": { "x": "center", "y": "center" },
  "animation_in": "fade",
  "animation_out": "fade"
}
```

#### split_screen
```json
{
  "left": { "label": "", "value": "", "color": "#5AC8FA" },
  "right": { "label": "", "value": "", "color": "#FF3B30" },
  "divider_style": "vs",
  "animation_in": "slide_right",
  "animation_out": "fade"
}
```

#### progress_tracker
```json
{
  "steps": [],
  "current_step": 0,
  "style": "numbered",
  "position": { "x": "center", "y": "top" },
  "animation_in": "fade",
  "animation_out": "fade"
}
```

#### map_highlight
```json
{
  "image_path": "",
  "highlights": [],
  "position": { "x": "center", "y": "center" },
  "scale": 1.0,
  "animation_in": "fade",
  "animation_out": "fade"
}
```

#### transition
```json
{
  "transition_type": "dissolve",
  "direction": "right",
  "speed": "normal"
}
```

#### image_overlay
```json
{
  "image_path": "",
  "position": { "x": "center", "y": "center" },
  "width": 400,
  "height": 300,
  "animation_in": "fade",
  "animation_out": "fade"
}
```

---

### Do's and Don'ts

#### DO

1. **Alternate between presenter and graphics in strict separation.** Graphics get their own full-frame moment. The presenter gets clean, uncluttered screen time. This is the single most consistent pattern across all 6 channels and the foundation of professional YouTube editing.

2. **Lead with data, annotate with insight.** Show the chart first, let it breathe for 2-3 seconds, THEN add the callout box or annotation with the key takeaway. Damien's dark annotation bubble pattern is the gold standard: data reveals first, editorial voice second.

3. **Use source citations on every single piece of external data.** "Source: [Name]" in small gray text, positioned in the top-right or bottom-right corner. This is non-negotiable across all 6 channels. No exceptions.

4. **Color-code semantically and consistently.** Green = positive, red = negative, yellow = highlight/emphasis. Pick your accent colors at the start and maintain them throughout the entire video. Never introduce a new color for the same meaning mid-video.

5. **Match animation to purpose.** Data bars grow upward (build_up). Lines draw left-to-right (wipe). Text slides in (slide_up). Icons pop in (pop). Each element type has a natural animation — use it consistently.

6. **Create breathing room.** After every cluster of 3-5 graphics, return to 2-4 shots of clean presenter or unadorned b-roll. The contrast between "nothing" and "everything" is itself a design choice (NewMoney's clean talking head philosophy).

7. **Use the Ken Burns effect on any static visual held longer than 5 seconds.** Subtle zoom (1.0 to 1.12) prevents the frame from feeling dead. Universal across all channels for documents, screenshots, and archival photos.

8. **Keep text overlays under 15 words.** If you need more text, use a callout_box or source_overlay. Text overlays are for punchy phrases, not paragraphs.

9. **Highlight surgically.** When marking text in a document, highlight ONLY the critical 3-7 words, not the whole paragraph. James Jani's precision highlighting is the benchmark.

10. **Pair number_counter with context.** A number alone means nothing. Always include a `title` (what the number is) and ideally a `subtitle` (comparison point or time period).

#### DON'T

1. **Never overlay complex graphics on the presenter.** The presenter's frame should have zero visual clutter (universal across all 6 channels). Exception: one small corner callout (price, logo) maximum 1-2 times per video.

2. **Never use more than 2 accent colors per graphic element.** NewMoney's discipline of maximum-2 accent colors per frame is the rule. A third color creates visual noise.

3. **Never use bouncy/spring animations for text or data.** Spring easing is only appropriate for icon_accent elements. Text and data should use ease_out — weighty and deliberate, not playful.

4. **Never run continuous graphics for more than 90 seconds without a visual break.** Even MagnatesMedia (100% graphics density) varies the intensity with different graphic types. For presenter-based channels, return to the talking head.

5. **Never use whip/swish transitions in analytical content.** These feel like TikTok edits, not documentary journalism. Dissolves and hard cuts only.

6. **Never stack multiple callout boxes or annotations.** One editorial annotation per chart. If you need to make multiple points, show the chart multiple times with different annotations (NewMoney's progressive chart reveal technique).

7. **Never leave a data graphic without a source citation.** Even if the data is obvious (e.g., a stock price), cite where it came from. This is table-stakes credibility for financial content.

8. **Never use decorative animations (particle effects, confetti, continuous loops).** Animation serves clarity, not spectacle. Once an element is revealed, it should be static. (Universal across all 6 channels except MagnatesMedia's cinematic 3D, which is not applicable to our pipeline.)

9. **Never place text below y: 90% of frame.** This zone is reserved for subtitles/captions and will be obscured on many playback platforms.

10. **Never introduce an enhancement type that doesn't advance understanding.** If removing a graphic doesn't hurt the viewer's comprehension, remove it. Every element must earn its screen time. This philosophy of purposeful restraint is the defining characteristic shared by all 6 channels studied.

---

## Ad Read / Sponsor Segment Styling

During ad-read segments, add a **progress line** — a thin horizontal bar at the very bottom of the frame that fills left-to-right over the ad segment duration. Color must **match the sponsor's brand color**.

---

## Appendix: Channel-Specific Techniques Worth Adopting

These are standout techniques from individual channels that are worth incorporating when the content type matches:

| Technique | Source Channel | When to Use | Remotion Implementation |
|-----------|---------------|-------------|------------------------|
| Yellow evidence highlighting | ZietInvests | Financial documents, legal filings | `source_overlay` with `highlight_regions` + yellow (#FFFF00) overlay |
| Dark annotation bubbles | Damien | Key takeaway on any chart | `callout_box` style `"insight"` with semi-transparent dark bg |
| Progressive chart reveals | NewMoney, Damien | Building narrative tension with data | Show `data_viz` twice — first partial, then complete with annotation |
| Color-segment line highlighting | Damien | Isolating a key period on a time series | Two-color `data_viz` with accent on the highlighted segment |
| Desaturation as temporal marker | ZietInvests | "This was the past" or "this didn't last" signals | Apply grayscale treatment to archival `image_overlay` |
| Yellow subtitles for translations | Johnny Harris | Translated speech, foreign language quotes | `text_overlay` with `color: "#F0D020"`, italic, bottom-center |
| Semantic color grading | MagnatesMedia | Shifting narrative modes (drama vs. education) | Adjust `accent_color` warmth between sections |
| Physical document highlight animation | James Jani | Revealing evidence in a document | `source_overlay` with `highlight_regions` + `zoom_effect` ken_burns |
| Benchmark bar styling | Damien | Comparative bar charts with a reference point | One bar in `data_viz` with `color: "#888888"` as benchmark |
| Frame-filling impact numbers | James Jani | Dramatic price/value reveals | `number_counter` with `font_size: 96-120`, centered, nothing else on screen |
