#!/usr/bin/env python3
"""
Video Transcription Executor
=============================
Transcribes a video file using local OpenAI Whisper.
Extracts audio first (via ffmpeg), then runs Whisper on the audio track.

Usage:
    python3 executors/video/transcribe.py <video_file> <output_json>
    python3 executors/video/transcribe.py <video_file> <output_json> --model small --workers 4
    python3 executors/video/transcribe.py --help

Arguments:
    video_file    Path to the source video file
    output_json   Path where the transcript JSON will be written
    --model       Whisper model size: tiny, base, small, medium, large (default: base)
    --language    Language code, e.g. 'en' (default: en)
    --workers     Number of parallel transcription workers (default: 2, max: cpu_count capped at 4)
                  Each worker loads its own model copy — memory scales with workers.
                  Use 1 to disable parallelism.

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
from concurrent.futures import ProcessPoolExecutor, as_completed
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


def _transcribe_worker(batch: list, model_name: str, language: str) -> list:
    """Worker function for parallel transcription (runs in a separate process).

    Each worker loads its own Whisper model copy and transcribes its batch of
    segment WAVs sequentially.  Returns a list of result dicts, one per segment,
    in the same order as the input batch.

    batch items: {"index": int, "seg_start": float, "wav_path": str}
    """
    import whisper as _whisper

    model = _whisper.load_model(model_name)

    transcribe_kwargs = {
        "verbose": False,
        "condition_on_previous_text": False,
    }
    if language:
        transcribe_kwargs["language"] = language

    results = []
    for item in batch:
        try:
            raw = model.transcribe(item["wav_path"], **transcribe_kwargs)
            segments = []
            for seg in raw.get("segments", []):
                segments.append({
                    "start": round(seg.get("start", 0.0) + item["seg_start"], 3),
                    "end":   round(seg.get("end", 0.0)   + item["seg_start"], 3),
                    "text":  seg.get("text", "").strip(),
                })
            results.append({
                "index": item["index"],
                "status": "success",
                "segments": segments,
            })
        except Exception as e:
            results.append({
                "index": item["index"],
                "status": "error",
                "error": str(e),
            })
    return results


def _split_into_batches(items: list, n_batches: int) -> list:
    """Split a list into n roughly equal batches (round-robin for balance)."""
    batches = [[] for _ in range(n_batches)]
    for i, item in enumerate(items):
        batches[i % n_batches].append(item)
    return [b for b in batches if b]


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


def transcribe_video(video_path: str, output_json: str, model_name: str = "base",
                      language: str = "en", workers: int = 2) -> dict:
    """
    Full pipeline: extract audio from video, run Whisper, save transcript JSON.
    Audio is pre-split at silence boundaries so mid-take restarts are captured.
    When workers > 1, speech segments are transcribed in parallel across processes.
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
            actual_workers = min(workers, len(speech_segments))
            parallel_label = f" across {actual_workers} workers" if actual_workers > 1 else ""
            print(
                f"Pre-splitting into {len(speech_segments)} speech segment(s) "
                f"at silence boundaries{parallel_label}.",
                file=sys.stderr
            )

            seg_temp_dir = tempfile.mkdtemp(prefix="transcribe_segs_")
            try:
                # Phase A — Extract all segment WAVs (sequential, fast I/O)
                batch_items = []
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

                    batch_items.append({
                        "index": i,
                        "seg_start": seg_start,
                        "wav_path": seg_wav,
                    })

                if not batch_items:
                    return {
                        "status": "error",
                        "error": "All speech segments failed to extract. Check ffmpeg installation."
                    }

                # Phase B — Transcribe (parallel or sequential)
                all_segments = []

                if actual_workers <= 1:
                    # Sequential path — reuse already-loaded model (no multiprocessing overhead)
                    transcribe_kwargs = {
                        "verbose": False,
                        "condition_on_previous_text": False,
                    }
                    if language:
                        transcribe_kwargs["language"] = language

                    for item in batch_items:
                        print(f"  [{item['index']+1}/{len(speech_segments)}] Transcribing...", file=sys.stderr)
                        try:
                            raw = loaded_model.transcribe(item["wav_path"], **transcribe_kwargs)
                            for seg in raw.get("segments", []):
                                all_segments.append({
                                    "start": round(seg.get("start", 0.0) + item["seg_start"], 3),
                                    "end":   round(seg.get("end", 0.0)   + item["seg_start"], 3),
                                    "text":  seg.get("text", "").strip(),
                                })
                        except Exception as e:
                            print(f"[warn] Whisper failed on segment {item['index']}, skipping: {e}",
                                  file=sys.stderr)
                else:
                    # Parallel path — distribute across worker processes
                    del loaded_model  # free memory before forking workers
                    batches = _split_into_batches(batch_items, actual_workers)
                    print(f"  Dispatching {len(batch_items)} segments to {len(batches)} workers...",
                          file=sys.stderr)

                    worker_results = []
                    with ProcessPoolExecutor(max_workers=len(batches)) as pool:
                        futures = {
                            pool.submit(_transcribe_worker, batch, model_name, language): idx
                            for idx, batch in enumerate(batches)
                        }
                        for future in as_completed(futures):
                            worker_idx = futures[future]
                            try:
                                results = future.result()
                                worker_results.extend(results)
                                done_count = len(worker_results)
                                print(f"  Worker {worker_idx+1} done — "
                                      f"{done_count}/{len(batch_items)} segments transcribed",
                                      file=sys.stderr)
                            except Exception as e:
                                print(f"[warn] Worker {worker_idx+1} failed: {e}", file=sys.stderr)

                    # Phase C — Merge results in original segment order
                    worker_results.sort(key=lambda r: r["index"])
                    for r in worker_results:
                        if r["status"] == "success":
                            all_segments.extend(r["segments"])
                        else:
                            print(f"[warn] Segment {r['index']} failed: {r.get('error', '')}",
                                  file=sys.stderr)

                # Clean up extracted WAVs
                for item in batch_items:
                    try:
                        os.unlink(item["wav_path"])
                    except OSError:
                        pass

            finally:
                shutil.rmtree(seg_temp_dir, ignore_errors=True)

            if not all_segments:
                return {
                    "status": "error",
                    "error": "All speech segments failed to transcribe. Check ffmpeg and Whisper installation."
                }

            # Sort by start time to ensure chronological order
            all_segments.sort(key=lambda s: s["start"])

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
    workers = 2

    i = 2
    while i < len(args):
        if args[i] == '--model' and i + 1 < len(args):
            model_name = args[i + 1]
            i += 2
        elif args[i] == '--language' and i + 1 < len(args):
            language = args[i + 1]
            i += 2
        elif args[i] == '--workers' and i + 1 < len(args):
            try:
                workers = max(1, min(int(args[i + 1]), os.cpu_count() or 4, 4))
            except ValueError:
                workers = 2
            i += 2
        else:
            i += 1

    result = transcribe_video(video_path, output_json, model_name, language, workers=workers)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['status'] == 'success' else 1)


if __name__ == '__main__':
    main()
