#!/usr/bin/env python3
"""
Video Transcription Executor
=============================
Transcribes a video file using Whisper. Supports two engines:
- **mlx** (default on Apple Silicon): mlx-whisper with Metal GPU acceleration
- **faster-whisper**: CTranslate2 backend on CPU, ~4x faster than openai-whisper

Usage:
    python3 executors/video/transcribe.py <video_file> <output_json>
    python3 executors/video/transcribe.py <video_file> <output_json> --engine mlx --model large-v3
    python3 executors/video/transcribe.py <video_file> <output_json> --engine faster-whisper --model small --workers 4
    python3 executors/video/transcribe.py --help

Arguments:
    video_file    Path to the source video file
    output_json   Path where the transcript JSON will be written
    --engine      Transcription engine: mlx (default), faster-whisper
    --model       Whisper model size: tiny, base, small, medium, large-v3-turbo, large-v3 (default: medium)
                  For mlx engine, maps to mlx-community HF repos automatically.
    --language    Language code, e.g. 'en' (default: en)
    --workers     Number of parallel transcription workers (default: 2, max: cpu_count capped at 4)
                  Only used with faster-whisper engine. Ignored for mlx.

Installation:
    pip install mlx-whisper          # for mlx engine (Apple Silicon only)
    pip install faster-whisper       # for faster-whisper engine
    brew install ffmpeg

Output JSON format:
    {
      "source": "video.mp4",
      "duration_seconds": 342.5,
      "language": "en",
      "model": "medium",
      "engine": "mlx",
      "segments": [
        {"id": 0, "start": 0.0, "end": 4.2, "start_time": "00:00:00", "end_time": "00:04:20", "text": "So today..."},
        ...
      ]
    }

Notes:
    - mlx engine uses Apple Silicon GPU (Metal) — fastest on Mac, supports large-v3
    - faster-whisper uses CTranslate2 (int8 quantization on CPU)
    - First run downloads model weights to ~/.cache/huggingface/
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

# MLX model name mapping: short name → HuggingFace repo
MLX_MODEL_MAP: dict[str, str] = {
    "tiny":           "mlx-community/whisper-tiny-mlx",
    "base":           "mlx-community/whisper-base-mlx-q4",
    "small":          "mlx-community/whisper-small-mlx",
    "medium":         "mlx-community/whisper-medium-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "large-v3":       "mlx-community/whisper-large-v3-mlx",
    "large":          "mlx-community/whisper-large-v3-turbo",
}


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


def _load_model(model_name: str):
    """Load a faster-whisper model with int8 quantization for speed."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None, {
            "status": "error",
            "error": (
                "faster-whisper is not installed. "
                "Install it with: pip install faster-whisper"
            )
        }
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        return model, None
    except Exception as e:
        return None, {"status": "error", "error": f"Failed to load Whisper model '{model_name}': {e}"}


def transcribe_audio(audio_path: str, model_name: str, language: str, model=None) -> dict:
    """Run Whisper transcription on an audio file.

    If a pre-loaded model is provided via `model`, it is used directly
    (avoids reloading the model for every speech segment in the pre-split path).
    """
    if model is None:
        model, err = _load_model(model_name)
        if err:
            return err

    try:
        segments_gen, info = model.transcribe(
            audio_path,
            language=language or None,
            condition_on_previous_text=False,  # capture restarts/repeated phrases faithfully
        )
    except Exception as e:
        return {"status": "error", "error": f"Whisper transcription failed: {e}"}

    # Extract segments (generator must be consumed)
    segments = []
    for seg in segments_gen:
        segments.append({
            "id": seg.id,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip()
        })

    return {
        "status": "success",
        "language": info.language,
        "segments": segments,
    }


def transcribe_audio_mlx(audio_path: str, model_name: str, language: str,
                          seg_start: float = 0.0) -> dict:
    """Run MLX Whisper transcription on an audio file.

    Uses Apple Silicon GPU (Metal) for acceleration. No workers needed —
    MLX handles parallelism internally.

    seg_start: offset to add to all timestamps (for pre-split segments).
    """
    try:
        import mlx_whisper
    except ImportError:
        return {
            "status": "error",
            "error": (
                "mlx-whisper is not installed. "
                "Install it with: pip install mlx-whisper"
            )
        }

    hf_repo = MLX_MODEL_MAP.get(model_name, model_name)

    try:
        result = mlx_whisper.transcribe(
            audio_path,
            path_or_hf_repo=hf_repo,
            language=language or None,
            condition_on_previous_text=False,
            word_timestamps=False,
            verbose=False,
        )
    except Exception as e:
        return {"status": "error", "error": f"MLX Whisper transcription failed: {e}"}

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": round(seg["start"] + seg_start, 3),
            "end": round(seg["end"] + seg_start, 3),
            "text": seg["text"].strip(),
        })

    return {
        "status": "success",
        "language": result.get("language", language),
        "segments": segments,
    }


def _transcribe_worker(batch: list, model_name: str, language: str) -> list:
    """Worker function for parallel transcription (runs in a separate process).

    Each worker loads its own model copy and transcribes its batch of
    segment WAVs sequentially.  Returns a list of result dicts, one per segment,
    in the same order as the input batch.

    batch items: {"index": int, "seg_start": float, "wav_path": str}
    """
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")

    results = []
    for item in batch:
        try:
            segments_gen, _info = model.transcribe(
                item["wav_path"],
                language=language or None,
                condition_on_previous_text=False,
            )
            segments = []
            for seg in segments_gen:
                segments.append({
                    "start": round(seg.start + item["seg_start"], 3),
                    "end":   round(seg.end   + item["seg_start"], 3),
                    "text":  seg.text.strip(),
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


def transcribe_video(video_path: str, output_json: str, model_name: str = "medium",
                      language: str = "en", workers: int = 2,
                      engine: str = "mlx") -> dict:
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

        engine_label = "MLX" if engine == "mlx" else "faster-whisper"
        model_label = MLX_MODEL_MAP.get(model_name, model_name) if engine == "mlx" else model_name
        print(f"Transcribing with {engine_label} model '{model_label}'...", file=sys.stderr)
        print("(First run will download model weights — this may take a moment)", file=sys.stderr)

        if engine == "mlx":
            # ── MLX engine path ──
            # MLX uses Metal GPU — no workers needed, process segments sequentially
            # Pre-split still helps capture mid-take restarts as separate segments
            if len(speech_segments) <= 1:
                print("No split points found — transcribing full audio.", file=sys.stderr)
                transcribe_result = transcribe_audio_mlx(audio_path, model_name, language)
                if transcribe_result["status"] != "success":
                    return transcribe_result
                all_segments = transcribe_result["segments"]
            else:
                print(
                    f"Pre-splitting into {len(speech_segments)} speech segment(s) "
                    f"at silence boundaries.",
                    file=sys.stderr
                )
                seg_temp_dir = tempfile.mkdtemp(prefix="transcribe_segs_")
                try:
                    all_segments = []
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
                        print(f"  [{i+1}/{len(speech_segments)}] Transcribing...", file=sys.stderr)
                        result = transcribe_audio_mlx(seg_wav, model_name, language, seg_start=seg_start)
                        if result["status"] == "success":
                            all_segments.extend(result["segments"])
                        else:
                            print(f"[warn] MLX failed on segment {i}, skipping: {result.get('error', '')}",
                                  file=sys.stderr)
                        try:
                            os.unlink(seg_wav)
                        except OSError:
                            pass
                finally:
                    shutil.rmtree(seg_temp_dir, ignore_errors=True)

                if not all_segments:
                    return {
                        "status": "error",
                        "error": "All speech segments failed to transcribe. Check mlx-whisper installation."
                    }
                all_segments.sort(key=lambda s: s["start"])

            transcribe_result = {
                "status": "success",
                "language": language,
                "segments": all_segments,
            }

        else:
            # ── faster-whisper engine path ──
            loaded_model, err = _load_model(model_name)
            if err:
                return err

            if len(speech_segments) <= 1:
                print("No split points found — transcribing full audio.", file=sys.stderr)
                transcribe_result = transcribe_audio(audio_path, model_name, language, model=loaded_model)
                if transcribe_result["status"] != "success":
                    return transcribe_result
                all_segments = transcribe_result["segments"]

            else:
                actual_workers = min(workers, len(speech_segments))
                parallel_label = f" across {actual_workers} workers" if actual_workers > 1 else ""
                print(
                    f"Pre-splitting into {len(speech_segments)} speech segment(s) "
                    f"at silence boundaries{parallel_label}.",
                    file=sys.stderr
                )

                seg_temp_dir = tempfile.mkdtemp(prefix="transcribe_segs_")
                try:
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

                    all_segments = []
                    if actual_workers <= 1:
                        for item in batch_items:
                            print(f"  [{item['index']+1}/{len(speech_segments)}] Transcribing...", file=sys.stderr)
                            try:
                                segments_gen, _info = loaded_model.transcribe(
                                    item["wav_path"],
                                    language=language or None,
                                    condition_on_previous_text=False,
                                )
                                for seg in segments_gen:
                                    all_segments.append({
                                        "start": round(seg.start + item["seg_start"], 3),
                                        "end":   round(seg.end   + item["seg_start"], 3),
                                        "text":  seg.text.strip(),
                                    })
                            except Exception as e:
                                print(f"[warn] Whisper failed on segment {item['index']}, skipping: {e}",
                                      file=sys.stderr)
                    else:
                        del loaded_model
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

                        worker_results.sort(key=lambda r: r["index"])
                        for r in worker_results:
                            if r["status"] == "success":
                                all_segments.extend(r["segments"])
                            else:
                                print(f"[warn] Segment {r['index']} failed: {r.get('error', '')}",
                                      file=sys.stderr)

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
        "engine": engine,
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
    model_name = "medium"
    language = "en"
    workers = 2
    engine = "auto"  # auto-detect: mlx on Apple Silicon, faster-whisper otherwise

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
        elif args[i] == '--engine' and i + 1 < len(args):
            engine = args[i + 1]
            i += 2
        else:
            i += 1

    # Auto-detect engine: try mlx on Apple Silicon, fall back to faster-whisper
    if engine == "auto":
        import platform
        if platform.machine() == "arm64" and platform.system() == "Darwin":
            try:
                import mlx_whisper  # noqa: F401
                engine = "mlx"
                print("Auto-detected Apple Silicon — using MLX engine.", file=sys.stderr)
            except ImportError:
                engine = "faster-whisper"
                print("mlx-whisper not installed — falling back to faster-whisper engine.", file=sys.stderr)
        else:
            engine = "faster-whisper"
            print("Not Apple Silicon — using faster-whisper engine.", file=sys.stderr)

    result = transcribe_video(video_path, output_json, model_name, language, workers=workers, engine=engine)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['status'] == 'success' else 1)


if __name__ == '__main__':
    main()
