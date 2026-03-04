#!/usr/bin/env python3
"""Generate a thumbnail background image using Google Gemini (Nano Banana).

Usage:
    python3 executors/thumbnail/generate_background.py \
        --prompt "cinematic dark office, dramatic lighting" \
        --output workspace/temp/thumbnail/slug/backgrounds/concept_A.png \
        [--width 1280] [--height 720] \
        [--negative-prompt "no text, no letters, no words, no watermarks"]

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
    """Load Gemini API key from credentials.json or environment variable.

    Priority: credentials.json > GEMINI_API_KEY env var.
    """
    # Try credentials.json first (project root)
    creds_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "credentials.json"
    )
    if os.path.isfile(creds_path):
        with open(creds_path) as f:
            creds = json.load(f)
        key = creds.get("gemini_api_key")
        if key and key != "YOUR_GEMINI_API_KEY":
            return key

    # Fall back to environment variable
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


def generate_image(prompt: str, width: int, height: int, negative_prompt: str | None, model: str = DEFAULT_MODEL) -> bytes:
    """Call Gemini API to generate an image. Returns PNG bytes."""
    from google import genai
    from google.genai import types

    api_key = load_api_key()

    client = genai.Client(api_key=api_key)

    # Build the full prompt — include aspect ratio and negative guidance
    full_prompt = prompt
    full_prompt += f". Image dimensions: {width}x{height} pixels, 16:9 aspect ratio."
    if negative_prompt:
        full_prompt += f" Do NOT include: {negative_prompt}."

    response = client.models.generate_content(
        model=model,
        contents=full_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )

    # Extract image from response
    for part in response.parts:
        if part.inline_data is not None:
            return part.inline_data.data

    raise RuntimeError("Gemini returned no image in the response. Try simplifying your prompt.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a thumbnail background image using Google Gemini (Nano Banana)."
    )
    parser.add_argument("--prompt", required=True, help="Image generation prompt describing the background")
    parser.add_argument("--output", required=True, help="Output file path (PNG)")
    parser.add_argument("--width", type=int, default=1280, help="Image width (default: 1280)")
    parser.add_argument("--height", type=int, default=720, help="Image height (default: 720)")
    parser.add_argument(
        "--negative-prompt",
        default="no text, no letters, no words, no watermarks",
        help="What to exclude from the image (default: no text/letters/words/watermarks)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model ID (default: {DEFAULT_MODEL})",
    )
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

    # Generate
    try:
        image_bytes = generate_image(args.prompt, args.width, args.height, args.negative_prompt, args.model)
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
    img = Image.open(io.BytesIO(image_bytes))
    if img.size != (args.width, args.height):
        img = img.resize((args.width, args.height), Image.LANCZOS)
    img.save(args.output, "PNG")

    # Update daily usage tracker
    update_usage_tracker()

    elapsed = round(time.time() - start, 2)
    file_size = os.path.getsize(args.output)
    usage = load_usage_tracker()

    print(json.dumps({
        "status": "success",
        "output_file": os.path.abspath(args.output),
        "prompt": args.prompt,
        "dimensions": f"{args.width}x{args.height}",
        "provider": "gemini",
        "model": args.model,
        "file_size_bytes": file_size,
        "elapsed_seconds": elapsed,
        "usage_today": usage.get("images_generated", 0),
    }))


if __name__ == "__main__":
    main()
