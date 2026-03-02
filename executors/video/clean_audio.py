#!/usr/bin/env python3
"""
Clean Audio Executor
====================
Processes talking-head audio to fix room noise, reverb, uneven levels, and peaks.
Uses a multi-stage pipeline with ML-based denoising (RNNoise via ffmpeg arnndn).

Usage:
    python3 executors/video/clean_audio.py <input> <output> [options]
    python3 executors/video/clean_audio.py --help

Arguments:
    input       Path to audio or video file (mp4, mov, wav, mp3, etc.)
    output      Path for the processed output file

Options:
    --preset PRESET            Filter preset: light, voice (default), heavy
    --target-lufs LUFS         Loudness target in LUFS (default: -14, YouTube standard)
    --denoise-backend BACKEND  Force denoise backend: auto (default), arnndn, afftdn
    --no-denoise               Skip noise/reverb reduction
    --no-compress              Skip compression + limiting
    --no-normalize             Skip loudness normalization
    --no-eq                    Skip de-esser
    --analyze                  Measure audio characteristics and recommend preset (no processing)
    --dry-run                  Print the pipeline plan without executing

Presets:
    light   — highpass + gentle compressor + two-pass loudnorm only
    voice   — full chain: highpass, arnndn, deesser, compressor, limiter, loudnorm (default)
    heavy   — arnndn (blended), stronger deesser, firmer compressor, limiter, loudnorm

Pipeline Stages:
    1. Extract audio to 48kHz mono WAV (temp)
    2. Apply filters: highpass → arnndn (RNNoise) → deesser → compressor → gate → limiter
    3. Loudnorm pass 1: measure loudness stats
    4. Loudnorm pass 2: apply linear normalization with measured values
    5. Mux processed audio back with original video stream (if present)

Output JSON:
    {
      "status": "success",
      "input_file": "/abs/path/input.mp4",
      "output_file": "/abs/path/output.mp4",
      "preset": "voice",
      "target_lufs": -14,
      "denoise_backend": "arnndn",
      "filters_applied": ["highpass", "arnndn", "deesser", "acompressor", "alimiter", "loudnorm_2pass"],
      "loudness_measured": { "input_i": -22.3, "output_i": -14.0 },
      "file_size_bytes": 12345678,
      "file_size_mb": 11.77,
      "ffmpeg_commands": ["..."]
    }

Exits:
    0 — success
    1 — failure
    2 — input error

Dependencies:
    ffmpeg 6.0+ (brew install ffmpeg) — must include arnndn filter
    Internet connection on first run (downloads ~3MB RNNoise model, cached)
"""

from __future__ import annotations

import sys
import json
import re
import time
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# RNNoise model management
# ---------------------------------------------------------------------------

ARNNDN_MODEL_URL = "https://raw.githubusercontent.com/richardpl/arnndn-models/master/cb.rnnn"
ARNNDN_CACHE_DIR = Path.home() / ".cache" / "clean_audio"
ARNNDN_MODEL_PATH = ARNNDN_CACHE_DIR / "cb.rnnn"


def ensure_arnndn_model() -> str | None:
    """Download the RNNoise model if not cached. Returns path or None on failure."""
    if ARNNDN_MODEL_PATH.exists():
        return str(ARNNDN_MODEL_PATH)

    try:
        ARNNDN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Downloading RNNoise model to {ARNNDN_MODEL_PATH} ...", file=sys.stderr)
        urllib.request.urlretrieve(ARNNDN_MODEL_URL, str(ARNNDN_MODEL_PATH))
        print("  Done.", file=sys.stderr)
        return str(ARNNDN_MODEL_PATH)
    except Exception as e:
        print(f"  Failed to download RNNoise model: {e}", file=sys.stderr)
        return None


def check_arnndn_available() -> bool:
    """Check if ffmpeg has the arnndn filter compiled in."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True, text=True, timeout=10
        )
        return "arnndn" in result.stdout
    except Exception:
        return False


def detect_denoise_backend() -> str:
    """Auto-detect the best available denoise backend."""
    if check_arnndn_available() and ensure_arnndn_model() is not None:
        return "arnndn"
    return "afftdn"


# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------

PRESETS = {
    "light": {
        "highpass_freq": 80,
        "denoise": False,
        "arnndn_mix": 1.0,
        "deesser": False,
        "deesser_intensity": 0.0,
        "deesser_max": 0.5,
        "deesser_freq": 0.5,
        "compressor_threshold": -20,
        "compressor_ratio": 1.5,
        "compressor_attack": 30,
        "compressor_release": 300,
        "compressor_knee": 6,
        "gate": False,
        "gate_threshold": 0.006,
        "gate_ratio": 2,
        "gate_attack": 5,
        "gate_release": 100,
        "limiter": False,
        "limiter_limit": 0.95,
        "limiter_attack": 5,
        "limiter_release": 50,
    },
    "voice": {
        "highpass_freq": 80,
        "denoise": True,
        "arnndn_mix": 1.0,
        "deesser": True,
        "deesser_intensity": 0.4,
        "deesser_max": 0.5,
        "deesser_freq": 0.5,
        "compressor_threshold": -20,
        "compressor_ratio": 2,
        "compressor_attack": 20,
        "compressor_release": 200,
        "compressor_knee": 4,
        "gate": True,
        "gate_threshold": 0.006,
        "gate_ratio": 2,
        "gate_attack": 5,
        "gate_release": 100,
        "limiter": True,
        "limiter_limit": 0.95,
        "limiter_attack": 5,
        "limiter_release": 50,
    },
    "heavy": {
        "highpass_freq": 100,
        "denoise": True,
        "arnndn_mix": 1.0,
        "deesser": True,
        "deesser_intensity": 0.6,
        "deesser_max": 0.6,
        "deesser_freq": 0.5,
        "compressor_threshold": -18,
        "compressor_ratio": 2.5,
        "compressor_attack": 15,
        "compressor_release": 150,
        "compressor_knee": 3,
        "gate": True,
        "gate_threshold": 0.01,
        "gate_ratio": 3,
        "gate_attack": 5,
        "gate_release": 80,
        "limiter": True,
        "limiter_limit": 0.9,
        "limiter_attack": 5,
        "limiter_release": 50,
    },
}


# ---------------------------------------------------------------------------
# Audio probing
# ---------------------------------------------------------------------------

def has_video_stream(filepath: str) -> bool:
    """Check if the file contains a video stream."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-select_streams", "v:0", filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return len(info.get("streams", [])) > 0
    except Exception:
        pass
    return False


def get_audio_info(filepath: str) -> dict | None:
    """Get audio stream info (sample rate, channels, codec, duration)."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", "-select_streams", "a:0", filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            streams = info.get("streams", [])
            fmt = info.get("format", {})
            if streams:
                s = streams[0]
                return {
                    "sample_rate": int(s.get("sample_rate", 48000)),
                    "channels": int(s.get("channels", 1)),
                    "codec": s.get("codec_name", "unknown"),
                    "duration": float(fmt.get("duration", s.get("duration", 0))),
                }
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def extract_audio_wav(input_file: str, wav_path: str) -> dict:
    """Extract audio to 48kHz mono 16-bit WAV."""
    cmd = [
        "ffmpeg", "-i", input_file,
        "-vn", "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "1",
        "-y", wav_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        return {"status": "error", "error": "Failed to extract audio", "stderr": result.stderr}
    return {"status": "success", "output": wav_path}


def build_processing_chain(preset_name: str, denoise_backend: str,
                           no_denoise: bool, no_compress: bool, no_eq: bool) -> tuple:
    """
    Build the ffmpeg audio filter chain for the processing pass (everything except loudnorm).

    Returns:
        (filter_string, filter_names, model_path_or_none)
    """
    preset = PRESETS[preset_name]
    filters = []
    names = []
    model_path = None

    # 1. High-pass filter
    filters.append(f"highpass=f={preset['highpass_freq']}")
    names.append("highpass")

    # 2. Denoise
    if preset["denoise"] and not no_denoise:
        if denoise_backend == "arnndn":
            model_path = ensure_arnndn_model()
            if model_path:
                mix = preset["arnndn_mix"]
                filters.append(f"arnndn=m={model_path}:mix={mix}")
                names.append("arnndn")
            else:
                # Fallback to afftdn
                filters.append("afftdn=nf=-30")
                names.append("afftdn")
        else:
            # afftdn backend (gentler than old -25)
            filters.append("afftdn=nf=-30")
            names.append("afftdn")

    # 3. De-esser
    if preset["deesser"] and not no_eq:
        i = preset["deesser_intensity"]
        m = preset["deesser_max"]
        f = preset["deesser_freq"]
        filters.append(f"deesser=i={i}:m={m}:f={f}:s=o")
        names.append("deesser")

    # 4. Compressor
    if not no_compress:
        t = preset["compressor_threshold"]
        r = preset["compressor_ratio"]
        a = preset["compressor_attack"]
        rel = preset["compressor_release"]
        k = preset["compressor_knee"]
        filters.append(
            f"acompressor=threshold={t}dB:ratio={r}:attack={a}:release={rel}:knee={k}"
        )
        names.append("acompressor")

    # 4b. Noise gate (mutes residual noise between phrases)
    if preset.get("gate") and not no_compress:
        gt = preset["gate_threshold"]
        gr = preset["gate_ratio"]
        ga = preset["gate_attack"]
        grel = preset["gate_release"]
        filters.append(f"agate=threshold={gt}:ratio={gr}:attack={ga}:release={grel}")
        names.append("agate")

    # 5. Limiter
    if preset["limiter"] and not no_compress:
        lim = preset["limiter_limit"]
        la = preset["limiter_attack"]
        lr = preset["limiter_release"]
        filters.append(f"alimiter=limit={lim}:attack={la}:release={lr}")
        names.append("alimiter")

    filter_chain = ",".join(filters)
    return filter_chain, names, model_path


def process_audio(input_wav: str, output_wav: str, filter_chain: str) -> dict:
    """Apply the filter chain to a WAV file (everything except loudnorm)."""
    cmd = [
        "ffmpeg", "-i", input_wav,
        "-af", filter_chain,
        "-y", output_wav
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        return {"status": "error", "error": "Audio processing failed", "stderr": result.stderr}
    return {"status": "success", "output": output_wav}


def measure_loudness(input_wav: str, target_lufs: float) -> dict | None:
    """
    Loudnorm pass 1: measure loudness stats.

    Returns dict with measured_I, measured_LRA, measured_TP, measured_thresh, or None on failure.
    """
    cmd = [
        "ffmpeg", "-i", input_wav,
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        return None

    # Parse the JSON block from stderr
    # loudnorm prints JSON embedded in other ffmpeg output
    stderr = result.stderr
    json_match = re.search(r'\{[^{}]*"input_i"[^{}]*\}', stderr, re.DOTALL)
    if not json_match:
        return None

    try:
        stats = json.loads(json_match.group())
        return {
            "measured_I": float(stats.get("input_i", 0)),
            "measured_LRA": float(stats.get("input_lra", 0)),
            "measured_TP": float(stats.get("input_tp", 0)),
            "measured_thresh": float(stats.get("input_thresh", -70)),
        }
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def normalize_loudness(input_wav: str, output_wav: str, target_lufs: float,
                       measured: dict) -> dict:
    """Loudnorm pass 2: apply linear normalization using measured values."""
    af = (
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
        f":measured_I={measured['measured_I']}"
        f":measured_LRA={measured['measured_LRA']}"
        f":measured_TP={measured['measured_TP']}"
        f":measured_thresh={measured['measured_thresh']}"
        f":linear=true"
    )
    cmd = [
        "ffmpeg", "-i", input_wav,
        "-af", af,
        "-y", output_wav
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        return {"status": "error", "error": "Loudnorm pass 2 failed", "stderr": result.stderr}
    return {"status": "success", "output": output_wav}


def single_pass_loudnorm(input_wav: str, output_wav: str, target_lufs: float) -> dict:
    """Fallback: single-pass loudnorm if two-pass measurement fails."""
    cmd = [
        "ffmpeg", "-i", input_wav,
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        "-y", output_wav
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        return {"status": "error", "error": "Loudnorm failed", "stderr": result.stderr}
    return {"status": "success", "output": output_wav}


def mux_audio_video(original_video: str, processed_wav: str, output_file: str) -> dict:
    """Combine processed audio with original video stream."""
    cmd = [
        "ffmpeg",
        "-i", original_video,
        "-i", processed_wav,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-y", output_file
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        return {"status": "error", "error": "Mux failed", "stderr": result.stderr}
    return {"status": "success", "output": output_file}


def copy_audio_only(processed_wav: str, output_file: str, output_ext: str) -> dict:
    """For audio-only inputs, encode the processed WAV to the output format."""
    cmd = ["ffmpeg", "-i", processed_wav, "-y", output_file]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        return {"status": "error", "error": "Audio encoding failed", "stderr": result.stderr}
    return {"status": "success", "output": output_file}


# ---------------------------------------------------------------------------
# Analyze mode
# ---------------------------------------------------------------------------

def analyze_audio(input_file: str, target_lufs: float) -> dict:
    """Measure audio loudness and recommend a preset."""
    info = get_audio_info(input_file)
    if not info:
        return {"status": "error", "error": "Could not read audio info from file"}

    # Measure loudness
    cmd = [
        "ffmpeg", "-i", input_file,
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    loudness = {}
    if result.returncode == 0:
        json_match = re.search(r'\{[^{}]*"input_i"[^{}]*\}', result.stderr, re.DOTALL)
        if json_match:
            try:
                stats = json.loads(json_match.group())
                loudness = {
                    "integrated_loudness": float(stats.get("input_i", 0)),
                    "true_peak": float(stats.get("input_tp", 0)),
                    "loudness_range": float(stats.get("input_lra", 0)),
                    "threshold": float(stats.get("input_thresh", -70)),
                }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

    # Recommend preset
    il = loudness.get("integrated_loudness", -24)
    lra = loudness.get("loudness_range", 10)

    if -16 <= il <= -12 and lra < 8:
        recommended = "light"
    elif il < -28 or lra > 15:
        recommended = "heavy"
    else:
        recommended = "voice"

    return {
        "status": "success",
        "analyze": True,
        "input_file": str(Path(input_file).resolve()),
        "audio_info": info,
        "loudness": loudness,
        "recommended_preset": recommended,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def clean_audio(input_file: str, output_file: str, preset: str = "voice",
                target_lufs: float = -14, denoise_backend: str = "auto",
                no_denoise: bool = False, no_compress: bool = False,
                no_normalize: bool = False, no_eq: bool = False,
                dry_run: bool = False, analyze: bool = False) -> dict:
    """Orchestrate the full multi-stage audio cleanup pipeline."""
    t_start = time.time()
    input_path = Path(input_file)
    output_path = Path(output_file)

    # Validate input
    if not input_path.exists():
        return {"status": "error", "error": f"Input file not found: {input_file}"}

    if preset not in PRESETS:
        return {
            "status": "error",
            "error": f"Unknown preset: {preset}. Use: {', '.join(PRESETS.keys())}"
        }

    if shutil.which("ffmpeg") is None:
        return {"status": "error", "error": "ffmpeg not found. Install with: brew install ffmpeg"}

    # Analyze mode
    if analyze:
        return analyze_audio(input_file, target_lufs)

    # Resolve denoise backend
    if denoise_backend == "auto":
        if no_denoise or not PRESETS[preset]["denoise"]:
            denoise_backend = "none"
        else:
            denoise_backend = detect_denoise_backend()

    # Build filter chain
    filter_chain, filter_names, model_path = build_processing_chain(
        preset, denoise_backend, no_denoise, no_compress, no_eq
    )

    if not filter_chain:
        return {"status": "error", "error": "All filters disabled — nothing to do"}

    # Check video
    input_has_video = has_video_stream(str(input_path))

    # Collect all commands for dry-run reporting
    commands = []

    if dry_run:
        stages = []
        stages.append(f"1. Extract audio to 48kHz mono WAV")
        stages.append(f"2. Process: {' → '.join(filter_names)}")
        if not no_normalize:
            stages.append(f"3. Loudnorm pass 1: measure loudness")
            stages.append(f"4. Loudnorm pass 2: linear normalize to {target_lufs} LUFS")
        if input_has_video:
            stages.append(f"5. Mux: combine processed audio with original video (-c:v copy)")
        return {
            "status": "success",
            "dry_run": True,
            "input_file": str(input_path.resolve()),
            "output_file": str(output_path.resolve()),
            "preset": preset,
            "target_lufs": target_lufs,
            "denoise_backend": denoise_backend,
            "filters_applied": filter_names,
            "pipeline_stages": stages,
        }

    # Create temp directory for intermediate files
    tmp_dir = tempfile.mkdtemp(prefix="clean_audio_")
    tmp_path = Path(tmp_dir)

    try:
        print(f"Cleaning audio: {input_path.name}", file=sys.stderr)
        print(f"  Preset: {preset}", file=sys.stderr)
        print(f"  Denoise backend: {denoise_backend}", file=sys.stderr)
        print(f"  Filters: {' → '.join(filter_names)}", file=sys.stderr)
        print(f"  Target loudness: {target_lufs} LUFS", file=sys.stderr)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Stage 1: Extract audio to WAV
        raw_wav = str(tmp_path / "raw.wav")
        print("\n  [1/5] Extracting audio ...", file=sys.stderr)
        r = extract_audio_wav(str(input_path.resolve()), raw_wav)
        if r["status"] != "success":
            return r
        commands.append(f"extract → {raw_wav}")

        # Stage 2: Apply filters
        processed_wav = str(tmp_path / "processed.wav")
        print(f"  [2/5] Processing: {' → '.join(filter_names)} ...", file=sys.stderr)
        r = process_audio(raw_wav, processed_wav, filter_chain)
        if r["status"] != "success":
            return r
        commands.append(f"process ({filter_chain})")

        # Stage 3 & 4: Two-pass loudnorm
        loudness_data = {}
        if not no_normalize:
            normalized_wav = str(tmp_path / "normalized.wav")
            print(f"  [3/5] Measuring loudness ...", file=sys.stderr)
            measured = measure_loudness(processed_wav, target_lufs)

            if measured:
                loudness_data = {
                    "input_i": measured["measured_I"],
                    "input_tp": measured["measured_TP"],
                    "input_lra": measured["measured_LRA"],
                }
                print(f"         Measured: {measured['measured_I']:.1f} LUFS, "
                      f"TP={measured['measured_TP']:.1f} dBTP, "
                      f"LRA={measured['measured_LRA']:.1f} LU", file=sys.stderr)

                print(f"  [4/5] Normalizing to {target_lufs} LUFS (linear) ...", file=sys.stderr)
                r = normalize_loudness(processed_wav, normalized_wav, target_lufs, measured)
                if r["status"] != "success":
                    # Fallback to single-pass
                    print("         Two-pass failed, falling back to single-pass ...", file=sys.stderr)
                    r = single_pass_loudnorm(processed_wav, normalized_wav, target_lufs)
                    if r["status"] != "success":
                        return r
                    filter_names.append("loudnorm_1pass")
                else:
                    filter_names.append("loudnorm_2pass")
                    loudness_data["output_i"] = target_lufs
            else:
                # Fallback to single-pass
                print("         Measurement failed, falling back to single-pass loudnorm ...", file=sys.stderr)
                r = single_pass_loudnorm(processed_wav, normalized_wav, target_lufs)
                if r["status"] != "success":
                    return r
                filter_names.append("loudnorm_1pass")
        else:
            # Skip normalization — use processed wav directly
            normalized_wav = processed_wav

        # Stage 5: Mux or copy
        if input_has_video:
            print(f"  [5/5] Muxing with original video ...", file=sys.stderr)
            r = mux_audio_video(
                str(input_path.resolve()),
                normalized_wav,
                str(output_path.resolve())
            )
            if r["status"] != "success":
                return r
        else:
            print(f"  [5/5] Encoding output ...", file=sys.stderr)
            r = copy_audio_only(
                normalized_wav,
                str(output_path.resolve()),
                output_path.suffix
            )
            if r["status"] != "success":
                return r

        # Get output file size
        file_size = output_path.stat().st_size if output_path.exists() else 0

        elapsed = round(time.time() - t_start, 1)
        print(f"\nDone. Output: {output_path}", file=sys.stderr)
        print(f"  Size: {file_size / (1024 * 1024):.1f} MB", file=sys.stderr)
        print(f"  Elapsed: {elapsed}s", file=sys.stderr)

        return {
            "status": "success",
            "input_file": str(input_path.resolve()),
            "output_file": str(output_path.resolve()),
            "preset": preset,
            "target_lufs": target_lufs,
            "denoise_backend": denoise_backend,
            "filters_applied": filter_names,
            "loudness_measured": loudness_data,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "ffmpeg_commands": commands,
            "elapsed_seconds": elapsed,
        }

    finally:
        # Clean up temp files
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    # Parse named options
    preset = "voice"
    target_lufs = -14.0
    denoise_backend = "auto"
    no_denoise = False
    no_compress = False
    no_normalize = False
    no_eq = False
    dry_run = False
    analyze = False
    positional = []

    i = 0
    while i < len(args):
        if args[i] == "--preset" and i + 1 < len(args):
            preset = args[i + 1]
            i += 2
        elif args[i] == "--target-lufs" and i + 1 < len(args):
            try:
                target_lufs = float(args[i + 1])
            except ValueError:
                print(json.dumps({
                    "status": "error",
                    "error": f"Invalid LUFS value: {args[i + 1]}"
                }, indent=2))
                sys.exit(2)
            i += 2
        elif args[i] == "--denoise-backend" and i + 1 < len(args):
            denoise_backend = args[i + 1]
            i += 2
        elif args[i] == "--no-denoise":
            no_denoise = True
            i += 1
        elif args[i] == "--no-compress":
            no_compress = True
            i += 1
        elif args[i] == "--no-normalize":
            no_normalize = True
            i += 1
        elif args[i] == "--no-eq":
            no_eq = True
            i += 1
        elif args[i] == "--dry-run":
            dry_run = True
            i += 1
        elif args[i] == "--analyze":
            analyze = True
            i += 1
        else:
            positional.append(args[i])
            i += 1

    if analyze:
        if not positional:
            print(json.dumps({
                "status": "error",
                "error": "Usage: clean_audio.py --analyze <input>"
            }, indent=2))
            sys.exit(1)
        result = analyze_audio(positional[0], target_lufs)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["status"] == "success" else 1)

    if len(positional) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Usage: clean_audio.py <input> <output> [--preset voice] [--target-lufs -14]"
        }, indent=2))
        sys.exit(1)

    result = clean_audio(
        positional[0], positional[1],
        preset=preset, target_lufs=target_lufs,
        denoise_backend=denoise_backend,
        no_denoise=no_denoise, no_compress=no_compress,
        no_normalize=no_normalize, no_eq=no_eq,
        dry_run=dry_run
    )
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
