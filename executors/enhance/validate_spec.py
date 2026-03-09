#!/usr/bin/env python3
"""
Validate Enhancement Spec Executor
====================================
Checks an enhancement_spec.json for schema validity, timing issues,
and consistency.

Usage:
    python executors/enhance/validate_spec.py <spec_json>

Exits:
    0  — no issues found (valid)
    1  — one or more issues found (review required)
    2  — input error (missing file, bad JSON, etc.)

Output (stdout, JSON):
    {
      "valid": true|false,
      "issues": [...],
      "stats": { "total": N, "by_type": {...} }
    }
"""

import sys
import json
from pathlib import Path

VALID_TYPES = {
    "text_overlay", "lower_third", "source_overlay", "zoom_effect",
    "sound_effect", "section_divider", "data_viz", "icon_accent",
    "callout_box", "animated_list", "number_counter", "split_screen",
    "progress_tracker", "map_highlight", "transition",
}

VALID_SFX = {
    "whoosh", "whoosh_soft", "pop", "ding", "swoosh",
    "impact", "click", "transition", "success", "notification",
}

VALID_ANIMATIONS = {
    "none", "fade", "slide_up", "slide_down", "slide_left", "slide_right",
    "scale_bounce", "scale_in", "scale_out", "pop", "typewriter",
    "wipe_right", "wipe_left", "bounce_in", "spring_in", "blur_in",
    "rotate_in", "build_up",
}


def validate(spec_path: str) -> dict:
    path = Path(spec_path)
    if not path.exists():
        return {"valid": False, "issues": [{"type": "error", "message": f"File not found: {spec_path}"}], "stats": {}}

    try:
        spec = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"valid": False, "issues": [{"type": "error", "message": f"Invalid JSON: {e}"}], "stats": {}}

    issues = []

    # Required top-level fields
    for field in ["version", "source_video", "fps", "duration_seconds", "width", "height", "global_style", "sections", "enhancements"]:
        if field not in spec:
            issues.append({"type": "error", "message": f"Missing required field: {field}"})

    if issues:
        return {"valid": False, "issues": issues, "stats": {}}

    duration = spec["duration_seconds"]
    section_ids = {s["id"] for s in spec.get("sections", [])}
    by_type = {}

    for enh in spec.get("enhancements", []):
        eid = enh.get("id", "unknown")
        etype = enh.get("type", "unknown")
        by_type[etype] = by_type.get(etype, 0) + 1

        # Type check
        if etype not in VALID_TYPES:
            issues.append({"type": "warning", "id": eid, "message": f"Unknown enhancement type: {etype}"})

        # Timing checks
        start = enh.get("start_seconds", 0)
        end = enh.get("end_seconds", 0)

        if start >= end:
            issues.append({"type": "error", "id": eid, "message": f"start_seconds ({start}) >= end_seconds ({end})"})

        if start < 0:
            issues.append({"type": "error", "id": eid, "message": f"start_seconds ({start}) is negative"})

        if end > duration + 0.5:
            issues.append({"type": "warning", "id": eid, "message": f"end_seconds ({end}) exceeds video duration ({duration})"})

        # Duration checks
        enh_duration = end - start
        if etype != "sound_effect" and enh_duration < 0.5:
            issues.append({"type": "warning", "id": eid, "message": f"Very short duration ({enh_duration:.1f}s) for {etype}"})

        # Section reference
        section_id = enh.get("section_id")
        if section_id and section_id not in section_ids:
            issues.append({"type": "warning", "id": eid, "message": f"References unknown section: {section_id}"})

        # Content validation
        content = enh.get("content", {})

        if etype == "sound_effect":
            sfx_id = content.get("sfx_id", "")
            if sfx_id not in VALID_SFX:
                issues.append({"type": "warning", "id": eid, "message": f"Unknown sfx_id: {sfx_id}"})
            volume = content.get("volume", 1)
            if not (0 <= volume <= 1):
                issues.append({"type": "warning", "id": eid, "message": f"Volume ({volume}) should be 0-1"})

        # Animation validation
        for anim_field in ["animation_in", "animation_out", "animation"]:
            if anim_field in content:
                anim = content[anim_field]
                if anim not in VALID_ANIMATIONS:
                    issues.append({"type": "warning", "id": eid, "message": f"Unknown animation preset: {anim}"})

    # Check for duplicate IDs
    ids = [e.get("id") for e in spec.get("enhancements", [])]
    seen = set()
    for eid in ids:
        if eid in seen:
            issues.append({"type": "error", "message": f"Duplicate enhancement ID: {eid}"})
        seen.add(eid)

    stats = {
        "total": len(spec.get("enhancements", [])),
        "by_type": by_type,
        "sections": len(spec.get("sections", [])),
        "duration": duration,
    }

    has_errors = any(i["type"] == "error" for i in issues)
    return {"valid": not has_errors, "issues": issues, "stats": stats}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"valid": False, "issues": [{"type": "error", "message": "Usage: validate_spec.py <spec_json>"}]}))
        sys.exit(2)

    result = validate(sys.argv[1])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
