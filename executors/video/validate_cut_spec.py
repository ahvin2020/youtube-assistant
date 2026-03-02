#!/usr/bin/env python3
"""
Validate Cut Spec Executor
===========================
Checks every keep_segment in a cut_spec.json for internal gaps or overlapping
Whisper segments that may hide false starts or stumbles.

Usage:
    python executors/video/validate_cut_spec.py <transcript_json> <cut_spec_json>

Exits:
    0  — no issues found (valid)
    1  — one or more issues found (review required)
    2  — input error (missing file, bad JSON, etc.)

Output (stdout, JSON):
    {
      "valid": true,
      "issues": []
    }

    or

    {
      "valid": false,
      "issues": [
        {
          "keep_segment_index": 5,
          "keep_segment": {"start": "...", "end": "..."},
          "type": "gap",
          "gap_seconds": 2.231,
          "before_end": "00:01:48.035",
          "after_start": "00:01:50.266",
          "suggestion": "Split keep_segment[5] at this boundary: end at 00:01:48.035, next start at 00:01:50.266"
        }
      ]
    }

Issue types:
  gap      — consecutive transcript segments with a gap > GAP_THRESHOLD seconds.
             A large gap within a kept block usually means a stumble or false start
             that Whisper didn't fully transcribe.
  overlap  — a later transcript segment starts before the previous one ends.
             Whisper hallucination during a pause can produce overlapping segments
             that visually mask a real gap.
"""

import sys
import json
from pathlib import Path

GAP_THRESHOLD = 0.5      # seconds — gaps wider than this trigger a split suggestion
OVERLAP_THRESHOLD = 0.5  # seconds — overlaps smaller than this are Whisper timestamp
                         # imprecision and are ignored; larger ones may mask stumbles


def seconds_to_hms(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:06.3f}"


def parse_timestamp(ts: str) -> float:
    if isinstance(ts, (int, float)):
        return float(ts)
    ts = ts.strip()
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(ts)


def validate(transcript_path: str, cut_spec_path: str) -> dict:
    # --- Load inputs ---
    if not Path(transcript_path).exists():
        return {"error": f"Transcript not found: {transcript_path}"}
    if not Path(cut_spec_path).exists():
        return {"error": f"Cut spec not found: {cut_spec_path}"}

    with open(transcript_path) as f:
        transcript = json.load(f)
    with open(cut_spec_path) as f:
        cut_spec = json.load(f)

    # Whisper output can be {"segments": [...]} or a list directly
    if isinstance(transcript, dict):
        t_segments = transcript.get("segments", [])
    else:
        t_segments = transcript

    keep_segments = cut_spec.get("keep_segments", [])
    issues = []

    for idx, ks in enumerate(keep_segments):
        try:
            ks_start = parse_timestamp(ks["start"])
            ks_end = parse_timestamp(ks["end"])
        except (KeyError, ValueError):
            continue

        # Collect all transcript segments whose start falls within this keep range
        inner = [
            seg for seg in t_segments
            if ks_start <= float(seg.get("start", 0)) < ks_end
        ]
        inner.sort(key=lambda s: float(s.get("start", 0)))

        if len(inner) < 2:
            continue

        for i in range(len(inner) - 1):
            a = inner[i]
            b = inner[i + 1]
            a_end = float(a.get("end", a.get("start", 0)))
            b_start = float(b.get("start", 0))

            # Overlap: next segment starts before current ends
            # Small overlaps (< OVERLAP_THRESHOLD) are Whisper timestamp imprecision
            if b_start < a_end and (a_end - b_start) >= OVERLAP_THRESHOLD:
                issues.append({
                    "keep_segment_index": idx,
                    "keep_segment": {"start": ks["start"], "end": ks["end"]},
                    "type": "overlap",
                    "overlap_seconds": round(a_end - b_start, 3),
                    "segment_a": {"start": seconds_to_hms(float(a.get("start", 0))),
                                  "end": seconds_to_hms(a_end),
                                  "text": a.get("text", "").strip()},
                    "segment_b": {"start": seconds_to_hms(b_start),
                                  "text": b.get("text", "").strip()},
                    "suggestion": (
                        f"Whisper segments overlap inside keep_segment[{idx}] — "
                        f"inspect manually around {seconds_to_hms(a_end)}"
                    ),
                })
                continue  # Don't also report a gap for overlapping segments

            # Gap: next segment starts more than GAP_THRESHOLD after current ends
            gap = b_start - a_end
            if gap > GAP_THRESHOLD:
                issues.append({
                    "keep_segment_index": idx,
                    "keep_segment": {"start": ks["start"], "end": ks["end"]},
                    "type": "gap",
                    "gap_seconds": round(gap, 3),
                    "before_end": seconds_to_hms(a_end),
                    "after_start": seconds_to_hms(b_start),
                    "before_text": a.get("text", "").strip(),
                    "after_text": b.get("text", "").strip(),
                    "suggestion": (
                        f"Split keep_segment[{idx}] at this boundary: "
                        f"end at {seconds_to_hms(a_end)}, next start at {seconds_to_hms(b_start)}"
                    ),
                })

    return {"valid": len(issues) == 0, "issues": issues}


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if len(args) < 2:
        print(json.dumps({
            "error": "Usage: validate_cut_spec.py <transcript_json> <cut_spec_json>"
        }, indent=2))
        sys.exit(2)

    result = validate(args[0], args[1])

    if "error" in result:
        print(json.dumps(result, indent=2))
        sys.exit(2)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
