#!/usr/bin/env python3
"""
Prepare Assets Executor
========================
Fetches screenshots for source overlays and verifies all assets
referenced in the enhancement spec.

Usage:
    python executors/enhance/prepare_assets.py --spec <spec_json> --output-dir <dir>

Exits:
    0  — all assets prepared
    1  — some assets failed (partial success)
    2  — input error

Output (stdout, JSON):
    {
      "status": "ok"|"partial"|"error",
      "assets": [
        {"type": "screenshot", "url": "...", "path": "...", "status": "ok"|"failed"},
        {"type": "sfx", "sfx_id": "...", "status": "ok"|"missing"}
      ]
    }
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path

# Resolve project root for sfx path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
SFX_DIR = os.path.join(PROJECT_ROOT, "remotion", "public", "sfx")


def capture_screenshot(url: str, output_path: str) -> bool:
    """Capture a screenshot of a URL using Playwright (if available)."""
    try:
        result = subprocess.run(
            [
                sys.executable, "-c",
                f"""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={{"width": 1280, "height": 800}})
    page.goto("{url}", wait_until="networkidle", timeout=15000)
    page.screenshot(path="{output_path}", full_page=False)
    browser.close()
    print("ok")
"""
            ],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0 and "ok" in result.stdout
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Prepare assets for enhancement spec")
    parser.add_argument("--spec", required=True, help="Path to enhancement_spec.json")
    parser.add_argument("--output-dir", required=True, help="Directory for downloaded assets")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not spec_path.exists():
        print(json.dumps({"status": "error", "assets": [], "message": f"Spec not found: {args.spec}"}))
        sys.exit(2)

    spec = json.loads(spec_path.read_text())
    assets = []

    for enh in spec.get("enhancements", []):
        etype = enh.get("type")
        content = enh.get("content", {})
        eid = enh.get("id", "unknown")

        # Source overlay screenshots
        if etype == "source_overlay":
            source_url = content.get("source_url")
            screenshot_path = content.get("screenshot_path", "")

            if source_url and (not screenshot_path or not Path(screenshot_path).exists()):
                # Generate screenshot path
                safe_name = f"screenshot_{eid}.png"
                output_path = str(output_dir / safe_name)

                success = capture_screenshot(source_url, output_path)
                assets.append({
                    "type": "screenshot",
                    "url": source_url,
                    "path": output_path,
                    "status": "ok" if success else "failed",
                    "enhancement_id": eid,
                })

                if success:
                    # Update spec with the actual screenshot path
                    content["screenshot_path"] = output_path
            elif screenshot_path and Path(screenshot_path).exists():
                assets.append({
                    "type": "screenshot",
                    "path": screenshot_path,
                    "status": "ok",
                    "enhancement_id": eid,
                })
            else:
                assets.append({
                    "type": "screenshot",
                    "url": source_url or "none",
                    "status": "failed",
                    "enhancement_id": eid,
                    "reason": "No source URL and no existing screenshot",
                })

        # Sound effect verification
        if etype == "sound_effect":
            sfx_id = content.get("sfx_id", "")
            sfx_path = os.path.join(SFX_DIR, f"{sfx_id}.mp3")
            exists = os.path.exists(sfx_path)
            assets.append({
                "type": "sfx",
                "sfx_id": sfx_id,
                "path": sfx_path,
                "status": "ok" if exists else "missing",
                "enhancement_id": eid,
            })

        # Image assets (map_highlight, source_overlay images)
        if etype == "map_highlight":
            image_path = content.get("image_path", "")
            if image_path:
                exists = Path(image_path).exists()
                assets.append({
                    "type": "image",
                    "path": image_path,
                    "status": "ok" if exists else "missing",
                    "enhancement_id": eid,
                })

    # Write updated spec back (with corrected paths)
    spec_path.write_text(json.dumps(spec, indent=2))

    # Determine overall status
    failed = [a for a in assets if a["status"] in ("failed", "missing")]
    status = "ok" if not failed else "partial" if len(failed) < len(assets) else "error"

    result = {"status": status, "assets": assets}
    print(json.dumps(result, indent=2))
    sys.exit(0 if status == "ok" else 1)


if __name__ == "__main__":
    main()
