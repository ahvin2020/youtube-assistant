#!/usr/bin/env python3
"""
Video Transcription Executor
=============================
Transcribes a video file using local OpenAI Whisper.
Extracts audio first (via ffmpeg), then runs Whisper on the audio track.

Usage:
    python3 executors/video/transcribe.py <video_file> <output_json>
    python3 executors/video/transcribe.py <video_file> <output_json> --model small
    python3 executors/video/transcribe.py --help

Arguments:
    video_file    Path to the source video file
    output_json   Path where the transcript JSON will be written
    --model       Whisper model size: tiny, base, small, medium, large (default: base)
    --language    Language code, e.g. 'en' (default: en)

Installation:
    pip install openai-whisper
    brew install ffmpeg  (if not already installed)

Output JSON format:
    {
      "source": "video.mp4",
      "duration_seconds": 342.5,
      "language": "en",
      "model": "base",
      "segments": [
        {"id": 0, "start": 0.0, "end": 4.2, "start_time": "00:00:00", "end_time": "00:04:20", "text": "So today..."},
        ...
      ]
    }

Notes:
    - The base model (~74MB) is fast and sufficient for retake detection
    - The small model (~244MB) gives better accuracy for paraphrased speech
    - First run downloads the model weights (~74MB for base) to ~/.cache/whisper/
    - Audio is pre-split at silence boundaries before transcription so that
      mid-take restarts are captured as separate segments rather than collapsed.
      Silence threshold: -35 dB, minimum silence duration: 0.3s.
"""
from __future__ import annotations

import sys
import json
import re
import time
import shutil
import subprocess
import tempfile
import os
from pathlib import Path

# Silence detection tuning — used during audio pre-split
SILENCE_THRESH_DB: int = -35      # dBFS — more sensitive than detect_silence.py default
SILENCE_MIN_DURATION: float = 0.3  # seconds — captures short breath-gap restarts
MIN_SEGMENT_DURATION: float = 0.5  # seconds — skip speech chunks shorter than this


def to_mmss(seconds: float) -> str:
    """Convert a float seconds value to MM:SS:cc string (e.g. 125.617 → '02:05:61')."""
    total_cs = round(seconds * 100)
    cs = total_cs % 100
    total_s = total_cs // 100
    return f"{total_s // 60:02d}:{total_s % 60:02d}:{cs:02d}"


def extract_audio(video_path: str, audio_path: str) -> dict:
    """Extract audio track from video to a temporary WAV file."""
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vn',              # no video
        '-acodec', 'pcm_s16le',  # 16-bit PCM (Whisper's preferred format)
        '-ar', '16000',     # 16kHz sample rate (Whisper's native rate)
        '-ac', '1',         # mono
        '-y',
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        return {
            "status": "error",
            "error": "ffmpeg failed to extract audio",
            "stderr": result.stderr
        }
    return {"status": "success"}


def detect_silences(
    audio_path: str,
    thresh_db: int,
    min_duration: float,
    total_duration: float = 0.0
) -> list[tuple[float, float]]:
    """
    Run ffmpeg silencedetect on a WAV file.
    Returns a list of (start, end) tuples for each detected silence interval.
    On any ffmpeg failure, returns [] so the caller falls back to full-file transcription.
    """
    cmd = [
        'ffmpeg',
        '-i', audio_path,
        '-af', f'silencedetect=n={thresh_db}dB:d={min_duration}',
        '-f', 'null',
        '-'
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as e:
        print(f"[detect_silences] ffmpeg failed: {e}", file=sys.stderr)
        return []

    stderr = result.stderr
    start_times = [float(m) for m in re.findall(r'silence_start: ([0-9.]+)', stderr)]
    end_times   = [float(m) for m in re.findall(r'silence_end: ([0-9.]+)', stderr)]

    silences = list(zip(start_times, end_times))

    # Handle trailing silence that reaches end of file (silence_end is missing)
    if len(start_times) > len(end_times):
        silences.append((start_times[len(end_times)], total_duration))

    return [(round(s, 3), round(e, 3)) for s, e in silences]


def compute_speech_segments(
    silences: list[tuple[float, float]],
    total_duration: float,
    min_segment_duration: float = 0.5
) -> list[tuple[float, float]]:
    """
    Invert a list of (silence_start, silence_end) tuples to get speech segments.
    Skips segments shorter than min_segment_duration seconds.
    Returns [(start, end), ...] for each speech region.
    """
    if not silences:
        return [(0.0, total_duration)]

    segments = []
    cursor = 0.0
    for (s_start, s_end) in silences:
        if s_start > cursor:
            if s_start - cursor >= min_segment_duration:
                segments.append((round(cursor, 3), round(s_start, 3)))
        cursor = s_end

    # Final segment after last silence
    if total_duration > cursor and total_duration - cursor >= min_segment_duration:
        segments.append((round(cursor, 3), round(total_duration, 3)))

    # Safety: if all segments were too short, return full duration
    if not segments:
        return [(0.0, total_duration)]

    return segments


def extract_audio_segment(
    audio_path: str,
    start: float,
    end: float,
    output_path: str
) -> dict:
    """Extract a time-bounded slice of a WAV file using ffmpeg."""
    duration = round(end - start, 6)
    cmd = [
        'ffmpeg',
        '-ss', str(start),
        '-t', str(duration),
        '-i', audio_path,
        '-y',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        return {
            "status": "error",
            "error": f"ffmpeg failed to extract audio segment [{start}s-{end}s]",
            "stderr": result.stderr
        }
    return {"status": "success"}


def transcribe_audio(audio_path: str, model_name: str, language: str, model=None) -> dict:
    """Run Whisper transcription on an audio file.

    If a pre-loaded Whisper model is provided via `model`, it is used directly
    (avoids reloading the model for every speech segment in the pre-split path).
    """
    if model is None:
        try:
            import whisper
        except ImportError:
            return {
                "status": "error",
                "error": (
                    "openai-whisper is not installed. "
                    "Install it with: pip install openai-whisper"
                )
            }
        try:
            model = whisper.load_model(model_name)
        except Exception as e:
            return {"status": "error", "error": f"Failed to load Whisper model '{model_name}': {e}"}

    transcribe_kwargs = {
        "verbose": False,
        "condition_on_previous_text": False,  # capture restarts/repeated phrases faithfully
    }
    if language:
        transcribe_kwargs["language"] = language

    try:
        result = model.transcribe(audio_path, **transcribe_kwargs)
    except Exception as e:
        return {"status": "error", "error": f"Whisper transcription failed: {e}"}

    # Extract segments
    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "id": seg.get("id", 0),
            "start": round(seg.get("start", 0.0), 3),
            "end": round(seg.get("end", 0.0), 3),
            "text": seg.get("text", "").strip()
        })

    return {
        "status": "success",
        "language": result.get("language", "unknown"),
        "segments": segments,
    }


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return 0.0
    try:
        info = json.loads(result.stdout)
        return float(info.get("format", {}).get("duration", 0.0))
    except (json.JSONDecodeError, ValueError):
        return 0.0


def transcribe_video(video_path: str, output_json: str, model_name: str = "base", language: str = "en") -> dict:
    """
    Full pipeline: extract audio from video, run Whisper, save transcript JSON.
    Audio is pre-split at silence boundaries so mid-take restarts are captured.
    """
    t_start = time.time()

    if not Path(video_path).exists():
        return {"status": "error", "error": f"Video file not found: {video_path}"}

    Path(output_json).parent.mkdir(parents=True, exist_ok=True)

    duration = get_video_duration(video_path)

    print(f"Extracting audio from {video_path}...", file=sys.stderr)
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        audio_path = tmp.name

    try:
        extract_result = extract_audio(video_path, audio_path)
        if extract_result["status"] != "success":
            return extract_result

        # Detect silence boundaries in the extracted WAV
        print("Detecting silence boundaries...", file=sys.stderr)
        silences = detect_silences(audio_path, SILENCE_THRESH_DB, SILENCE_MIN_DURATION, duration)
        speech_segments = compute_speech_segments(silences, duration, MIN_SEGMENT_DURATION)

        print(f"Transcribing with Whisper model '{model_name}'...", file=sys.stderr)
        print("(First run will download model weights — this may take a moment)", file=sys.stderr)

        # Load Whisper model once before the segment loop
        try:
            import whisper
            loaded_model = whisper.load_model(model_name)
        except ImportError:
            return {
                "status": "error",
                "error": "openai-whisper is not installed. Install it with: pip install openai-whisper"
            }
        except Exception as e:
            return {"status": "error", "error": f"Failed to load Whisper model '{model_name}': {e}"}

        if len(speech_segments) <= 1:
            # No split points — transcribe full audio as before
            print("No split points found — transcribing full audio.", file=sys.stderr)
            transcribe_result = transcribe_audio(audio_path, model_name, language, model=loaded_model)
            if transcribe_result["status"] != "success":
                return transcribe_result
            all_segments = transcribe_result["segments"]

        else:
            # Pre-split path: transcribe each speech segment independently
            print(
                f"Pre-splitting into {len(speech_segments)} speech segment(s) at silence boundaries.",
                file=sys.stderr
            )

            seg_temp_dir = tempfile.mkdtemp(prefix="transcribe_segs_")
            try:
                all_segments = []
                global_seg_id = 0

                for i, (seg_start, seg_end) in enumerate(speech_segments):
                    seg_wav = os.path.join(seg_temp_dir, f"seg_{i:04d}.wav")

                    slice_result = extract_audio_segment(audio_path, seg_start, seg_end, seg_wav)
                    if slice_result["status"] != "success":
                        print(
                            f"[warn] Failed to extract segment {i} [{seg_start}s-{seg_end}s], skipping: "
                            f"{slice_result.get('error', '')}",
                            file=sys.stderr
                        )
                        continue

                    t_result = transcribe_audio(seg_wav, model_name, language, model=loaded_model)
                    if t_result["status"] != "success":
                        print(
                            f"[warn] Whisper failed on segment {i} [{seg_start}s-{seg_end}s], skipping: "
                            f"{t_result.get('error', '')}",
                            file=sys.stderr
                        )
                        if os.path.exists(seg_wav):
                            os.unlink(seg_wav)
                        continue

                    # Offset timestamps back to original video timeline
                    for seg in t_result["segments"]:
                        all_segments.append({
                            "id": global_seg_id,
                            "start": round(seg["start"] + seg_start, 3),
                            "end":   round(seg["end"]   + seg_start, 3),
                            "text":  seg["text"]
                        })
                        global_seg_id += 1

                    if os.path.exists(seg_wav):
                        os.unlink(seg_wav)

            finally:
                shutil.rmtree(seg_temp_dir, ignore_errors=True)

            if not all_segments:
                return {
                    "status": "error",
                    "error": "All speech segments failed to transcribe. Check ffmpeg and Whisper installation."
                }

            transcribe_result = {
                "status": "success",
                "language": language,
                "segments": all_segments,
            }

    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)

    for seg in transcribe_result["segments"]:
        seg["start_time"] = to_mmss(seg["start"])
        seg["end_time"] = to_mmss(seg["end"])

    transcript = {
        "source": str(Path(video_path).resolve()),
        "duration_seconds": round(duration, 3),
        "language": transcribe_result["language"],
        "model": model_name,
        "segments": transcribe_result["segments"],
    }

    with open(output_json, 'w') as f:
        json.dump(transcript, f, indent=2)

    elapsed = round(time.time() - t_start, 1)
    print(f"Transcript saved to: {output_json}", file=sys.stderr)
    print(f"  Segments: {len(transcript['segments'])}", file=sys.stderr)
    print(f"  Elapsed:  {elapsed}s", file=sys.stderr)

    return {
        "status": "success",
        "transcript_file": str(Path(output_json).resolve()),
        "source_file": str(Path(video_path).resolve()),
        "duration_seconds": duration,
        "language": transcript["language"],
        "segment_count": len(transcript["segments"]),
        "elapsed_seconds": elapsed,
    }


def main():
    args = sys.argv[1:]

    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)

    if len(args) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Usage: transcribe.py <video_file> <output_json> [--model base] [--language en]"
        }, indent=2))
        sys.exit(1)

    video_path = args[0]
    output_json = args[1]
    model_name = "base"
    language = "en"

    i = 2
    while i < len(args):
        if args[i] == '--model' and i + 1 < len(args):
            model_name = args[i + 1]
            i += 2
        elif args[i] == '--language' and i + 1 < len(args):
            language = args[i + 1]
            i += 2
        else:
            i += 1

    result = transcribe_video(video_path, output_json, model_name, language)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['status'] == 'success' else 1)


if __name__ == '__main__':
    main()
