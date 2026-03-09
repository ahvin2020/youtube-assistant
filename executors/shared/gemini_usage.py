#!/usr/bin/env python3
"""Shared Gemini image generation usage tracking and pricing cache.

Consolidates usage tracking (daily image count) and pricing data into
a single `workspace/temp/thumbnail/usage.json` file. Used by all Gemini
image generation executors (replace_face.py, generate_background.py)
and can be called standalone to track mockup generation or refresh pricing.

Usage (CLI):
    # Increment usage (e.g. after generating a mockup)
    python3 executors/shared/gemini_usage.py --update-usage --count 2

    # Show current usage and pricing
    python3 executors/shared/gemini_usage.py --show

    # Update pricing from JSON string
    python3 executors/shared/gemini_usage.py --update-pricing '{
        "gemini-3.1-flash-image-preview": {"cost_per_image": 0.03, "daily_free_limit": 500}
    }'

Usage (import):
    from shared.gemini_usage import load_usage, update_usage, load_pricing
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

USAGE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "workspace", "temp", "thumbnail", "usage.json"
)

DEFAULT_PRICING = {
    "gemini-3.1-flash-image-preview": {"cost_per_image": 0.03, "daily_free_limit": 500, "notes": "Good balance of quality and cost"},
    "gemini-2.0-flash-exp-image-generation": {"cost_per_image": 0.00, "daily_free_limit": 500, "notes": "Experimental, lower quality"},
    "imagen-4-fast": {"cost_per_image": 0.020, "daily_free_limit": 100, "notes": "Google Imagen"},
    "gemini-3-pro-image": {"cost_per_image": 0.039, "daily_free_limit": 0, "notes": "Highest quality, no free tier"},
}


def _load_file() -> dict:
    """Load the full usage.json file, or return empty structure."""
    if not os.path.isfile(USAGE_FILE):
        return {}
    with open(USAGE_FILE) as f:
        return json.load(f)


def _save_file(data: dict) -> None:
    """Write data to usage.json."""
    os.makedirs(os.path.dirname(USAGE_FILE) or ".", exist_ok=True)
    with open(USAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_usage() -> dict:
    """Load today's usage count. Resets on a new day.

    Returns: {"date": "YYYY-MM-DD", "images_generated": N}
    """
    data = _load_file()
    today = str(date.today())
    if data.get("date") != today:
        return {"date": today, "images_generated": 0}
    return {"date": today, "images_generated": data.get("images_generated", 0)}


def update_usage(count: int = 1) -> dict:
    """Increment today's image count by `count`. Returns updated usage."""
    data = _load_file()
    today = str(date.today())
    if data.get("date") != today:
        data["date"] = today
        data["images_generated"] = 0
    data["images_generated"] = data.get("images_generated", 0) + count
    _save_file(data)
    return {"date": today, "images_generated": data["images_generated"]}


def load_pricing() -> dict:
    """Load pricing data from usage.json, falling back to defaults.

    Returns: {"fetched_date": "YYYY-MM-DD", "models": {model_id: {cost_per_image, daily_free_limit, notes}}}
    """
    data = _load_file()
    pricing = data.get("pricing")
    if pricing and pricing.get("models"):
        return pricing
    return {"fetched_date": "default", "models": DEFAULT_PRICING}


def update_pricing(models: dict) -> dict:
    """Update pricing data in usage.json. Returns the saved pricing block."""
    data = _load_file()
    today = str(date.today())
    if data.get("date") != today:
        data["date"] = today
        data["images_generated"] = 0
    data["pricing"] = {"fetched_date": today, "models": models}
    _save_file(data)
    return data["pricing"]


def pricing_needs_refresh() -> bool:
    """Check if pricing was last fetched before today."""
    pricing = load_pricing()
    return pricing.get("fetched_date") != str(date.today())


def main():
    parser = argparse.ArgumentParser(description="Gemini image generation usage tracking and pricing cache.")
    parser.add_argument("--update-usage", action="store_true", help="Increment today's image usage count")
    parser.add_argument("--count", type=int, default=1, help="Number of images to add (default: 1)")
    parser.add_argument("--show", action="store_true", help="Show current usage and pricing")
    parser.add_argument("--update-pricing", type=str, default=None,
                        help="Update pricing from JSON string: '{\"model\": {\"cost_per_image\": 0.03, ...}}'")
    parser.add_argument("--check-pricing-refresh", action="store_true",
                        help="Check if pricing needs refresh (exits 0 if fresh, 1 if stale)")
    args = parser.parse_args()

    if args.update_usage:
        usage = update_usage(args.count)
        print(json.dumps({"status": "success", "action": "update_usage", **usage}))

    elif args.update_pricing:
        models = json.loads(args.update_pricing)
        pricing = update_pricing(models)
        print(json.dumps({"status": "success", "action": "update_pricing", "pricing": pricing}))

    elif args.check_pricing_refresh:
        needs = pricing_needs_refresh()
        print(json.dumps({"needs_refresh": needs, "pricing": load_pricing()}))
        sys.exit(0 if not needs else 1)

    elif args.show:
        usage = load_usage()
        pricing = load_pricing()
        print(json.dumps({"usage": usage, "pricing": pricing}, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
