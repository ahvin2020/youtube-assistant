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
from datetime import date

DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
USAGE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "workspace", "temp", "thumbnail", "usage.json"
)

BASE_PROMPT_SINGLE = (
    "The first image is a scene/layout reference. The second image is a reference "
    "photo of a person called Subject Alpha. Generate a high-quality YouTube "
    "thumbnail of Subject Alpha in a scene inspired by the first image. "
    "Maintain strict facial and physical consistency with the provided reference "
    "photo of Subject Alpha — same face, same build, same hair, same glasses "
    "(if any), same skin tone. Match the composition, background style, colors, "
    "lighting, and overall layout of the first image. Subject Alpha should adopt "
    "a similar pose and position in the frame as the person in the first image. "
    "Do NOT include any text, letters, or words in the generated image. "
    "Do NOT include any watermarks."
)

BASE_PROMPT_MULTI = (
    "The first image is a scene/layout reference. The remaining images are all "
    "reference photos of the same person called Subject Alpha, showing them from "
    "different angles and expressions. Study all of the reference photos carefully "
    "to understand Subject Alpha's face, build, hair, glasses, and skin tone. "
    "Generate a high-quality YouTube thumbnail of Subject Alpha in a scene "
    "inspired by the first image. Maintain strict facial and physical consistency "
    "with the provided reference photos of Subject Alpha — same face, same build, "
    "same hair, same glasses (if any), same skin tone. Match the composition, "
    "background style, colors, lighting, and overall layout of the first image. "
    "Subject Alpha should adopt a similar pose and position in the frame as the "
    "person in the first image. "
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


def load_usage_tracker() -> dict:
    """Load today's usage from workspace/temp/thumbnail/usage.json."""
    if not os.path.isfile(USAGE_FILE):
        return {"date": str(date.today()), "images_generated": 0}
    with open(USAGE_FILE) as f:
        data = json.load(f)
    if data.get("date") != str(date.today()):
        return {"date": str(date.today()), "images_generated": 0}
    return data


def update_usage_tracker() -> None:
    """Increment today's image count in usage.json."""
    usage = load_usage_tracker()
    usage["images_generated"] = usage.get("images_generated", 0) + 1
    usage["date"] = str(date.today())
    os.makedirs(os.path.dirname(USAGE_FILE) or ".", exist_ok=True)
    with open(USAGE_FILE, "w") as f:
        json.dump(usage, f, indent=2)


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

    # Build prompt: --full-prompt replaces BASE_PROMPT entirely
    if full_prompt:
        prompt = full_prompt
    else:
        if len(headshot_imgs) > 1:
            prompt = BASE_PROMPT_MULTI
        else:
            prompt = BASE_PROMPT_SINGLE
        if extra_prompt:
            prompt += f" Additional instructions: {extra_prompt}"
    prompt += f" Image dimensions: {width}x{height} pixels, 16:9 aspect ratio."

    # Send multi-image request to Gemini
    # Image order: reference (scene/layout), then headshot(s) (character identity)
    contents: list = [prompt, reference_img] + headshot_imgs
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

    # Generate image with character consistency
    try:
        image_bytes = replace_face(
            args.reference, all_headshots,
            args.width, args.height,
            args.prompt, args.full_prompt, args.model,
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
    update_usage_tracker()

    elapsed = round(time.time() - start, 2)
    file_size = os.path.getsize(args.output)
    usage = load_usage_tracker()

    print(json.dumps({
        "status": "success",
        "output_file": os.path.abspath(args.output),
        "reference_file": os.path.abspath(args.reference),
        "headshot_files": [os.path.abspath(hs) for hs in all_headshots],
        "headshot_count": len(all_headshots),
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
