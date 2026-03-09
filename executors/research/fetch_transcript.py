#!/usr/bin/env python3
"""
YouTube Transcript Fetcher
===========================
Fetches captions/subtitles from a YouTube video using yt-dlp.

Usage:
    python3 executors/research/fetch_transcript.py <youtube_url> <output_json>
    python3 executors/research/fetch_transcript.py --help

Arguments:
    youtube_url   Full YouTube URL (e.g. https://www.youtube.com/watch?v=xxxxx)
    output_json   Path where the transcript JSON will be written

Installation:
    pip install yt-dlp

Output JSON format:
    {
      "source": "https://www.youtube.com/watch?v=xxxxx",
      "title": "Video Title",
      "channel": "Channel Name",
      "duration_seconds": 600,
      "full_text": "The complete transcript as a single string...",
      "segments": [
        {"start": 0.0, "end": 4.2, "text": "So today..."},
        ...
      ]
    }

Notes:
    - Prefers manually uploaded English captions over auto-generated
    - Falls back to auto-generated English captions if manual not available
    - If no English captions exist, tries any available language
    - Segments may not be available for all caption types (full_text always provided)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


def print_help() -> None:
    print(__doc__.strip())


def fail(message: str) -> None:
    """Print error JSON to stdout and exit 1."""
    print(json.dumps({"error": message}))
    sys.exit(1)


def check_dependencies() -> None:
    if shutil.which("yt-dlp") is None:
        fail("yt-dlp not found. Install with: pip install yt-dlp")


def parse_vtt_to_segments(vtt_content: str) -> list[dict]:
    """Parse WebVTT content into a list of {start, end, text} segments."""
    segments: list[dict] = []
    lines = vtt_content.strip().split("\n")

    timestamp_pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})"
    )

    i = 0
    while i < len(lines):
        match = timestamp_pattern.match(lines[i])
        if match:
            start_str, end_str = match.group(1), match.group(2)
            start_sec = _timestamp_to_seconds(start_str)
            end_sec = _timestamp_to_seconds(end_str)

            # Collect text lines until next blank line or timestamp
            text_lines: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip() and not timestamp_pattern.match(lines[i]):
                # Strip VTT positioning tags like <c> </c> and alignment tags
                clean = re.sub(r"<[^>]+>", "", lines[i]).strip()
                if clean:
                    text_lines.append(clean)
                i += 1

            text = " ".join(text_lines).strip()
            if text:
                segments.append({
                    "start": round(start_sec, 3),
                    "end": round(end_sec, 3),
                    "text": text,
                })
        else:
            i += 1

    # Deduplicate consecutive segments with identical text (common in auto-captions)
    deduped: list[dict] = []
    for seg in segments:
        if deduped and deduped[-1]["text"] == seg["text"]:
            # Extend the previous segment's end time
            deduped[-1]["end"] = seg["end"]
        else:
            deduped.append(seg)

    return deduped


def _timestamp_to_seconds(ts: str) -> float:
    """Convert HH:MM:SS.mmm to seconds."""
    parts = ts.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def fetch_transcript(url: str, output_path: str) -> None:
    """Fetch transcript from YouTube and write to output_path as JSON."""
    check_dependencies()

    # Create a temp directory for yt-dlp subtitle output
    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = os.path.join(tmpdir, "subs")

        # Try auto-generated first (most common), then manual, then any
        sub_strategies = [
            # Strategy 1: Auto-generated English subs (most videos have these)
            ["--write-auto-subs", "--sub-langs", "en", "--skip-download"],
            # Strategy 2: Manual English subs
            ["--write-subs", "--sub-langs", "en", "--skip-download"],
            # Strategy 3: Any available subs
            ["--write-auto-subs", "--write-subs", "--sub-langs", "en.*,a]en.*", "--skip-download"],
        ]

        vtt_content: str | None = None
        metadata = {"title": "Unknown", "channel": "Unknown", "duration_seconds": 0}

        for strategy in sub_strategies:
            # Clean temp dir of previous attempts
            for f in os.listdir(tmpdir):
                os.remove(os.path.join(tmpdir, f))

            # Combine subtitle fetch + metadata in a single yt-dlp call
            cmd = [
                "yt-dlp",
                *strategy,
                "--sub-format", "vtt",
                "--convert-subs", "vtt",
                "--print", "%(title)s",
                "--print", "%(channel)s",
                "--print", "%(duration)s",
                "-o", output_template,
                url,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            # Parse metadata from stdout (--print lines appear first)
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 3:
                    metadata = {
                        "title": lines[0],
                        "channel": lines[1],
                        "duration_seconds": int(float(lines[2])) if lines[2].replace(".", "").isdigit() else 0,
                    }

            # Look for any .vtt file in the temp dir
            vtt_files = [f for f in os.listdir(tmpdir) if f.endswith(".vtt")]
            if vtt_files:
                vtt_path = os.path.join(tmpdir, vtt_files[0])
                with open(vtt_path, "r", encoding="utf-8") as f:
                    vtt_content = f.read()
                break

        if vtt_content is None:
            fail(
                f"No captions found for {url}. "
                "The video may not have subtitles, or it may be private/age-restricted."
            )

        # Parse VTT into segments
        segments = parse_vtt_to_segments(vtt_content)
        full_text = " ".join(seg["text"] for seg in segments)

        # Build output
        output = {
            "source": url,
            "title": metadata["title"],
            "channel": metadata["channel"],
            "duration_seconds": metadata["duration_seconds"],
            "full_text": full_text,
            "segments": segments,
        }

        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Write JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        # Print JSON to stdout per executor contract
        print(json.dumps({
            "success": True,
            "source": url,
            "title": metadata["title"],
            "channel": metadata["channel"],
            "duration_seconds": metadata["duration_seconds"],
            "segments_count": len(segments),
            "output_file": output_path,
        }))


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print_help()
        sys.exit(0)

    if len(sys.argv) < 3:
        fail("Missing required argument: output_json. Run with --help for usage.")

    url = sys.argv[1]
    output_path = sys.argv[2]

    # Basic URL validation
    if "youtube.com" not in url and "youtu.be" not in url:
        fail(f"URL does not appear to be a YouTube link: {url}")

    fetch_transcript(url, output_path)


if __name__ == "__main__":
    main()
