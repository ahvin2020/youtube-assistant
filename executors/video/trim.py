#!/usr/bin/env python3
"""
Trim helper module for video editing executors.

Provides:
  parse_timestamp(ts: str) -> float
      Parse "HH:MM:SS", "HH:MM:SS.mmm", or raw float-seconds into seconds.

  trim_video(source, start, end, output, re_encode=False) -> dict
      Extract a clip from source between start and end using ffmpeg.
      Returns {"status": "success"} or {"status": "error", "error": ..., "ffmpeg_stderr": ...}
"""

import subprocess
import sys
from pathlib import Path


def parse_timestamp(ts: str) -> float:
    """Parse a timestamp string into seconds (float).

    Accepts:
      "HH:MM:SS"
      "HH:MM:SS.mmm"
      "MM:SS"
      A bare float or int string (treated as raw seconds).
    """
    if isinstance(ts, (int, float)):
        return float(ts)
    ts = ts.strip()
    parts = ts.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        else:
            return float(ts)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Cannot parse timestamp: {ts!r}") from exc


def trim_video(
    source: str,
    start: str,
    end: str,
    output: str,
    re_encode: bool = False,
) -> dict:
    """Extract a clip from source between start and end timestamps.

    Uses ffmpeg with -ss before -i for accurate fast-seeking.
    Stream-copies by default (lossless, fast). Falls back to re-encode
    with libx264/aac when re_encode=True or stream copy fails.

    Returns:
        {"status": "success", "ffmpeg_command": <str>}
        {"status": "error",   "error": <str>, "ffmpeg_stderr": <str>}
    """
    try:
        start_s = parse_timestamp(start)
        end_s = parse_timestamp(end)
    except ValueError as exc:
        return {"status": "error", "error": str(exc), "ffmpeg_stderr": ""}

    duration = end_s - start_s
    if duration <= 0:
        return {
            "status": "error",
            "error": f"Invalid segment: start={start} >= end={end}",
            "ffmpeg_stderr": "",
        }

    Path(output).parent.mkdir(parents=True, exist_ok=True)

    def _run(cmd: list) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if re_encode:
        cmd = [
            "ffmpeg",
            "-ss", str(start_s),       # input seek: fast demuxer-level seeking
            "-i", source,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-vf", "setpts=PTS-STARTPTS",   # reset video PTS to 0 (removes edit-list offset)
            "-c:a", "aac",
            "-b:a", "192k",
            "-af", "asetpts=PTS-STARTPTS",  # reset audio PTS to 0 (keeps A/V in sync)
            "-y",
            output,
        ]
        result = _run(cmd)
        cmd_str = " ".join(f'"{a}"' if " " in a else a for a in cmd)
        if result.returncode == 0:
            return {"status": "success", "ffmpeg_command": cmd_str}
        return {
            "status": "error",
            "error": "ffmpeg re-encode failed",
            "ffmpeg_stderr": result.stderr,
            "ffmpeg_command": cmd_str,
        }

    # Try stream copy first (lossless, fast)
    cmd_copy = [
        "ffmpeg",
        "-ss", str(start_s),
        "-i", source,
        "-t", str(duration),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        "-y",
        output,
    ]
    result = _run(cmd_copy)
    cmd_str = " ".join(f'"{a}"' if " " in a else a for a in cmd_copy)
    if result.returncode == 0:
        return {"status": "success", "ffmpeg_command": cmd_str}

    # Fallback: re-encode
    print("Stream copy failed, falling back to re-encode...", file=sys.stderr)
    cmd_enc = [
        "ffmpeg",
        "-i", source,
        "-ss", str(start_s),       # output seek: frame-accurate (no keyframe pre-roll)
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-vf", "setpts=PTS-STARTPTS",   # reset video PTS to 0 (removes edit-list offset)
        "-c:a", "aac",
        "-b:a", "192k",
        "-af", "asetpts=PTS-STARTPTS",  # reset audio PTS to 0 (keeps A/V in sync)
        "-y",
        output,
    ]
    result2 = _run(cmd_enc)
    cmd_str2 = " ".join(f'"{a}"' if " " in a else a for a in cmd_enc)
    if result2.returncode == 0:
        return {"status": "success", "ffmpeg_command": cmd_str2}

    return {
        "status": "error",
        "error": "ffmpeg failed with both stream copy and re-encode",
        "ffmpeg_stderr": result2.stderr,
        "stream_copy_stderr": result.stderr,
        "ffmpeg_command": cmd_str,
    }
