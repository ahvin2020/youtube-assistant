#!/usr/bin/env python3
"""
Detect Silence Executor
=======================
Detects silence segments in a video file using ffmpeg's silencedetect filter.

Usage:
    python3 executors/video/detect_silence.py <source_video> <output_json>
    python3 executors/video/detect_silence.py <source_video> <output_json> --duration 0.5
    python3 executors/video/detect_silence.py <source_video> <output_json> --duration 0.5 --threshold -30

Arguments:
    source_video   Path to source video file
    output_json    Path to write the output JSON
    --duration     Minimum silence duration in seconds to detect (default: 0.5)
    --threshold    Silence threshold in dB (default: -30). More negative = more sensitive.

Output JSON:
    {
      "source": "workspace/input/video.mp4",
      "silence_duration_threshold": 0.5,
      "silence_threshold_db": -30,
      "silences": [
        {"start": 4.21, "end": 6.08, "duration": 1.87},
        ...
      ],
      "total_silence_seconds": 12.3,
      "silence_count": 5
    }

Exits 0 on success, 1 on failure.
"""
from __future__ import annotations

import sys
import json
import re
import subprocess
from pathlib import Path


def detect_silence(source: str, output_json: str, duration: float = 0.5, threshold: int = -30) -> dict:
    """
    Run ffmpeg silencedetect filter and parse the output.

    Returns a result dict with status and silence segments.
    """
    if not Path(source).exists():
        return {"status": "error", "error": f"Source file not found: {source}"}

    # ffmpeg silencedetect writes to stderr, not stdout
    # -f null - means discard video output (we only want the filter log)
    cmd = [
        'ffmpeg',
        '-i', source,
        '-af', f'silencedetect=noise={threshold}dB:d={duration}',
        '-f', 'null',
        '-'
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        return {"status": "error", "error": "ffmpeg not found. Install with: brew install ffmpeg"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "ffmpeg timed out after 5 minutes"}

    # ffmpeg exits non-zero only on hard failures; silencedetect always writes to stderr
    if result.returncode != 0 and 'silencedetect' not in result.stderr:
        return {
            "status": "error",
            "error": "ffmpeg failed",
            "stderr": result.stderr
        }

    # Parse silence_start and silence_end markers from stderr
    stderr = result.stderr

    start_times = [float(m) for m in re.findall(r'silence_start: ([0-9.]+)', stderr)]
    end_times   = [float(m) for m in re.findall(r'silence_end: ([0-9.]+)', stderr)]

    silences = []
    for i, (s, e) in enumerate(zip(start_times, end_times)):
        silences.append({
            "start": round(s, 3),
            "end": round(e, 3),
            "duration": round(e - s, 3)
        })

    # Handle trailing silence that reaches end of file (silence_end may be missing)
    if len(start_times) > len(end_times):
        # Get video duration via ffprobe
        probe_cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            source
        ]
        probe = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        if probe.returncode == 0:
            end_of_file = float(probe.stdout.strip())
            s = start_times[len(end_times)]
            silences.append({
                "start": round(s, 3),
                "end": round(end_of_file, 3),
                "duration": round(end_of_file - s, 3)
            })

    total_silence = round(sum(seg["duration"] for seg in silences), 3)

    output = {
        "status": "success",
        "source": str(Path(source).resolve()),
        "silence_duration_threshold": duration,
        "silence_threshold_db": threshold,
        "silences": silences,
        "total_silence_seconds": total_silence,
        "silence_count": len(silences)
    }

    # Write JSON output file
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, 'w') as f:
        json.dump(output, f, indent=2)

    return output


def main():
    args = sys.argv[1:]

    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)

    if len(args) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Usage: detect_silence.py <source_video> <output_json> [--duration 0.5] [--threshold -30]"
        }, indent=2))
        sys.exit(1)

    source = args[0]
    output_json = args[1]

    # Parse optional flags
    duration = 0.5
    threshold = -30

    i = 2
    while i < len(args):
        if args[i] == '--duration' and i + 1 < len(args):
            duration = float(args[i + 1])
            i += 2
        elif args[i] == '--threshold' and i + 1 < len(args):
            threshold = int(args[i + 1])
            i += 2
        else:
            i += 1

    result = detect_silence(source, output_json, duration, threshold)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['status'] == 'success' else 1)


if __name__ == '__main__':
    main()
