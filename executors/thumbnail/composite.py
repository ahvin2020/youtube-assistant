#!/usr/bin/env python3
"""Composite a headshot and text overlay onto a thumbnail background.

Usage:
    python3 executors/thumbnail/composite.py <background> <output> [options]

    python3 executors/thumbnail/composite.py \
        workspace/temp/thumbnail/slug/backgrounds/concept_A.png \
        workspace/temp/thumbnail/slug/composited/concept_A.png \
        --headshot workspace/input/thumbnail/headshots/excited.png \
        --headshot-scale 0.8 \
        --headshot-position right-bottom \
        --text "DON'T BUY" \
        --text-position top-left \
        --font-size 72 \
        --font-color "#FFFFFF" \
        --stroke-color "#000000" \
        --stroke-width 3

Requires: pip install Pillow
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

THUMB_W = 1280
THUMB_H = 720
PADDING = 64  # safe-zone margin


def find_font(font_path: str | None, font_size: int):
    """Load a TrueType font, falling back through system fonts."""
    from PIL import ImageFont

    candidates = [
        font_path,
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue
    # Last resort: Pillow default
    return ImageFont.load_default()


def compute_position(
    position_name: str,
    item_w: int,
    item_h: int,
    frame_w: int = THUMB_W,
    frame_h: int = THUMB_H,
) -> tuple[int, int]:
    """Compute (x, y) for a named position within the frame."""
    positions = {
        "top-left":      (PADDING, PADDING),
        "top-right":     (frame_w - item_w - PADDING, PADDING),
        "top-center":    ((frame_w - item_w) // 2, PADDING),
        "bottom-left":   (PADDING, frame_h - item_h - PADDING),
        "bottom-right":  (frame_w - item_w - PADDING, frame_h - item_h - PADDING),
        "center":        ((frame_w - item_w) // 2, (frame_h - item_h) // 2),
        "right-bottom":  (frame_w - item_w - PADDING, frame_h - item_h),
        "left-bottom":   (PADDING, frame_h - item_h),
        "center-bottom": ((frame_w - item_w) // 2, frame_h - item_h),
        "right-center":  (frame_w - item_w - PADDING, (frame_h - item_h) // 2),
        "left-center":   (PADDING, (frame_h - item_h) // 2),
    }
    return positions.get(position_name, positions["right-bottom"])


def draw_text_with_stroke(
    draw,
    position: tuple[int, int],
    text: str,
    font,
    fill: str,
    stroke_color: str,
    stroke_width: int,
):
    """Draw text with an outline/stroke for readability."""
    x, y = position
    # Draw stroke by rendering text at offsets in all directions
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=stroke_color)
    # Draw main text on top
    draw.text((x, y), text, font=font, fill=fill)


def add_drop_shadow(image, offset: tuple[int, int] = (6, 6), blur_radius: int = 8):
    """Add a drop shadow to a RGBA image (for headshots)."""
    from PIL import Image, ImageFilter

    # Create shadow from alpha channel
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    alpha = image.split()[3]
    shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 120))
    shadow.paste(shadow_layer, mask=alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Create canvas large enough for shadow offset
    canvas_w = image.width + abs(offset[0])
    canvas_h = image.height + abs(offset[1])
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    # Place shadow offset, then image on top
    sx = max(offset[0], 0)
    sy = max(offset[1], 0)
    canvas.paste(shadow, (sx, sy), shadow)

    ix = max(-offset[0], 0)
    iy = max(-offset[1], 0)
    canvas.paste(image, (ix, iy), image)

    return canvas


def main():
    parser = argparse.ArgumentParser(
        description="Composite a headshot and text onto a thumbnail background."
    )
    parser.add_argument("background", help="Path to background image (1280x720 PNG/JPG)")
    parser.add_argument("output", help="Output file path")

    # Headshot options
    parser.add_argument("--headshot", help="Path to headshot PNG (transparent background)")
    parser.add_argument("--headshot-scale", type=float, default=0.8,
                        help="Headshot height as fraction of frame height (default: 0.8)")
    parser.add_argument("--headshot-position", default="right-bottom",
                        help="Named position (default: right-bottom)")
    parser.add_argument("--headshot-x", type=int, help="Exact X offset (overrides position)")
    parser.add_argument("--headshot-y", type=int, help="Exact Y offset (overrides position)")
    parser.add_argument("--shadow", action="store_true", help="Add drop shadow behind headshot")

    # Text options
    parser.add_argument("--text", help="Text to overlay on the thumbnail")
    parser.add_argument("--text-position", default="top-left",
                        help="Named position (default: top-left)")
    parser.add_argument("--text-x", type=int, help="Exact X offset (overrides position)")
    parser.add_argument("--text-y", type=int, help="Exact Y offset (overrides position)")
    parser.add_argument("--font-size", type=int, default=72, help="Font size in pixels (default: 72)")
    parser.add_argument("--font-color", default="#FFFFFF", help="Font color as hex (default: #FFFFFF)")
    parser.add_argument("--stroke-color", default="#000000", help="Stroke color as hex (default: #000000)")
    parser.add_argument("--stroke-width", type=int, default=3, help="Stroke width in pixels (default: 3)")
    parser.add_argument("--font-path", help="Path to .ttf font file")

    # Mode
    parser.add_argument("--text-only", action="store_true",
                        help="Text overlay only — skip headshot compositing (for reference-based pipeline)")

    # Asset overlays
    parser.add_argument("--asset", action="append", help="Path to additional asset image (can repeat)")
    parser.add_argument("--asset-position", action="append", help="Position for each asset")
    parser.add_argument("--asset-scale", action="append", type=float, help="Scale for each asset")

    args = parser.parse_args()

    start = time.time()

    # Check Pillow
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print(json.dumps({
            "status": "error",
            "error": "Pillow not installed. Install with: pip install Pillow",
        }))
        sys.exit(1)

    # Load background
    if not os.path.isfile(args.background):
        print(json.dumps({
            "status": "error",
            "error": f"Background image not found: {args.background}",
        }))
        sys.exit(1)

    canvas = Image.open(args.background).convert("RGBA")
    if canvas.size != (THUMB_W, THUMB_H):
        canvas = canvas.resize((THUMB_W, THUMB_H), Image.LANCZOS)

    headshot_used = None
    text_bbox = None

    # --- Headshot compositing (skipped in text-only mode) ---
    if args.headshot and not args.text_only:
        if not os.path.isfile(args.headshot):
            print(json.dumps({
                "status": "error",
                "error": f"Headshot not found: {args.headshot}",
            }))
            sys.exit(1)

        hs_raw = Image.open(args.headshot)
        # Auto-detect EXIF orientation
        try:
            from PIL import ImageOps
            hs_raw = ImageOps.exif_transpose(hs_raw)
        except Exception:
            pass
        # Auto-remove background if headshot lacks transparency (JPG etc.)
        if hs_raw.mode != "RGBA" or not hs_raw.getbands()[-1]:
            try:
                from rembg import remove
                hs = remove(hs_raw).convert("RGBA")
            except ImportError:
                hs = hs_raw.convert("RGBA")
        else:
            hs = hs_raw.convert("RGBA")
        target_h = int(THUMB_H * args.headshot_scale)
        aspect = hs.width / hs.height
        target_w = int(target_h * aspect)
        hs = hs.resize((target_w, target_h), Image.LANCZOS)

        if args.shadow:
            hs = add_drop_shadow(hs)
            target_w, target_h = hs.size

        if args.headshot_x is not None and args.headshot_y is not None:
            hx, hy = args.headshot_x, args.headshot_y
        else:
            hx, hy = compute_position(args.headshot_position, target_w, target_h)

        canvas.paste(hs, (hx, hy), hs)
        headshot_used = os.path.basename(args.headshot)

    # --- Asset overlays ---
    if args.asset:
        for i, asset_path in enumerate(args.asset):
            if not os.path.isfile(asset_path):
                continue
            asset_img = Image.open(asset_path).convert("RGBA")
            scale = args.asset_scale[i] if args.asset_scale and i < len(args.asset_scale) else 0.15
            asset_h = int(THUMB_H * scale)
            a_aspect = asset_img.width / asset_img.height
            asset_w = int(asset_h * a_aspect)
            asset_img = asset_img.resize((asset_w, asset_h), Image.LANCZOS)
            pos_name = args.asset_position[i] if args.asset_position and i < len(args.asset_position) else "bottom-left"
            ax, ay = compute_position(pos_name, asset_w, asset_h)
            canvas.paste(asset_img, (ax, ay), asset_img)

    # --- Text overlay ---
    if args.text:
        draw = ImageDraw.Draw(canvas)
        font = find_font(args.font_path, args.font_size)

        # Measure text
        bbox = draw.textbbox((0, 0), args.text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        if args.text_x is not None and args.text_y is not None:
            tx, ty = args.text_x, args.text_y
        else:
            tx, ty = compute_position(args.text_position, text_w, text_h)

        draw_text_with_stroke(
            draw,
            (tx, ty),
            args.text,
            font,
            fill=args.font_color,
            stroke_color=args.stroke_color,
            stroke_width=args.stroke_width,
        )
        text_bbox = {"x": tx, "y": ty, "width": text_w, "height": text_h}

    # --- Save ---
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    # Convert to RGB for smaller file size (PNG with no alpha needed for final)
    final = canvas.convert("RGB")
    final.save(args.output, "PNG")

    elapsed = round(time.time() - start, 2)
    file_size = os.path.getsize(args.output)

    result = {
        "status": "success",
        "output_file": os.path.abspath(args.output),
        "dimensions": f"{THUMB_W}x{THUMB_H}",
        "file_size_bytes": file_size,
        "elapsed_seconds": elapsed,
    }
    if headshot_used:
        result["headshot_used"] = headshot_used
    if args.text:
        result["text"] = args.text
    if text_bbox:
        result["text_bbox"] = text_bbox

    print(json.dumps(result))


if __name__ == "__main__":
    main()
