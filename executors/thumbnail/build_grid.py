#!/usr/bin/env python3
"""Combine thumbnail images into a labeled grid and run mobile QA.

Usage:
    # Standard 2x2 concept grid (backward-compatible):
    python3 executors/thumbnail/build_grid.py \\
        concept_A.png concept_B.png concept_C.png concept_D.png \\
        output_grid.png

    # Large research grid (numbered, no QA):
    python3 executors/thumbnail/build_grid.py \\
        thumb_01.jpg thumb_02.jpg ... thumb_20.jpg \\
        research_grid.png \\
        --cols 4 --label-style number --skip-qa

The last positional argument is always the output path.
All preceding positional arguments are input images (2+).

Requires: pip install Pillow
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

THUMB_W = 1280
THUMB_H = 720
MOBILE_W = 320
MOBILE_H = 180
WCAG_AA_RATIO = 4.5


def relative_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance per WCAG 2.0 formula."""
    def linearize(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(l1: float, l2: float) -> float:
    """Calculate contrast ratio between two luminance values."""
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def sample_region_luminance(image, x: int, y: int, w: int, h: int) -> float:
    """Calculate average luminance of a region in the image."""
    # Clamp to image bounds
    x = max(0, min(x, image.width - 1))
    y = max(0, min(y, image.height - 1))
    w = min(w, image.width - x)
    h = min(h, image.height - y)

    if w <= 0 or h <= 0:
        return 0.0

    region = image.crop((x, y, x + w, y + h))
    pixels = list(region.getdata())
    if not pixels:
        return 0.0

    total = sum(relative_luminance(p[0], p[1], p[2]) for p in pixels)
    return total / len(pixels)


def heuristic_text_region(image) -> tuple[int, int, int, int]:
    """Heuristic: assume text is in the top-left quadrant (common placement)."""
    return (40, 40, image.width // 2 - 40, image.height // 3)


def run_qa(image, text_region: dict | None, original_font_size: int = 72) -> dict:
    """Run mobile readability QA on a single thumbnail image."""
    # Determine text bounding box
    if text_region:
        tx, ty = text_region["x"], text_region["y"]
        tw, th = text_region["width"], text_region["height"]
    else:
        tx, ty, tw, th = heuristic_text_region(image)

    # Sample text region luminance (assume white text → luminance ~1.0)
    text_lum = 1.0  # white text assumption
    bg_lum = sample_region_luminance(image, tx, ty, tw, th)
    ratio = contrast_ratio(text_lum, bg_lum)

    # Check mobile-size font legibility
    # Scale factor from 1280 → 320 = 0.25
    scale = MOBILE_W / THUMB_W
    mobile_font_px = original_font_size * scale
    mobile_readable = mobile_font_px >= 12

    return {
        "contrast_ratio": round(ratio, 1),
        "contrast_pass": ratio >= WCAG_AA_RATIO,
        "mobile_font_px": round(mobile_font_px, 1),
        "mobile_readable": mobile_readable,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Combine thumbnail images into a labeled grid with optional mobile QA."
    )
    parser.add_argument("images", nargs="+",
                        help="Input images followed by output path (last arg is output)")
    parser.add_argument("--text-regions", type=str, default=None,
                        help="JSON array of text bounding boxes [{x,y,width,height}, ...] from composite.py")
    parser.add_argument("--font-size", type=int, default=72,
                        help="Original font size used in compositing (for mobile QA)")
    parser.add_argument("--cols", type=int, default=None,
                        help="Number of columns (default: 2 for <=4 images, 4 for >4)")
    parser.add_argument("--label-style", choices=["letter", "number"], default="letter",
                        help="Label style: 'letter' (A,B,C,D) or 'number' (1,2,3,...)")
    parser.add_argument("--skip-qa", action="store_true",
                        help="Skip mobile QA and contrast checks (for research grids)")
    args = parser.parse_args()

    start = time.time()

    # Check Pillow
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print(json.dumps({
            "status": "error",
            "error": "Pillow not installed. Install with: pip install Pillow",
        }))
        sys.exit(1)

    # Parse args: last is output, rest are input images
    if len(args.images) < 3:  # minimum: 2 inputs + 1 output
        print(json.dumps({
            "status": "error",
            "error": "Need at least 2 input images and 1 output path. Usage: build_grid.py img1 img2 [...] output.png",
        }))
        sys.exit(1)

    output_path = args.images[-1]
    input_paths = args.images[:-1]

    # Cap at 25 images to keep grid manageable
    if len(input_paths) > 25:
        input_paths = input_paths[:25]

    # Parse text regions if provided
    text_regions = None
    if args.text_regions:
        try:
            text_regions = json.loads(args.text_regions)
        except json.JSONDecodeError:
            text_regions = None

    # Validate inputs exist
    for p in input_paths:
        if not os.path.isfile(p):
            print(json.dumps({"status": "error", "error": f"Image not found: {p}"}))
            sys.exit(1)

    # Load and resize all images to standard thumbnail size
    images = []
    for p in input_paths:
        img = Image.open(p).convert("RGB")
        if img.size != (THUMB_W, THUMB_H):
            img = img.resize((THUMB_W, THUMB_H), Image.LANCZOS)
        images.append(img)

    n = len(images)

    # Generate labels based on style
    if args.label_style == "number":
        labels = [str(i + 1) for i in range(n)]
    else:
        labels = [chr(65 + i) for i in range(min(n, 26))]  # A-Z

    # Determine grid dimensions
    if args.cols:
        cols = args.cols
    elif n <= 2:
        cols = 2
    elif n <= 4:
        cols = 2
    else:
        cols = 4
    rows = math.ceil(n / cols)

    # For large grids, scale thumbnails down to keep output manageable
    if cols <= 2:
        cell_w, cell_h = THUMB_W, THUMB_H
    else:
        # Scale each cell to fit 4 columns within a reasonable width
        cell_w = THUMB_W // 2  # 640px per cell
        cell_h = THUMB_H // 2  # 360px per cell

    grid_w = cols * cell_w
    grid_h = rows * cell_h
    grid = Image.new("RGB", (grid_w, grid_h), (30, 30, 30))

    positions = []
    for i in range(n):
        col = i % cols
        row = i // cols
        x = col * cell_w
        y = row * cell_h
        # Resize image to cell size if different from THUMB dimensions
        cell_img = images[i]
        if (cell_w, cell_h) != (THUMB_W, THUMB_H):
            cell_img = cell_img.resize((cell_w, cell_h), Image.LANCZOS)
        grid.paste(cell_img, (x, y))
        positions.append((x, y))

    # Add labels
    draw = ImageDraw.Draw(grid)
    # Scale label font for large grids
    label_font_size = 28 if cols > 2 else 48
    # Try to load a font for labels
    label_font = None
    for fpath in [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
    ]:
        if os.path.isfile(fpath):
            try:
                label_font = ImageFont.truetype(fpath, label_font_size)
                break
            except Exception:
                continue
    if label_font is None:
        label_font = ImageFont.load_default()

    for i, (px, py) in enumerate(positions):
        label = labels[i]
        lx, ly = px + 20, py + 12

        # Draw background pill for label
        bbox = draw.textbbox((lx, ly), label, font=label_font)
        pill_pad = 10
        draw.rounded_rectangle(
            [bbox[0] - pill_pad, bbox[1] - pill_pad, bbox[2] + pill_pad, bbox[3] + pill_pad],
            radius=8,
            fill=(0, 0, 0, 180),
        )
        draw.text((lx, ly), label, font=label_font, fill="#FFFFFF")

    # Save grid
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    grid.save(output_path, "PNG")

    # --- QA on each image (skip for research grids) ---
    qa_results = []
    if not args.skip_qa:
        for i, img in enumerate(images):
            tr = text_regions[i] if text_regions and i < len(text_regions) else None
            qa = run_qa(img, tr, args.font_size)
            qa_results.append({
                "label": labels[i],
                "source": os.path.abspath(input_paths[i]),
                **qa,
            })

        # Generate mobile previews
        mobile_dir = os.path.join(os.path.dirname(output_path), "mobile_previews")
        os.makedirs(mobile_dir, exist_ok=True)
        for i, img in enumerate(images):
            mobile = img.resize((MOBILE_W, MOBILE_H), Image.LANCZOS)
            mobile_path = os.path.join(mobile_dir, f"concept_{labels[i]}_mobile.png")
            mobile.save(mobile_path, "PNG")
            qa_results[i]["mobile_preview"] = os.path.abspath(mobile_path)

    elapsed = round(time.time() - start, 2)
    file_size = os.path.getsize(output_path)

    result = {
        "status": "success",
        "grid_file": os.path.abspath(output_path),
        "grid_dimensions": f"{grid_w}x{grid_h}",
        "images": n,
        "cols": cols,
        "rows": rows,
        "label_style": args.label_style,
        "file_size_bytes": file_size,
        "elapsed_seconds": elapsed,
    }
    if qa_results:
        result["qa"] = qa_results
    print(json.dumps(result))


if __name__ == "__main__":
    main()
