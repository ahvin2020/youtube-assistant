#!/usr/bin/env python3
"""Download logos, icons, or images from the web for thumbnail compositing.

Usage:
    python3 executors/thumbnail/fetch_asset.py <url> <output_path>

No external dependencies beyond Python stdlib.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error


def validate_image(path: str) -> tuple[bool, str | None]:
    """Check if the downloaded file is a valid image.

    Returns (is_valid, dimensions_string).
    Uses Pillow if available, otherwise checks magic bytes.
    """
    try:
        from PIL import Image
        img = Image.open(path)
        img.verify()
        return True, f"{img.width}x{img.height}"
    except ImportError:
        # Fallback: check magic bytes
        with open(path, "rb") as f:
            header = f.read(16)
        # PNG
        if header[:8] == b"\x89PNG\r\n\x1a\n":
            return True, None
        # JPEG
        if header[:2] == b"\xff\xd8":
            return True, None
        # GIF
        if header[:6] in (b"GIF87a", b"GIF89a"):
            return True, None
        # WebP
        if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
            return True, None
        return False, None
    except Exception:
        return False, None


def download_file(url: str, output_path: str) -> int:
    """Download a file from a URL. Returns file size in bytes."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    return len(data)


def main():
    parser = argparse.ArgumentParser(
        description="Download an image asset (logo, icon, photo) from a URL."
    )
    parser.add_argument("url", help="Direct URL to the image to download")
    parser.add_argument("output_path", help="Where to save the downloaded file")
    args = parser.parse_args()

    start = time.time()

    # Download
    try:
        file_size = download_file(args.url, args.output_path)
    except urllib.error.HTTPError as e:
        print(json.dumps({
            "status": "error",
            "error": f"HTTP {e.code}: {args.url}",
        }))
        sys.exit(1)
    except urllib.error.URLError as e:
        print(json.dumps({
            "status": "error",
            "error": f"URL error: {e.reason}",
        }))
        sys.exit(1)
    except OSError as e:
        print(json.dumps({
            "status": "error",
            "error": f"Download failed: {e}",
        }))
        sys.exit(1)

    # Validate
    is_valid, dimensions = validate_image(args.output_path)
    if not is_valid:
        os.remove(args.output_path)
        print(json.dumps({
            "status": "error",
            "error": "Downloaded file is not a valid image",
        }))
        sys.exit(1)

    elapsed = round(time.time() - start, 2)

    result = {
        "status": "success",
        "output_file": os.path.abspath(args.output_path),
        "source_url": args.url,
        "file_size_bytes": file_size,
        "elapsed_seconds": elapsed,
    }
    if dimensions:
        result["dimensions"] = dimensions

    print(json.dumps(result))


if __name__ == "__main__":
    main()
