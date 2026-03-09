#!/usr/bin/env python3
"""Generate a thumbnail with character consistency using Gemini.

Takes a competitor thumbnail as a layout/scene reference and the user's
headshot as a character reference, then uses Gemini's multi-image generation
to create a new thumbnail featuring the user in a similar scene/composition.

Uses "character consistency" prompting: the headshot defines the person's
identity (face, build, glasses, clothing), and the reference thumbnail
defines the scene, composition, and style.

Usage:
    python3 executors/thumbnail/replace_face.py \
        --reference competitor_thumbnail.jpg \
        --headshot primary_headshot.jpg \
        --extra-headshots ref2.jpg ref3.jpg ref4.jpg \
        --output workspace/temp/thumbnail/slug/face_replaced/concept_A.png \
        [--prompt "additional instructions"] \
        [--full-prompt "complete prompt replacing BASE_PROMPT"] \
        [--width 1280] [--height 720] \
        [--model gemini-3.1-flash-image-preview] \
        [--color-match]

Requires:
    - pip install google-genai Pillow
    - Set GEMINI_API_KEY in credentials.json or as environment variable
"""

from __future__ import annotations

import argparse
import json
import io
import os
import sys
import time

DEFAULT_MODEL = "gemini-3.1-flash-image-preview"

_EXECUTORS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EXECUTORS_DIR not in sys.path:
    sys.path.insert(0, _EXECUTORS_DIR)
from shared.gemini_usage import load_usage, update_usage

BASE_PROMPT_SINGLE = (
    "The first image is a scene/layout reference. The second image is a reference "
    "photo of a person called Subject Alpha. Generate a high-quality YouTube "
    "thumbnail of Subject Alpha in a scene inspired by the first image. "
    "Maintain EXACT facial identity of Subject Alpha — the face must be "
    "photographically identical to the reference photo. Same face structure, "
    "same features, same skin tone, same build, same hair, same glasses (if any). "
    "Do NOT alter, stylize, or reinterpret any facial features. "
    "Match the composition, pose, position, and overall layout of the first image. "
    "You have full creative freedom over color grading, brightness, contrast, "
    "saturation, lighting direction, and overall color palette — adjust these "
    "freely to create the most visually striking thumbnail. "
    "Do NOT include any text, letters, or words in the generated image. "
    "Do NOT include any watermarks."
)

BASE_PROMPT_MULTI = (
    "The first image is a scene/layout reference. The remaining images are all "
    "reference photos of the same person called Subject Alpha, showing them from "
    "different angles and expressions. Study all of the reference photos carefully "
    "to understand Subject Alpha's exact facial identity. "
    "Generate a high-quality YouTube thumbnail of Subject Alpha in a scene "
    "inspired by the first image. "
    "Maintain EXACT facial identity of Subject Alpha — the face must be "
    "photographically identical to the reference photos. Same face structure, "
    "same features, same skin tone, same build, same hair, same glasses (if any). "
    "Do NOT alter, stylize, or reinterpret any facial features. "
    "Match the composition, pose, position, and overall layout of the first image. "
    "You have full creative freedom over color grading, brightness, contrast, "
    "saturation, lighting direction, and overall color palette — adjust these "
    "freely to create the most visually striking thumbnail. "
    "Do NOT include any text, letters, or words in the generated image. "
    "Do NOT include any watermarks."
)


def check_dependencies():
    """Check that required packages are installed."""
    missing = []
    try:
        from google import genai  # noqa: F401
    except ImportError:
        missing.append("google-genai")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow")
    return missing


def load_api_key() -> str:
    """Load Gemini API key from credentials.json or environment variable."""
    creds_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "credentials.json"
    )
    if os.path.isfile(creds_path):
        with open(creds_path) as f:
            creds = json.load(f)
        key = creds.get("gemini_api_key")
        if key and key != "YOUR_GEMINI_API_KEY":
            return key

    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key

    raise EnvironmentError(
        "Gemini API key not found. Set it in one of:\n"
        "  1. credentials.json → add \"gemini_api_key\": \"your_key\"\n"
        "  2. Environment variable → export GEMINI_API_KEY=your_key\n"
        "Get a key at https://aistudio.google.com/apikey"
    )



def color_match(reference_img, generated_img):
    """Adjust generated image brightness and contrast to match the reference.

    Uses per-channel mean (brightness) and std dev (contrast) from ImageStat
    to compute correction factors, then applies via ImageEnhance.
    Factors are clamped to [0.5, 2.0] to prevent extreme corrections.
    """
    from PIL import ImageStat, ImageEnhance

    ref_stat = ImageStat.Stat(reference_img)
    gen_stat = ImageStat.Stat(generated_img)

    # Mean brightness across RGB channels
    ref_mean = sum(ref_stat.mean[:3]) / 3.0
    gen_mean = sum(gen_stat.mean[:3]) / 3.0

    # Std dev (contrast proxy) across RGB channels
    ref_std = sum(ref_stat.stddev[:3]) / 3.0
    gen_std = sum(gen_stat.stddev[:3]) / 3.0

    # Brightness correction
    if gen_mean > 0:
        brightness_factor = max(0.5, min(2.0, ref_mean / gen_mean))
        generated_img = ImageEnhance.Brightness(generated_img).enhance(brightness_factor)

    # Contrast correction
    if gen_std > 0:
        contrast_factor = max(0.5, min(2.0, ref_std / gen_std))
        generated_img = ImageEnhance.Contrast(generated_img).enhance(contrast_factor)

    return generated_img


def replace_face(
    reference_path: str,
    headshot_paths: list[str],
    width: int,
    height: int,
    extra_prompt: str | None,
    full_prompt: str | None = None,
    model: str = DEFAULT_MODEL,
    asset_paths: list[str] | None = None,
) -> bytes:
    """Call Gemini API with character consistency to generate thumbnail.

    Passes the reference thumbnail (scene/layout) and one or more headshots
    (character identity) as inline reference images alongside a text prompt
    that uses character consistency framing (no face-swap language).

    Multiple headshots give Gemini more angles/expressions to understand
    the person's appearance, improving facial consistency.
    """
    from google import genai
    from google.genai import types
    from PIL import Image

    api_key = load_api_key()
    client = genai.Client(api_key=api_key)

    # Load images
    reference_img = Image.open(reference_path).convert("RGB")
    headshot_imgs = [Image.open(p).convert("RGB") for p in headshot_paths]
    asset_imgs = [Image.open(p).convert("RGBA") for p in (asset_paths or [])]

    # Build prompt: --full-prompt replaces BASE_PROMPT entirely
    if full_prompt:
        prompt = full_prompt
    else:
        prompt = BASE_PROMPT_MULTI if len(headshot_imgs) > 1 else BASE_PROMPT_SINGLE
        if extra_prompt:
            prompt += f" Additional instructions: {extra_prompt}"

    # Asset preservation instructions
    if asset_imgs:
        n_headshots = len(headshot_imgs)
        asset_start = n_headshots + 2  # 1-indexed: 1=reference, 2..N=headshots, then assets
        asset_labels = []
        for i in range(len(asset_imgs)):
            label = f"image {asset_start + i}"
            asset_labels.append(label)
        labels_str = ", ".join(asset_labels)
        prompt += (
            f" The following additional images ({labels_str}) are asset references "
            f"(logos, screenshots, icons, or graphics). You MUST include each asset "
            f"in the generated thumbnail EXACTLY as provided — preserve every detail: "
            f"exact colors, exact shapes, exact proportions, exact text/lettering, "
            f"exact transparency. Do NOT redraw, reinterpret, simplify, or stylize "
            f"these assets in any way. Place them naturally within the composition."
        )

    prompt += f" Image dimensions: {width}x{height} pixels, 16:9 aspect ratio."

    # Send multi-image request to Gemini
    # Image order: reference (scene/layout), then headshot(s) (character identity), then assets
    contents: list = [prompt, reference_img] + headshot_imgs + asset_imgs
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )

    # Extract image from response
    for part in response.parts:
        if part.inline_data is not None:
            return part.inline_data.data

    raise RuntimeError(
        "Gemini returned no image in the response. "
        "The reference thumbnail may not contain a usable scene, "
        "or the prompt may need adjustment."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate a thumbnail with character consistency using Gemini."
    )
    parser.add_argument("--reference", required=True,
                        help="Path to the scene/layout reference thumbnail image")
    parser.add_argument("--headshot", required=True,
                        help="Path to the primary character reference (headshot) image")
    parser.add_argument("--extra-headshots", nargs="*", default=[],
                        help="Additional headshot reference images (different angles/expressions)")
    parser.add_argument("--assets", nargs="*", default=[],
                        help="Asset images (logos, screenshots, icons) to include exactly as-is")
    parser.add_argument("--output", required=True,
                        help="Output file path (PNG)")
    parser.add_argument("--prompt", default=None,
                        help="Additional instructions appended to BASE_PROMPT")
    parser.add_argument("--full-prompt", default=None,
                        help="Complete prompt replacing BASE_PROMPT (for custom scene prompts)")
    parser.add_argument("--width", type=int, default=1280,
                        help="Output image width (default: 1280)")
    parser.add_argument("--height", type=int, default=720,
                        help="Output image height (default: 720)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Gemini model ID (default: {DEFAULT_MODEL})")
    parser.add_argument("--color-match", action="store_true",
                        help="Adjust output brightness/contrast to match the reference thumbnail")
    args = parser.parse_args()

    start = time.time()

    # Check dependencies
    missing = check_dependencies()
    if missing:
        print(json.dumps({
            "status": "error",
            "error": f"Missing packages: {', '.join(missing)}. Install with: pip install {' '.join(missing)}",
        }))
        sys.exit(1)

    from PIL import Image

    # Validate inputs
    if not os.path.isfile(args.reference):
        print(json.dumps({
            "status": "error",
            "error": f"Reference image not found: {args.reference}",
        }))
        sys.exit(1)

    # Build headshot list: primary + extras
    all_headshots = [args.headshot] + (args.extra_headshots or [])
    for hs in all_headshots:
        if not os.path.isfile(hs):
            print(json.dumps({
                "status": "error",
                "error": f"Headshot image not found: {hs}",
            }))
            sys.exit(1)

    # Validate asset files
    for asset in (args.assets or []):
        if not os.path.isfile(asset):
            print(json.dumps({
                "status": "error",
                "error": f"Asset image not found: {asset}",
            }))
            sys.exit(1)

    # Generate image with character consistency
    try:
        image_bytes = replace_face(
            args.reference, all_headshots,
            args.width, args.height,
            args.prompt, args.full_prompt, args.model,
            args.assets or None,
        )
    except EnvironmentError as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "error": f"Image generation failed: {e}",
        }))
        sys.exit(1)

    # Save and resize to exact dimensions
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if img.size != (args.width, args.height):
        img = img.resize((args.width, args.height), Image.LANCZOS)

    # Color-match output to reference brightness/contrast
    color_matched = False
    if args.color_match:
        ref_img = Image.open(args.reference).convert("RGB")
        img = color_match(ref_img, img)
        color_matched = True

    img.save(args.output, "PNG")

    # Update daily usage tracker
    usage = update_usage()

    elapsed = round(time.time() - start, 2)
    file_size = os.path.getsize(args.output)

    print(json.dumps({
        "status": "success",
        "output_file": os.path.abspath(args.output),
        "reference_file": os.path.abspath(args.reference),
        "headshot_files": [os.path.abspath(hs) for hs in all_headshots],
        "headshot_count": len(all_headshots),
        "asset_files": [os.path.abspath(a) for a in (args.assets or [])],
        "asset_count": len(args.assets or []),
        "dimensions": f"{args.width}x{args.height}",
        "provider": "gemini",
        "model": args.model,
        "color_matched": color_matched,
        "file_size_bytes": file_size,
        "elapsed_seconds": elapsed,
        "usage_today": usage.get("images_generated", 0),
    }))


if __name__ == "__main__":
    main()
