#!/usr/bin/env python3
"""
Audio-Based Cut Verification Executor
=======================================
Renders audio from keep_segments, re-transcribes the output with Whisper,
then detects and optionally auto-fixes "double" and "missing" errors.

Detects three categories of issues:
1. **Boundary doubles** — words repeated at segment join points (most common)
2. **Global doubles** — repeated phrases anywhere in output (n-gram analysis)
3. **Audio issues** — silence gaps, amplitude spikes, mid-word cutoffs (warnings only)

Usage:
    python3 executors/video/verify_cut.py <transcript.json> <cut_spec.json>
    python3 executors/video/verify_cut.py <transcript.json> <cut_spec.json> --fix
    python3 executors/video/verify_cut.py <transcript.json> <cut_spec.json> --dry-run
    python3 executors/video/verify_cut.py <transcript.json> <cut_spec.json> --script <script.txt> --fix
    python3 executors/video/verify_cut.py --help

Arguments:
    transcript.json   Source transcript (from transcribe.py)
    cut_spec.json     Cut specification with keep_segments
    --script PATH     Script file for missing detection (without it, only doubles are checked)
    --fix             Auto-fix detected errors (writes modified cut_spec.json)
    --dry-run         Show proposed fixes without applying (detection + proposed changes)
    --temp-dir DIR    Directory for temp audio/transcript files (default: system temp)
    --model MODEL     Whisper model for re-transcription (default: small)

Exits:
    0  — no errors found (clean)
    1  — errors found and fixed (--fix) or errors found (no --fix)
    2  — input error (missing file, bad JSON, etc.)

Output (stdout, JSON):
    {
      "status": "clean|fixed|errors",
      "boundary_doubles": [...],
      "doubles": [...],
      "missing": [...],
      "audio_warnings": [...],
      "fixes_applied": {"boundary_doubles": N, "doubles": N, "missing_restored": N},
      "elapsed_seconds": N
    }

Max iterations: 2 (initial check + one re-check after fixes). If the re-check
still finds issues, they are reported but NOT auto-fixed — flagged for human review.
"""
from __future__ import annotations

import sys
import json
import os
import re
import time
import struct
import string
import subprocess
import tempfile
from pathlib import Path
from collections import defaultdict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NGRAM_MIN = 3         # minimum n-gram size for global double detection
NGRAM_MAX = 7         # check up to this size for confirmation
FUZZY_THRESHOLD = 0.60  # Jaccard similarity for missing detection
CONSECUTIVE_MATCH = 3   # consecutive script words found in order = match
CONSECUTIVE_MATCH_SHORT = 2  # for short sentences (< 30 chars)
WHISPER_MODEL = "small"
MAX_ITERATIONS = 2
MAX_DOUBLE_DISTANCE = 45.0  # seconds — phrases repeating further apart are likely intentional
BOUNDARY_WINDOW_WORDS = 5   # words to compare at each side of a boundary
SILENCE_THRESHOLD_DB = -50  # dB below peak for silence detection (strict — only near-total silence)
SILENCE_MIN_DURATION = 0.8  # seconds of continuous silence to flag as pause (skip natural gaps)
SPIKE_THRESHOLD_DB = 25     # dB jump in single frame = possible artifact

# Padding constants — MUST match apply_cuts.py so verification tests the same audio
START_PADDING_SECONDS = 0.1
END_PADDING_SECONDS = 0.1
# After fixing a boundary double, the resulting gap must be >= this to prevent
# padding from re-introducing the double (> 2*padding + bridge threshold)
MIN_SAFE_GAP_AFTER_FIX = 0.30

# Common phrases that naturally repeat in speech — skip these as doubles
COMMON_PHRASES = {
    # 5-word phrases
    ("in", "other", "words", "the", "real"),
    ("at", "the", "same", "time", "the"),
    ("at", "the", "end", "of", "the"),
    ("this", "is", "going", "to", "be"),
    ("what", "this", "means", "is", "that"),
    ("if", "you", "want", "to", "know"),
    ("one", "of", "the", "most", "important"),
    ("for", "the", "rest", "of", "the"),
    ("you", "are", "going", "to", "be"),
    ("it", "is", "going", "to", "be"),
    ("the", "end", "of", "the", "day"),
    # 3-word common transitions
    ("and", "so", "the"),
    ("so", "the", "question"),
    ("but", "the", "thing"),
    ("and", "the", "thing"),
    ("so", "if", "you"),
    ("but", "if", "you"),
    ("and", "if", "you"),
    ("this", "is", "the"),
    ("that", "is", "the"),
    ("what", "is", "the"),
    ("one", "of", "the"),
    ("a", "lot", "of"),
    ("the", "fact", "that"),
    ("in", "terms", "of"),
    ("at", "the", "end"),
    ("end", "of", "the"),
    ("the", "end", "of"),
    # 4-word common transitions
    ("and", "so", "the", "question"),
    ("but", "the", "thing", "is"),
    ("and", "the", "thing", "is"),
    ("so", "if", "you", "want"),
    ("one", "of", "the", "most"),
    ("at", "the", "end", "of"),
    ("the", "end", "of", "the"),
    ("a", "lot", "of", "people"),
    ("the", "fact", "that", "the"),
}

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "and", "but", "or",
    "nor", "not", "so", "yet", "both", "either", "neither", "each",
    "every", "all", "any", "few", "more", "most", "other", "some", "such",
    "no", "only", "own", "same", "than", "too", "very", "just", "about",
    "also", "then", "that", "this", "these", "those", "it", "its",
    "i", "me", "my", "we", "us", "our", "you", "your", "he", "him",
    "his", "she", "her", "they", "them", "their", "what", "which", "who",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_timestamp(ts) -> float:
    if isinstance(ts, (int, float)):
        return float(ts)
    ts = str(ts).strip()
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(ts)


def seconds_to_hms(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:06.3f}"


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into words."""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation.replace("'", "")))
    return text.split()


def load_transcript(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("segments", [])
    return data


def load_cut_spec(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Step 1: Render audio preview
# ---------------------------------------------------------------------------

def _compute_padded_segments(keep_segs: list[dict]) -> list[dict]:
    """Apply ±padding and clamping — mirrors apply_cuts.py's logic exactly.

    Returns a list of dicts with 'start', 'end', 'raw_start', 'raw_end', 'index'.
    """
    padded = []
    for i, seg in enumerate(keep_segs):
        raw_start = parse_timestamp(seg["start"])
        raw_end = parse_timestamp(seg["end"])
        padded.append({
            "index": i,
            "raw_start": raw_start,
            "raw_end": raw_end,
            "start": max(0.0, raw_start - START_PADDING_SECONDS),
            "end": raw_end + END_PADDING_SECONDS,
        })
    # Clamp overlapping padded segments (same as apply_cuts.py lines 411-415)
    for i in range(len(padded) - 1):
        if padded[i]["end"] > padded[i + 1]["start"]:
            boundary = padded[i]["raw_end"]
            padded[i]["end"] = boundary
            padded[i + 1]["start"] = boundary
    return padded


def render_audio_preview(cut_spec: dict, temp_dir: str) -> str:
    """Render audio-only from keep_segments WITH padding + clamping.

    Mirrors apply_cuts.py's ±0.1s padding and overlap clamping so that
    the verification audio matches what the user actually hears.
    Returns path to the rendered WAV file.
    """
    source = cut_spec["source"]
    if not os.path.isabs(source):
        source = os.path.join(os.getcwd(), source)

    keep_segs = cut_spec["keep_segments"]
    padded = _compute_padded_segments(keep_segs)

    seg_dir = os.path.join(temp_dir, "verify_segs")
    os.makedirs(seg_dir, exist_ok=True)

    seg_paths = []
    for p in padded:
        start = p["start"]
        end = p["end"]
        duration = end - start
        if duration <= 0:
            continue
        seg_path = os.path.join(seg_dir, f"seg_{p['index']:04d}.wav")
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-t", str(duration),
            "-i", source,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            seg_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"[verify_cut] ffmpeg segment {p['index']} failed: {result.stderr[:200]}",
                  file=sys.stderr)
            continue
        seg_paths.append(seg_path)

    if not seg_paths:
        return ""

    concat_list = os.path.join(temp_dir, "verify_concat.txt")
    with open(concat_list, "w") as f:
        for path in seg_paths:
            f.write(f"file '{path}'\n")

    output_wav = os.path.join(temp_dir, "verify_audio.wav")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        output_wav
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"[verify_cut] ffmpeg concat failed: {result.stderr[:200]}",
              file=sys.stderr)
        return ""

    return output_wav


# ---------------------------------------------------------------------------
# Step 2: Transcribe output audio
# ---------------------------------------------------------------------------

def transcribe_preview(audio_path: str, model_name: str, temp_dir: str) -> list[dict]:
    """Transcribe rendered audio with faster-whisper. Returns segment list."""
    executor_dir = os.path.dirname(os.path.abspath(__file__))
    if executor_dir not in sys.path:
        sys.path.insert(0, executor_dir)

    from transcribe import _load_model, transcribe_audio

    model, err = _load_model(model_name)
    if err:
        print(f"[verify_cut] Model load failed: {err}", file=sys.stderr)
        return []

    result = transcribe_audio(audio_path, model_name, "en", model=model)
    if result.get("status") != "success":
        print(f"[verify_cut] Transcription failed: {result.get('error', 'unknown')}",
              file=sys.stderr)
        return []

    segments = result["segments"]

    out_path = os.path.join(temp_dir, "verify_transcript.json")
    with open(out_path, "w") as f:
        json.dump({"segments": segments}, f, indent=2)

    return segments


# ---------------------------------------------------------------------------
# Step 3: Build duration map (output time → source time)
# ---------------------------------------------------------------------------

def build_duration_map(keep_segments: list[dict]) -> list[dict]:
    """Build cumulative output→source timestamp mapping using padded timestamps.

    Uses the same padding + clamping as apply_cuts.py and render_audio_preview
    so that output timestamps match what the user actually hears.
    """
    padded = _compute_padded_segments(keep_segments)
    mapping = []
    cum = 0.0
    for p in padded:
        dur = p["end"] - p["start"]
        if dur <= 0:
            continue
        mapping.append({
            "index": p["index"],
            "output_start": cum,
            "output_end": cum + dur,
            "source_start": p["start"],   # padded source start
            "source_end": p["end"],        # padded source end
            "raw_start": p["raw_start"],   # original cut_spec start
            "raw_end": p["raw_end"],       # original cut_spec end
        })
        cum += dur
    return mapping


def output_to_source(output_ts: float, duration_map: list[dict]) -> tuple[float, int]:
    """Map an output timestamp to (source_timestamp, keep_segment_index)."""
    for m in duration_map:
        if m["output_start"] <= output_ts <= m["output_end"]:
            offset = output_ts - m["output_start"]
            return m["source_start"] + offset, m["index"]
    if duration_map:
        m = duration_map[-1]
        return m["source_end"], m["index"]
    return 0.0, 0


# ---------------------------------------------------------------------------
# Step 4a: Detect boundary doubles (segment join points)
# ---------------------------------------------------------------------------

def detect_boundary_doubles(
    output_segments: list[dict],
    duration_map: list[dict],
    keep_segments: list[dict],
) -> list[dict]:
    """Detect repeated words at segment boundaries.

    For each consecutive pair of keep_segments, extract the last few words
    before the boundary and first few words after. If any words match at
    the join point, it's a boundary double.
    """
    if len(duration_map) < 2:
        return []

    # Build word list with output timestamps
    words_with_ts = []
    for seg in output_segments:
        tokens = tokenize(seg.get("text", ""))
        seg_start = seg.get("start", 0.0)
        seg_end = seg.get("end", seg_start)
        seg_dur = max(seg_end - seg_start, 0.001)
        for j, w in enumerate(tokens):
            word_ts = seg_start + (j / max(len(tokens), 1)) * seg_dur
            words_with_ts.append((w, word_ts))

    if not words_with_ts:
        return []

    boundary_doubles = []

    for mi in range(len(duration_map) - 1):
        m_cur = duration_map[mi]
        m_next = duration_map[mi + 1]
        boundary_ts = m_cur["output_end"]  # where segment N ends in output time

        # Get words near the boundary: last N words before, first N words after
        pre_words = []
        post_words = []
        for w, ts in words_with_ts:
            if m_cur["output_start"] <= ts <= boundary_ts:
                pre_words.append((w, ts))
            elif boundary_ts < ts <= m_next["output_end"]:
                post_words.append((w, ts))

        if not pre_words or not post_words:
            continue

        # Take last BOUNDARY_WINDOW_WORDS from pre, first BOUNDARY_WINDOW_WORDS from post
        pre_tail = pre_words[-BOUNDARY_WINDOW_WORDS:]
        post_head = post_words[:BOUNDARY_WINDOW_WORDS]

        pre_tail_words = [w for w, _ in pre_tail]
        post_head_words = [w for w, _ in post_head]

        # Find the longest matching suffix of pre_tail that equals prefix of post_head
        # e.g., pre ends with ["the", "risk"] and post starts with ["the", "risk", "is"]
        # → match length 2: "the risk"
        max_match = min(len(pre_tail_words), len(post_head_words))
        match_len = 0
        for k in range(1, max_match + 1):
            if pre_tail_words[-k:] == post_head_words[:k]:
                match_len = k

        if match_len == 0:
            # Also check single-word overlap: last word of pre == first word of post
            # This catches "A ... A" type doubles where it's a restart
            if pre_tail_words[-1] == post_head_words[0]:
                match_len = 1

        if match_len == 0:
            continue

        matched_phrase = " ".join(post_head_words[:match_len])
        pre_ts = pre_tail[-match_len][1]
        post_ts = post_head[0][1]

        # Calculate how far into the post segment the doubled phrase extends
        # in output time, then convert to approximate source-time duration
        phrase_output_duration = 0.0
        if match_len > 0 and len(post_head) >= match_len:
            phrase_output_duration = post_head[min(match_len - 1, len(post_head) - 1)][1] - post_head[0][1]
            if phrase_output_duration <= 0:
                phrase_output_duration = match_len * 0.15  # fallback estimate

        boundary_doubles.append({
            "phrase": matched_phrase,
            "match_length": match_len,
            "boundary_between_segments": [m_cur["index"], m_next["index"]],
            "pre_segment_index": m_cur["index"],
            "post_segment_index": m_next["index"],
            "output_ts_pre": round(pre_ts, 2),
            "output_ts_post": round(post_ts, 2),
            "source_ts_pre": round(m_cur["source_end"] - (boundary_ts - pre_ts), 2),
            "source_ts_post": round(m_next["source_start"] + (post_ts - boundary_ts), 2),
            "trim_recommendation": {
                "action": "advance_start",
                "segment_index": m_next["index"],
                "trim_seconds": round(phrase_output_duration + 0.15, 3),
            },
        })

    return boundary_doubles


# ---------------------------------------------------------------------------
# Step 4b: Detect global doubles via n-gram analysis
# ---------------------------------------------------------------------------

def detect_doubles(output_segments: list[dict], duration_map: list[dict]) -> list[dict]:
    """Find repeated phrases in the output transcript (global n-gram analysis)."""
    words_with_ts = []
    for seg in output_segments:
        tokens = tokenize(seg.get("text", ""))
        seg_start = seg.get("start", 0.0)
        seg_end = seg.get("end", seg_start)
        seg_dur = max(seg_end - seg_start, 0.001)
        for j, w in enumerate(tokens):
            word_ts = seg_start + (j / max(len(tokens), 1)) * seg_dur
            words_with_ts.append((w, word_ts))

    if len(words_with_ts) < NGRAM_MIN:
        return []

    words = [w for w, _ in words_with_ts]
    timestamps = [t for _, t in words_with_ts]

    # Build n-gram index
    ngram_positions = defaultdict(list)
    for i in range(len(words) - NGRAM_MIN + 1):
        ngram = tuple(words[i:i + NGRAM_MIN])
        ngram_positions[ngram].append(i)

    doubles = []
    seen_ranges = set()

    for ngram, positions in ngram_positions.items():
        if len(positions) < 2:
            continue
        if ngram in COMMON_PHRASES:
            continue

        # For 3-4 word n-grams, require confirmation by a larger n-gram
        confirmed = False
        if len(ngram) >= 5:
            confirmed = True  # 5+ word repeats are strong signal on their own
        else:
            # Check if a larger n-gram also repeats
            for n in range(len(ngram) + 1, min(NGRAM_MAX + 1, len(words))):
                for pos in positions:
                    if pos + n > len(words):
                        continue
                    bigger = tuple(words[pos:pos + n])
                    for other_pos in positions:
                        if other_pos == pos:
                            continue
                        if other_pos + n > len(words):
                            continue
                        if tuple(words[other_pos:other_pos + n]) == bigger:
                            confirmed = True
                            break
                    if confirmed:
                        break
                if confirmed:
                    break

        if not confirmed:
            continue

        pos1, pos2 = positions[0], positions[1]

        if abs(pos2 - pos1) < NGRAM_MIN:
            continue

        ts1 = timestamps[pos1]
        ts2 = timestamps[pos2]
        if abs(ts2 - ts1) > MAX_DOUBLE_DISTANCE:
            continue

        range_key = (pos1 // 20, pos2 // 20)
        if range_key in seen_ranges:
            continue
        seen_ranges.add(range_key)

        # Extend both directions while words match
        ext_start1, ext_start2 = pos1, pos2
        ext_end1 = pos1 + NGRAM_MIN
        ext_end2 = pos2 + NGRAM_MIN
        while ext_end1 < len(words) and ext_end2 < len(words) and words[ext_end1] == words[ext_end2]:
            ext_end1 += 1
            ext_end2 += 1

        phrase = " ".join(words[ext_start1:ext_end1])
        ts1_start = timestamps[ext_start1]
        ts1_end = timestamps[min(ext_end1, len(timestamps) - 1)]
        ts2_start = timestamps[ext_start2]
        ts2_end = timestamps[min(ext_end2, len(timestamps) - 1)]

        src_ts1, seg_idx1 = output_to_source(ts1_start, duration_map)
        src_ts2, seg_idx2 = output_to_source(ts2_start, duration_map)

        doubles.append({
            "phrase": phrase,
            "confirmed_by_larger_ngram": confirmed,
            "occurrence_1": {
                "output_ts_start": round(ts1_start, 2),
                "output_ts_end": round(ts1_end, 2),
                "source_ts": round(src_ts1, 2),
                "keep_segment_index": seg_idx1,
            },
            "occurrence_2": {
                "output_ts_start": round(ts2_start, 2),
                "output_ts_end": round(ts2_end, 2),
                "source_ts": round(src_ts2, 2),
                "keep_segment_index": seg_idx2,
            },
        })

    return doubles


# ---------------------------------------------------------------------------
# Step 4c: Detect audio issues (silence, spikes, cutoffs)
# ---------------------------------------------------------------------------

def _read_wav_samples(wav_path: str) -> tuple[list[int], int]:
    """Read 16-bit mono PCM WAV samples. Returns (samples, sample_rate)."""
    with open(wav_path, "rb") as f:
        # Read RIFF header
        riff = f.read(4)
        if riff != b"RIFF":
            return [], 16000
        f.read(4)  # file size
        wave = f.read(4)
        if wave != b"WAVE":
            return [], 16000

        sample_rate = 16000
        data_bytes = b""

        while True:
            chunk_id = f.read(4)
            if len(chunk_id) < 4:
                break
            chunk_size = struct.unpack("<I", f.read(4))[0]
            if chunk_id == b"fmt ":
                fmt_data = f.read(chunk_size)
                sample_rate = struct.unpack("<I", fmt_data[4:8])[0]
            elif chunk_id == b"data":
                data_bytes = f.read(chunk_size)
                break
            else:
                f.read(chunk_size)

    if not data_bytes:
        return [], sample_rate

    n_samples = len(data_bytes) // 2
    samples = list(struct.unpack(f"<{n_samples}h", data_bytes[:n_samples * 2]))
    return samples, sample_rate


def _rms_frames(samples: list[int], sample_rate: int, frame_ms: int = 50) -> list[float]:
    """Compute RMS energy per frame. Returns list of RMS values (linear)."""
    frame_size = sample_rate * frame_ms // 1000
    frames = []
    for i in range(0, len(samples) - frame_size + 1, frame_size):
        frame = samples[i:i + frame_size]
        rms = (sum(s * s for s in frame) / len(frame)) ** 0.5
        frames.append(rms)
    return frames


def detect_audio_issues(
    audio_path: str,
    duration_map: list[dict],
    output_segments: list[dict],
) -> list[dict]:
    """Detect audio quality issues: silence gaps, amplitude spikes, cutoffs."""
    warnings = []

    try:
        samples, sample_rate = _read_wav_samples(audio_path)
    except Exception as e:
        print(f"[verify_cut] Audio analysis failed: {e}", file=sys.stderr)
        return warnings

    if not samples:
        return warnings

    frame_ms = 50
    rms_frames = _rms_frames(samples, sample_rate, frame_ms)
    if not rms_frames:
        return warnings

    peak_rms = max(rms_frames) if rms_frames else 1.0
    if peak_rms == 0:
        return warnings

    import math

    # --- Silence gap detection ---
    silence_threshold = peak_rms * (10 ** (SILENCE_THRESHOLD_DB / 20))
    silence_start = None
    for i, rms in enumerate(rms_frames):
        ts = i * frame_ms / 1000.0
        if rms < silence_threshold:
            if silence_start is None:
                silence_start = ts
        else:
            if silence_start is not None:
                duration = ts - silence_start
                if duration >= SILENCE_MIN_DURATION:
                    # Check if this silence is at a segment boundary
                    at_boundary = False
                    mid_ts = silence_start + duration / 2
                    for m in duration_map:
                        if abs(mid_ts - m["output_end"]) < 0.5:
                            at_boundary = True
                            break
                    src_ts, seg_idx = output_to_source(silence_start, duration_map)
                    warnings.append({
                        "type": "silence_gap",
                        "output_ts_start": round(silence_start, 2),
                        "output_ts_end": round(ts, 2),
                        "duration_seconds": round(duration, 2),
                        "at_segment_boundary": at_boundary,
                        "source_ts": round(src_ts, 2),
                        "segment_index": seg_idx,
                    })
                silence_start = None

    # --- Amplitude spike detection ---
    for i in range(1, len(rms_frames)):
        prev_rms = max(rms_frames[i - 1], 1.0)
        curr_rms = max(rms_frames[i], 1.0)
        try:
            db_jump = 20 * math.log10(curr_rms / prev_rms)
        except (ValueError, ZeroDivisionError):
            continue
        if abs(db_jump) >= SPIKE_THRESHOLD_DB:
            ts = i * frame_ms / 1000.0
            src_ts, seg_idx = output_to_source(ts, duration_map)
            warnings.append({
                "type": "amplitude_spike",
                "output_ts": round(ts, 2),
                "db_jump": round(db_jump, 1),
                "source_ts": round(src_ts, 2),
                "segment_index": seg_idx,
            })

    # --- Mid-word cutoff detection ---
    # Check Whisper segments at boundaries: short words with low-ish confidence
    for m in duration_map:
        boundary_ts = m["output_end"]
        # Find the last Whisper segment before this boundary
        for seg in output_segments:
            seg_end = seg.get("end", 0.0)
            if abs(seg_end - boundary_ts) < 0.3:
                text = seg.get("text", "").strip()
                words = text.split()
                if words:
                    last_word = words[-1].strip(string.punctuation)
                    # Flag very short words at boundaries (possible cutoff)
                    if len(last_word) <= 2 and last_word.isalpha():
                        src_ts, seg_idx = output_to_source(seg_end, duration_map)
                        warnings.append({
                            "type": "possible_cutoff",
                            "word": last_word,
                            "output_ts": round(seg_end, 2),
                            "source_ts": round(src_ts, 2),
                            "segment_index": seg_idx,
                        })
                break

    return warnings


# ---------------------------------------------------------------------------
# Step 5: Detect missing content (requires script)
# ---------------------------------------------------------------------------

def parse_script(script_path: str) -> list[str]:
    """Parse a script file into spoken sentences (strip non-spoken content)."""
    with open(script_path) as f:
        text = f.read()

    lines = text.split("\n")
    spoken_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith("#"):
            continue
        if line.startswith("[Source:") or line.startswith("[source:"):
            continue
        if line.startswith("**Format**") or line.startswith("**Based on**"):
            continue
        if re.match(r"^\*\*[^*]+\*\*\s*:", line):
            continue
        if re.match(r"^https?://", line):
            continue
        if not line or line in ("---", "***"):
            continue
        spoken_lines.append(line)

    full_text = " ".join(spoken_lines)
    sentences = re.split(r'(?<=[.?!])\s+', full_text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def detect_missing(script_path: str, output_segments: list[dict]) -> list[dict]:
    """Check each script sentence against the output transcript."""
    sentences = parse_script(script_path)
    if not sentences:
        return []

    output_words_full = []
    for seg in output_segments:
        output_words_full.extend(tokenize(seg.get("text", "")))

    output_text_lower = " ".join(output_words_full)

    missing = []
    for i, sentence in enumerate(sentences):
        sent_words = tokenize(sentence)
        if not sent_words:
            continue

        sent_content = [w for w in sent_words if w not in STOPWORDS]
        if not sent_content:
            continue

        # Determine consecutive match threshold based on sentence length
        consec_threshold = CONSECUTIVE_MATCH_SHORT if len(sentence) < 30 else CONSECUTIVE_MATCH

        # Check 1: consecutive word match
        found_consecutive = False
        for start_idx in range(len(sent_content) - consec_threshold + 1):
            pattern = " ".join(sent_content[start_idx:start_idx + consec_threshold])
            if pattern in output_text_lower:
                found_consecutive = True
                break

        if found_consecutive:
            continue

        # Check 2: windowed recall score
        sent_set = set(sent_content)
        best_window_score = 0.0
        window_size = len(sent_content) * 2
        for w_start in range(0, max(1, len(output_words_full) - window_size), window_size // 2):
            window = output_words_full[w_start:w_start + window_size]
            window_content = set(w for w in window if w not in STOPWORDS)
            if not window_content:
                continue
            w_intersection = sent_set & window_content
            recall = len(w_intersection) / len(sent_set) if sent_set else 0
            best_window_score = max(best_window_score, recall)

        if best_window_score >= FUZZY_THRESHOLD:
            continue

        missing.append({
            "sentence": sentence[:120],
            "script_index": i,
            "best_match_score": round(best_window_score, 3),
        })

    return missing


# ---------------------------------------------------------------------------
# Step 6a: Auto-fix boundary doubles
# ---------------------------------------------------------------------------

def fix_boundary_doubles(cut_spec: dict, boundary_doubles: list[dict]) -> int:
    """Fix boundary doubles by advancing the START of the NEXT segment.

    The doubled word exists because the presenter restarted — the restart is at
    the BEGINNING of segment N+1, not at the END of segment N. Trimming N's end
    destroys real content; advancing N+1's start skips past the restart.

    The advance amount accounts for END_PADDING_SECONDS to prevent padding
    bleed-back from re-introducing the double.
    """
    keep_segs = cut_spec["keep_segments"]
    fixes = 0

    # Process in reverse order to avoid index shifting
    for bd in sorted(boundary_doubles, key=lambda x: x["post_segment_index"], reverse=True):
        post_idx = bd["post_segment_index"]
        if post_idx >= len(keep_segs):
            continue

        post_seg = keep_segs[post_idx]
        post_start = parse_timestamp(post_seg["start"])
        post_end = parse_timestamp(post_seg["end"])

        # Advance start past the doubled phrase + padding buffer + safety margin
        trim_secs = bd["trim_recommendation"]["trim_seconds"]
        advance = trim_secs + END_PADDING_SECONDS + 0.05
        new_start = post_start + advance

        if new_start >= post_end - 0.2:
            # Would consume almost entire segment — remove it
            keep_segs.pop(post_idx)
            fixes += 1
        else:
            post_seg["start"] = seconds_to_hms(new_start)
            post_seg["note"] = post_seg.get("note", "") + \
                f" [start-adjusted: boundary double '{bd['phrase']}' removed]"
            fixes += 1

    return fixes


# ---------------------------------------------------------------------------
# Step 6b: Auto-fix global doubles
# ---------------------------------------------------------------------------

def fix_doubles(cut_spec: dict, doubles: list[dict],
                source_transcript: list[dict]) -> int:
    """Fix global doubles by trimming the earlier occurrence from keep_segments.

    Uses timestamp proximity to find the right trim point.
    """
    keep_segs = cut_spec["keep_segments"]
    fixes = 0

    for double in doubles:
        occ1 = double["occurrence_1"]
        seg_idx = occ1["keep_segment_index"]

        if seg_idx >= len(keep_segs):
            continue

        seg = keep_segs[seg_idx]
        seg_start = parse_timestamp(seg["start"])
        seg_end = parse_timestamp(seg["end"])
        src_ts = occ1["source_ts"]

        best_trim_point = None
        best_distance = float("inf")

        for t_seg in source_transcript:
            t_start = t_seg.get("start", 0)
            if not (seg_start < t_start <= seg_end):
                continue
            dist = abs(t_start - src_ts)
            if dist < best_distance and dist < 3.0:
                best_distance = dist
                best_trim_point = t_start - (END_PADDING_SECONDS + 0.05)

        if best_trim_point is None:
            best_trim_point = src_ts - (END_PADDING_SECONDS + 0.05)

        if seg_start < best_trim_point < seg_end:
            remaining = best_trim_point - seg_start
            total = seg_end - seg_start

            if remaining / total < 0.15:
                keep_segs.pop(seg_idx)
                fixes += 1
            else:
                seg["end"] = seconds_to_hms(best_trim_point)
                seg["note"] = seg.get("note", "") + " [trimmed: double removed]"
                fixes += 1

    return fixes


# ---------------------------------------------------------------------------
# Step 7: Auto-fix missing content
# ---------------------------------------------------------------------------

def fix_missing(cut_spec: dict, missing_items: list[dict],
                source_transcript: list[dict]) -> int:
    """Fix missing content by extending adjacent keep segments or inserting new ones."""
    keep_segs = cut_spec["keep_segments"]
    fixes = 0

    for item in missing_items:
        sentence = item["sentence"]
        sent_words = set(tokenize(sentence)) - STOPWORDS
        if not sent_words:
            continue

        best_match = None
        best_score = 0
        for t_seg in source_transcript:
            t_words = set(tokenize(t_seg.get("text", ""))) - STOPWORDS
            if not t_words:
                continue
            overlap = len(sent_words & t_words)
            recall = overlap / len(sent_words) if sent_words else 0
            if recall > best_score:
                best_score = recall
                best_match = t_seg

        if not best_match or best_score < 0.4:
            continue

        t_start = best_match.get("start", 0)
        t_end = best_match.get("end", 0)

        already_kept = False
        for seg in keep_segs:
            s = parse_timestamp(seg["start"])
            e = parse_timestamp(seg["end"])
            if s <= t_start and t_end <= e:
                already_kept = True
                break

        if already_kept:
            continue

        extended = False
        for seg in keep_segs:
            s = parse_timestamp(seg["start"])
            e = parse_timestamp(seg["end"])

            if 0 < t_start - e < 3.0:
                new_end = t_end + 0.2
                seg_i = keep_segs.index(seg)
                if seg_i + 1 < len(keep_segs):
                    next_start = parse_timestamp(keep_segs[seg_i + 1]["start"])
                    new_end = min(new_end, next_start - 0.1)
                seg["end"] = seconds_to_hms(new_end)
                seg["note"] = seg.get("note", "") + " [extended: missing restored]"
                extended = True
                fixes += 1
                break

            if 0 < s - t_end < 3.0:
                new_start = t_start - 0.1
                seg_i = keep_segs.index(seg)
                if seg_i > 0:
                    prev_end = parse_timestamp(keep_segs[seg_i - 1]["end"])
                    new_start = max(new_start, prev_end + 0.1)
                seg["start"] = seconds_to_hms(new_start)
                seg["note"] = seg.get("note", "") + " [extended: missing restored]"
                extended = True
                fixes += 1
                break

        if not extended:
            new_seg = {
                "start": seconds_to_hms(max(0, t_start - 0.1)),
                "end": seconds_to_hms(t_end + 0.2),
                "note": f"[inserted: missing content restored] {best_match.get('text', '')[:60]}",
            }
            new_s = parse_timestamp(new_seg["start"])
            new_e = parse_timestamp(new_seg["end"])
            overlap = False
            for seg in keep_segs:
                s = parse_timestamp(seg["start"])
                e = parse_timestamp(seg["end"])
                if new_s < e and new_e > s:
                    overlap = True
                    break
            if not overlap:
                keep_segs.append(new_seg)
                keep_segs.sort(key=lambda x: parse_timestamp(x["start"]))
                fixes += 1

    return fixes


# ---------------------------------------------------------------------------
# Pre-render: internal retake detection using source transcript
# ---------------------------------------------------------------------------

def detect_internal_retakes(source_segments: list[dict],
                            keep_segments: list[dict]) -> list[dict]:
    """Scan keep_segments for internal retakes using source transcript data.

    For each keep_segment, finds all source transcript segments within its range
    and checks for repeated starting phrases (false starts). Also checks padding
    zones for false start bleed.

    Returns list of warnings (not auto-fixed — for human review).
    """
    warnings = []

    def _words(text: str) -> list[str]:
        return re.sub(r"[^\w\s]", "", text.lower()).split()

    for ki, kseg in enumerate(keep_segments):
        ks = parse_timestamp(kseg["start"])
        ke = parse_timestamp(kseg["end"])

        # Find source transcript segments within this keep range
        inner = []
        for ss in source_segments:
            seg_start = ss["start"] if isinstance(ss["start"], (int, float)) else parse_timestamp(str(ss["start"]))
            seg_end = ss["end"] if isinstance(ss["end"], (int, float)) else parse_timestamp(str(ss["end"]))
            # Segment overlaps with keep range
            if seg_end > ks and seg_start < ke:
                inner.append({
                    "start": seg_start,
                    "end": seg_end,
                    "text": ss.get("text", "").strip(),
                    "words": _words(ss.get("text", "")),
                })

        if len(inner) < 2:
            continue

        # Check for repeated starting words between consecutive inner segments
        for j in range(len(inner) - 1):
            w_cur = inner[j]["words"]
            for k in range(j + 1, min(j + 4, len(inner))):
                w_next = inner[k]["words"]
                if not w_cur or not w_next:
                    continue
                # Check if first 1-3 words match (single-word false starts are common)
                for n in range(1, min(4, len(w_cur) + 1, len(w_next) + 1)):
                    if w_cur[:n] == w_next[:n]:
                        # Skip common single stopwords
                        if n == 1 and w_cur[0] in STOPWORDS:
                            # Only flag if both segments start with the SAME phrase
                            # and the gap suggests a retake (not continuous speech)
                            gap = inner[k]["start"] - inner[j]["end"]
                            if gap < 0.3:
                                continue
                        phrase = " ".join(w_cur[:n])
                        warnings.append({
                            "type": "internal_retake",
                            "keep_segment_index": ki,
                            "phrase": phrase,
                            "first_occurrence": {
                                "start": inner[j]["start"],
                                "text": inner[j]["text"][:60],
                            },
                            "second_occurrence": {
                                "start": inner[k]["start"],
                                "text": inner[k]["text"][:60],
                            },
                            "suggestion": f"Split keep_segment {ki} between {seconds_to_hms(inner[j]['end'])} and {seconds_to_hms(inner[k]['start'])}"
                        })
                        break  # Found match at this word count, don't check longer

        # Check padding zones for false start bleed
        padded_start = max(0, ks - START_PADDING_SECONDS)
        padded_end = ke + END_PADDING_SECONDS

        # Check start padding zone
        for ss in source_segments:
            seg_start = ss["start"] if isinstance(ss["start"], (int, float)) else parse_timestamp(str(ss["start"]))
            seg_end = ss["end"] if isinstance(ss["end"], (int, float)) else parse_timestamp(str(ss["end"]))
            # Segment ends in the start padding zone (before raw start, after padded start)
            if seg_end > padded_start and seg_end <= ks and seg_start < ks:
                s_words = _words(ss.get("text", ""))
                if inner and inner[0]["words"]:
                    # Check if this segment shares starting words with the first inner segment
                    for n in range(1, min(3, len(s_words) + 1, len(inner[0]["words"]) + 1)):
                        if s_words[:n] == inner[0]["words"][:n]:
                            phrase = " ".join(s_words[:n])
                            warnings.append({
                                "type": "start_padding_bleed",
                                "keep_segment_index": ki,
                                "phrase": phrase,
                                "bleed_segment": {
                                    "start": seg_start,
                                    "end": seg_end,
                                    "text": ss.get("text", "").strip()[:60],
                                },
                                "suggestion": f"Advance keep_segment {ki} start past {seconds_to_hms(seg_end + 0.15)}"
                            })
                            break

        # Check end padding zone
        if ki + 1 < len(keep_segments):
            next_start = parse_timestamp(keep_segments[ki + 1]["start"])
            gap = next_start - ke
            if gap > 0.3:  # Only check if there's a real gap (not contiguous)
                for ss in source_segments:
                    seg_start = ss["start"] if isinstance(ss["start"], (int, float)) else parse_timestamp(str(ss["start"]))
                    # Segment starts in the end padding zone
                    if seg_start >= ke and seg_start <= padded_end:
                        s_words = _words(ss.get("text", ""))
                        # Find first inner segment of NEXT keep segment
                        nks = next_start
                        for ns in source_segments:
                            ns_start = ns["start"] if isinstance(ns["start"], (int, float)) else parse_timestamp(str(ns["start"]))
                            if ns_start >= nks - 0.2:
                                n_words = _words(ns.get("text", ""))
                                if s_words and n_words:
                                    for n in range(1, min(3, len(s_words) + 1, len(n_words) + 1)):
                                        if s_words[:n] == n_words[:n]:
                                            phrase = " ".join(s_words[:n])
                                            warnings.append({
                                                "type": "end_padding_bleed",
                                                "keep_segment_index": ki,
                                                "phrase": phrase,
                                                "bleed_segment": {
                                                    "start": seg_start,
                                                    "text": ss.get("text", "").strip()[:60],
                                                },
                                                "suggestion": f"Trim keep_segment {ki} end to before {seconds_to_hms(seg_start - 0.15)}"
                                            })
                                            break
                                break  # Only check first segment of next keep range

    return warnings


# ---------------------------------------------------------------------------
# Main verification pipeline
# ---------------------------------------------------------------------------

def verify_cut(transcript_path: str, cut_spec_path: str,
               script_path: str | None = None,
               fix: bool = False,
               dry_run: bool = False,
               temp_dir: str | None = None,
               model_name: str = WHISPER_MODEL) -> dict:
    """Run the full verification pipeline."""
    t0 = time.time()

    if temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="verify_cut_")
    temp_dir = os.path.abspath(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    source_transcript = load_transcript(transcript_path)
    cut_spec = load_cut_spec(cut_spec_path)

    if not cut_spec.get("keep_segments"):
        return {"status": "error", "error": "No keep_segments in cut_spec"}

    # Pre-render check: scan for internal retakes and padding bleed using source transcript
    print("[verify_cut] Pre-render: scanning for internal retakes and padding bleed...",
          file=sys.stderr)
    pre_render_warnings = detect_internal_retakes(
        source_transcript if isinstance(source_transcript, list) else source_transcript.get("segments", []),
        cut_spec["keep_segments"]
    )
    if pre_render_warnings:
        print(f"[verify_cut] Found {len(pre_render_warnings)} pre-render warnings",
              file=sys.stderr)
        for w in pre_render_warnings:
            print(f"  [{w['type']}] seg {w['keep_segment_index']}: "
                  f"'{w['phrase']}' — {w['suggestion']}", file=sys.stderr)

    result = {
        "status": "clean",
        "boundary_doubles": [],
        "doubles": [],
        "missing": [],
        "audio_warnings": [],
        "pre_render_warnings": pre_render_warnings,
        "fixes_applied": {"boundary_doubles": 0, "doubles": 0, "missing_restored": 0},
        "iterations": 0,
    }

    for iteration in range(MAX_ITERATIONS):
        result["iterations"] = iteration + 1

        # Step 1: Render audio preview
        print(f"[verify_cut] Iteration {iteration + 1}: Rendering audio preview...",
              file=sys.stderr)
        audio_path = render_audio_preview(cut_spec, temp_dir)
        if not audio_path:
            return {"status": "error", "error": "Failed to render audio preview"}

        # Step 2: Transcribe output
        print(f"[verify_cut] Transcribing output audio (model={model_name})...",
              file=sys.stderr)
        output_segments = transcribe_preview(audio_path, model_name, temp_dir)
        if not output_segments:
            return {"status": "error", "error": "Failed to transcribe output audio"}

        # Step 3: Build duration map
        duration_map = build_duration_map(cut_spec["keep_segments"])

        # Step 4a: Detect boundary doubles (highest priority)
        print("[verify_cut] Checking for boundary doubles...", file=sys.stderr)
        boundary_doubles = detect_boundary_doubles(
            output_segments, duration_map, cut_spec["keep_segments"])

        # Step 4b: Detect global doubles
        print("[verify_cut] Checking for global doubles...", file=sys.stderr)
        doubles = detect_doubles(output_segments, duration_map)

        # Step 4c: Detect audio issues (first iteration only)
        audio_warnings = []
        if iteration == 0:
            print("[verify_cut] Analyzing audio quality...", file=sys.stderr)
            audio_warnings = detect_audio_issues(audio_path, duration_map, output_segments)

        # Step 5: Detect missing (if script provided)
        missing = []
        if script_path:
            print("[verify_cut] Checking for missing content...", file=sys.stderr)
            missing = detect_missing(script_path, output_segments)

        has_errors = bool(boundary_doubles or doubles or missing)

        if not has_errors:
            if iteration == 0:
                result["status"] = "clean"
                result["audio_warnings"] = audio_warnings
            break

        result["boundary_doubles"] = boundary_doubles
        result["doubles"] = doubles
        result["missing"] = missing
        result["audio_warnings"] = audio_warnings
        result["status"] = "errors"

        if not fix and not dry_run:
            break

        if dry_run:
            # Report proposed fixes without applying
            result["status"] = "dry_run"
            result["proposed_fixes"] = {
                "boundary_doubles": [
                    {
                        "phrase": bd["phrase"],
                        "action": bd["trim_recommendation"]["action"],
                        "segment_index": bd["trim_recommendation"]["segment_index"],
                        "trim_seconds": bd["trim_recommendation"]["trim_seconds"],
                    }
                    for bd in boundary_doubles
                ],
                "doubles": [
                    {
                        "phrase": d["phrase"],
                        "segment_index": d["occurrence_1"]["keep_segment_index"],
                        "source_ts": d["occurrence_1"]["source_ts"],
                    }
                    for d in doubles
                ],
                "missing": [{"sentence": m["sentence"]} for m in missing],
            }
            break

        # Only auto-fix on first iteration
        if iteration == 0:
            print(f"[verify_cut] Fixing {len(boundary_doubles)} boundary doubles, "
                  f"{len(doubles)} global doubles, {len(missing)} missing...",
                  file=sys.stderr)

            # Fix boundary doubles first (most common)
            bd_fixes = fix_boundary_doubles(cut_spec, boundary_doubles)
            d_fixes = fix_doubles(cut_spec, doubles, source_transcript)
            m_fixes = fix_missing(cut_spec, missing, source_transcript)

            result["fixes_applied"]["boundary_doubles"] = bd_fixes
            result["fixes_applied"]["doubles"] = d_fixes
            result["fixes_applied"]["missing_restored"] = m_fixes

            total_fixes = bd_fixes + d_fixes + m_fixes
            if total_fixes > 0:
                result["status"] = "fixed"
                with open(cut_spec_path, "w") as f:
                    json.dump(cut_spec, f, indent=2)
                print(f"[verify_cut] Fixed {bd_fixes} boundary doubles, {d_fixes} global doubles, "
                      f"{m_fixes} missing. Re-verifying...", file=sys.stderr)
            else:
                print("[verify_cut] Issues detected but no auto-fixes applied.",
                      file=sys.stderr)
                break
        else:
            result["recheck_issues"] = {
                "boundary_doubles": len(boundary_doubles),
                "doubles": len(doubles),
                "missing": len(missing),
                "message": "Issues remain after fixes — flagged for human review"
            }
            print(f"[verify_cut] Re-check found {len(boundary_doubles)} boundary doubles, "
                  f"{len(doubles)} global doubles, {len(missing)} missing — "
                  f"flagged for human review.", file=sys.stderr)
            break

    result["elapsed_seconds"] = round(time.time() - t0, 1)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if "--help" in sys.argv or "-h" in sys.argv or len(sys.argv) < 3:
        print(__doc__)
        sys.exit(0)

    transcript_path = sys.argv[1]
    cut_spec_path = sys.argv[2]

    script_path = None
    fix = False
    dry_run = False
    temp_dir = None
    model_name = WHISPER_MODEL

    i = 3
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--script" and i + 1 < len(sys.argv):
            script_path = sys.argv[i + 1]
            i += 2
        elif arg == "--fix":
            fix = True
            i += 1
        elif arg == "--dry-run":
            dry_run = True
            i += 1
        elif arg == "--temp-dir" and i + 1 < len(sys.argv):
            temp_dir = sys.argv[i + 1]
            i += 2
        elif arg == "--model" and i + 1 < len(sys.argv):
            model_name = sys.argv[i + 1]
            i += 2
        else:
            print(json.dumps({"status": "error", "error": f"Unknown argument: {arg}"}))
            sys.exit(2)

    if not Path(transcript_path).exists():
        print(json.dumps({"status": "error", "error": f"Transcript not found: {transcript_path}"}))
        sys.exit(2)
    if not Path(cut_spec_path).exists():
        print(json.dumps({"status": "error", "error": f"Cut spec not found: {cut_spec_path}"}))
        sys.exit(2)
    if script_path and not Path(script_path).exists():
        print(json.dumps({"status": "error", "error": f"Script not found: {script_path}"}))
        sys.exit(2)

    result = verify_cut(transcript_path, cut_spec_path, script_path, fix, dry_run, temp_dir, model_name)

    print(json.dumps(result, indent=2))

    if result["status"] == "clean":
        sys.exit(0)
    elif result["status"] in ("fixed", "errors", "dry_run"):
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
