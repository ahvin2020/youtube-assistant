#!/usr/bin/env python3
"""Analyze face pose in a reference thumbnail and find the best-matching headshot.

Uses MediaPipe FaceLandmarker (Tasks API) to extract face landmarks, then
estimates yaw/pitch via PnP solve. Compares against all headshots in a directory
to find the closest pose match using Euclidean distance in pose space.

Usage:
    /opt/homebrew/bin/python3 executors/thumbnail/match_headshot.py \
        --reference competitor_thumbnail.jpg \
        --headshots-dir workspace/input/thumbnail/headshots/ \
        [--top-k 3]

Requires:
    - pip install mediapipe opencv-contrib-python numpy
    - Model file: executors/thumbnail/models/face_landmarker.task
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "models", "face_landmarker.task"
)


def check_dependencies():
    """Check that required packages are installed."""
    missing = []
    try:
        import mediapipe  # noqa: F401
    except ImportError:
        missing.append("mediapipe")
    try:
        import cv2  # noqa: F401
    except ImportError:
        missing.append("opencv-contrib-python")
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")
    if not os.path.isfile(MODEL_PATH):
        missing.append(f"model file ({MODEL_PATH})")
    return missing


def estimate_face_pose(image_path: str) -> dict | None:
    """Estimate face yaw and pitch using MediaPipe FaceLandmarker + PnP solve.

    Returns dict with yaw, pitch, roll (in degrees), or None if no face detected.
    """
    import cv2
    import numpy as np
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    # Create landmarker
    options = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
    )

    landmarker = vision.FaceLandmarker.create_from_options(options)

    # Load image
    mp_image = mp.Image.create_from_file(image_path)
    result = landmarker.detect(mp_image)
    landmarker.close()

    if not result.face_landmarks:
        return None

    landmarks = result.face_landmarks[0]
    h = mp_image.height
    w = mp_image.width

    # Key landmark indices for pose estimation:
    # 1 = nose tip, 33 = left eye outer, 263 = right eye outer,
    # 61 = left mouth corner, 291 = right mouth corner, 199 = chin
    nose = landmarks[1]
    left_eye = landmarks[33]
    right_eye = landmarks[263]
    left_mouth = landmarks[61]
    right_mouth = landmarks[291]
    chin = landmarks[199]

    # Convert normalized coords to pixel coords
    pts_2d = np.array([
        [nose.x * w, nose.y * h],
        [left_eye.x * w, left_eye.y * h],
        [right_eye.x * w, right_eye.y * h],
        [left_mouth.x * w, left_mouth.y * h],
        [right_mouth.x * w, right_mouth.y * h],
        [chin.x * w, chin.y * h],
    ], dtype=np.float64)

    # 3D model points (generic face model)
    pts_3d = np.array([
        [0.0, 0.0, 0.0],         # nose tip
        [-65.5, -5.0, -20.0],    # left eye outer
        [65.5, -5.0, -20.0],     # right eye outer
        [-40.0, 50.0, -10.0],    # left mouth corner
        [40.0, 50.0, -10.0],     # right mouth corner
        [0.0, 80.0, -30.0],      # chin
    ], dtype=np.float64)

    # Camera matrix (approximate)
    focal_length = w
    camera_matrix = np.array([
        [focal_length, 0, w / 2],
        [0, focal_length, h / 2],
        [0, 0, 1],
    ], dtype=np.float64)

    dist_coeffs = np.zeros((4, 1))

    success, rvec, tvec = cv2.solvePnP(
        pts_3d, pts_2d, camera_matrix, dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )

    if not success:
        return None

    # Convert rotation vector to rotation matrix, then extract Euler angles
    rmat, _ = cv2.Rodrigues(rvec)

    sy = math.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)
    singular = sy < 1e-6

    if not singular:
        pitch = math.atan2(-rmat[2, 0], sy)
        yaw = math.atan2(rmat[1, 0], rmat[0, 0])
        roll = math.atan2(rmat[2, 1], rmat[2, 2])
    else:
        pitch = math.atan2(-rmat[2, 0], sy)
        yaw = math.atan2(-rmat[1, 2], rmat[1, 1])
        roll = 0.0

    return {
        "yaw": round(math.degrees(yaw), 1),
        "pitch": round(math.degrees(pitch), 1),
        "roll": round(math.degrees(roll), 1),
    }


def euclidean_pose_distance(pose_a: dict, pose_b: dict) -> float:
    """Calculate Euclidean distance between two pose vectors (yaw, pitch)."""
    dy = pose_a["yaw"] - pose_b["yaw"]
    dp = pose_a["pitch"] - pose_b["pitch"]
    return math.sqrt(dy * dy + dp * dp)


def main():
    parser = argparse.ArgumentParser(
        description="Find the best-matching headshot for a reference thumbnail based on face pose."
    )
    parser.add_argument("--reference", required=True,
                        help="Path to the reference thumbnail image")
    parser.add_argument("--headshots-dir", required=True,
                        help="Directory containing headshot images")
    parser.add_argument("--top-k", type=int, default=3,
                        help="Number of top matches to return (default: 3)")
    args = parser.parse_args()

    start = time.time()

    # Check dependencies
    missing = check_dependencies()
    if missing:
        print(json.dumps({
            "status": "error",
            "error": f"Missing: {', '.join(missing)}. Install mediapipe + opencv-contrib-python, and ensure model file exists.",
        }))
        sys.exit(1)

    # Validate inputs
    if not os.path.isfile(args.reference):
        print(json.dumps({
            "status": "error",
            "error": f"Reference image not found: {args.reference}",
        }))
        sys.exit(1)

    if not os.path.isdir(args.headshots_dir):
        print(json.dumps({
            "status": "error",
            "error": f"Headshots directory not found: {args.headshots_dir}",
        }))
        sys.exit(1)

    # Analyze reference face
    ref_pose = estimate_face_pose(args.reference)
    if ref_pose is None:
        print(json.dumps({
            "status": "warning",
            "error": "No face detected in reference thumbnail. Cannot match pose.",
            "reference_pose": None,
            "matches": [],
        }))
        sys.exit(0)

    # Find all headshot images
    image_exts = {".jpg", ".jpeg", ".png", ".webp"}
    headshots = []
    for f in sorted(os.listdir(args.headshots_dir)):
        if os.path.splitext(f)[1].lower() in image_exts:
            headshots.append(os.path.join(args.headshots_dir, f))

    if not headshots:
        print(json.dumps({
            "status": "error",
            "error": f"No headshot images found in {args.headshots_dir}",
        }))
        sys.exit(1)

    # Analyze each headshot and compute distance
    matches = []
    for hs_path in headshots:
        hs_pose = estimate_face_pose(hs_path)
        if hs_pose is None:
            matches.append({
                "filename": os.path.basename(hs_path),
                "path": os.path.abspath(hs_path),
                "pose": None,
                "distance": float("inf"),
                "face_detected": False,
            })
            continue

        dist = euclidean_pose_distance(ref_pose, hs_pose)
        matches.append({
            "filename": os.path.basename(hs_path),
            "path": os.path.abspath(hs_path),
            "pose": hs_pose,
            "distance": round(dist, 2),
            "face_detected": True,
        })

    # Sort by distance (closest first)
    matches.sort(key=lambda m: m["distance"])

    elapsed = round(time.time() - start, 2)

    print(json.dumps({
        "status": "success",
        "reference": os.path.abspath(args.reference),
        "reference_pose": ref_pose,
        "headshots_analyzed": len(matches),
        "top_matches": matches[:args.top_k],
        "all_matches": matches,
        "elapsed_seconds": elapsed,
    }))


if __name__ == "__main__":
    main()
