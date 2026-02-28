#!/usr/bin/env python3
"""
Split Silences Executor
========================
Post-processes a cut_spec.json to sub-split kept segments at detected silence
boundaries. Uses silences.json (from detect_silence.py) to find silent periods
that fall WITHIN kept segments and removes them.

Run AFTER the cut spec has been built (Mode B). Operates in-place on cut_spec.json.

Why this is needed: Mode B analysis aligns cut boundaries to Whisper segment
boundaries. If a speaker pauses in the middle of a sentence, the pause is captured
by ffmpeg's silencedetect but stays INSIDE a kept segment. This executor sub-cuts
those internal silences out.

Usage:
    python executors/video/split_silences.py <cut_spec_json> <silences_json> [--min-gap SECONDS]
    python executors/video/split_silences.py --help

Arguments:
    cut_spec_json    Path to cut_spec.json (updated in-place)
    silences_json    Path to silences.json (from detect_silence.py)
    --min-gap        Minimum silence duration in seconds to split at (default: 0.8)

Output:
    Prints a JSON result object to stdout.
    Updates cut_spec.json in-place.
    Exits 0 on success, 1 on failure.
"""

import sys
import json
from pathlib import Path


def parse_timestamp(ts: str) -> float:
    """Convert HH:MM:SS.mmm to float seconds."""
    parts = ts.split(':')
    h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
    return h * 3600 + m * 60 + s


def seconds_to_ts(total_seconds: float) -> str:
    """Convert float seconds to HH:MM:SS.mmm."""
    h = int(total_seconds // 3600)
    m = int((total_seconds % 3600) // 60)
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def split_at_silences(cut_spec_path: str, silences_path: str, min_gap: float = 0.8) -> dict:
    for path, label in [(cut_spec_path, "cut_spec"), (silences_path, "silences")]:
        if not Path(path).exists():
            return {"status": "error", "error": f"{label} file not found: {path}"}

    with open(cut_spec_path) as f:
        cut_spec = json.load(f)
    with open(silences_path) as f:
        silences_data = json.load(f)

    # Accept both {"silences": [...]} and a bare list
    raw_silences = silences_data if isinstance(silences_data, list) else silences_data.get("silences", [])
    # Filter to silences that meet the minimum gap threshold
    silences = [s for s in raw_silences if s.get("duration", s["end"] - s["start"]) >= min_gap]

    original_keep = cut_spec.get("keep_segments", [])
    removed = list(cut_spec.get("removed_segments", []))

    # Small buffer on each side of the silence cut (50ms) to avoid clipping speech
    BUFFER = 0.05
    # Skip sub-segments shorter than this
    MIN_SUBSEG_SECS = 0.4

    new_keep = []
    splits_made = 0

    for seg in original_keep:
        seg_start = parse_timestamp(seg["start"])
        seg_end = parse_timestamp(seg["end"])
        base_note = seg.get("note", "clean speech segment")

        # Find silences that overlap with this kept segment
        # A silence overlaps if: silence.start < seg.end AND silence.end > seg.start
        overlapping = [
            s for s in silences
            if s["start"] < seg_end and s["end"] > seg_start
        ]

        if not overlapping:
            new_keep.append(seg)
            continue

        # Sort by start time and build sub-segments
        overlapping.sort(key=lambda s: s["start"])

        # Build a list of (silence_start, silence_end) clipped to [seg_start, seg_end]
        split_points = []
        for s in overlapping:
            s_start = max(s["start"], seg_start)
            s_end = min(s["end"], seg_end)
            if s_end - s_start >= min_gap:
                split_points.append((s_start, s_end))

        if not split_points:
            new_keep.append(seg)
            continue

        # Merge overlapping split points
        merged = [split_points[0]]
        for s_start, s_end in split_points[1:]:
            if s_start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(s_end, merged[-1][1]))
            else:
                merged.append((s_start, s_end))

        total_parts = len(merged) + 1
        sub_start = seg_start

        for i, (silence_start, silence_end) in enumerate(merged):
            part_num = i + 1
            sub_end = silence_start + BUFFER

            if sub_end - sub_start >= MIN_SUBSEG_SECS:
                label = f"{base_note} (pt {part_num}/{total_parts})" if total_parts > 1 else base_note
                new_keep.append({
                    "start": seconds_to_ts(sub_start),
                    "end": seconds_to_ts(sub_end),
                    "note": label
                })

            # Record the silence in removed_segments
            cut_start = silence_start + BUFFER
            cut_end = silence_end - BUFFER
            if cut_end > cut_start:
                removed.append({
                    "start": seconds_to_ts(cut_start),
                    "end": seconds_to_ts(cut_end),
                    "reason": f"silence within segment ({silence_end - silence_start:.1f}s)"
                })

            splits_made += 1
            sub_start = silence_end - BUFFER

        # Final sub-segment after last silence
        if seg_end - sub_start >= MIN_SUBSEG_SECS:
            label = f"{base_note} (pt {total_parts}/{total_parts})" if total_parts > 1 else base_note
            new_keep.append({
                "start": seconds_to_ts(sub_start),
                "end": seconds_to_ts(seg_end),
                "note": label
            })

    # Sort removed_segments chronologically
    removed.sort(key=lambda x: parse_timestamp(x["start"]))

    cut_spec["keep_segments"] = new_keep
    cut_spec["removed_segments"] = removed

    with open(cut_spec_path, "w") as f:
        json.dump(cut_spec, f, indent=2)

    return {
        "status": "success",
        "splits_made": splits_made,
        "keep_segments_before": len(original_keep),
        "keep_segments_after": len(new_keep),
        "message": f"Split {splits_made} internal silence(s) — {len(original_keep)} → {len(new_keep)} keep segments"
    }


def main():
    args = sys.argv[1:]

    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)

    if len(args) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Usage: split_silences.py <cut_spec_json> <silences_json> [--min-gap SECONDS]"
        }, indent=2))
        sys.exit(1)

    cut_spec_path = args[0]
    silences_path = args[1]
    min_gap = 0.8

    for i, arg in enumerate(args):
        if arg == '--min-gap' and i + 1 < len(args):
            try:
                min_gap = float(args[i + 1])
            except ValueError:
                print(json.dumps({"status": "error", "error": f"Invalid --min-gap value: {args[i+1]}"}))
                sys.exit(1)

    result = split_at_silences(cut_spec_path, silences_path, min_gap)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == '__main__':
    main()
