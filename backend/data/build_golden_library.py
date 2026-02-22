"""
data/build_golden_library.py
-----------------------------
One-time script that processes each reference video in data/golden_library/
and extracts its elbow-angle time series, saving it as a .json file alongside
the video.

Run this ONCE whenever you add or replace a reference video:

    python data/build_golden_library.py

After it runs, data/golden_library/ will contain both the original videos
AND their corresponding .json angle files, e.g.:

    data/golden_library/
        standard_rep.mp4
        standard_rep.json   ← produced by this script
        deep_rep.mov
        deep_rep.json       ← produced by this script

The FastAPI server's load_golden_library() reads the .json files.
The DTW engine then compares user reps against these pre-extracted series.
"""

import json
import sys
from pathlib import Path

# Make sure the project root is on the path so our modules import correctly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.video_handler  import extract_frames
from core.pose_detector  import PoseDetector
from core.geometry       import get_elbow_angle

GOLDEN_LIBRARY_DIR = Path("data/golden_library")
VIDEO_EXTENSIONS   = {".mp4", ".mov", ".MP4", ".MOV"}


def extract_angles_from_video(video_path: Path, detector: PoseDetector) -> list[float]:
    """Run the standard frame→pose→angle pipeline on a single video.

    This is intentionally identical to what server.py does for user uploads
    so the reference and user angles are computed the same way.

    Args:
        video_path: Path to the reference video file.
        detector:   A single shared PoseDetector instance (model loaded once).

    Returns:
        List of elbow angles (one per detected frame at 15fps).
        May be empty if pose was never detected.
    """
    elbow_angles: list[float] = []
    frames_total    = 0
    frames_detected = 0

    for rgb_frame in extract_frames(str(video_path), target_fps=15):
        frames_total += 1
        landmarks = detector.extract_landmarks(rgb_frame)

        if landmarks is None:
            continue

        frames_detected += 1
        angle = get_elbow_angle(landmarks)

        if angle is not None:
            elbow_angles.append(round(angle, 2))

    print(
        f"    {frames_total} frames extracted | "
        f"{frames_detected} pose detected | "
        f"{len(elbow_angles)} elbow angles"
    )

    return elbow_angles


def build_library() -> None:
    """Process every reference video and write its angle series as JSON."""

    if not GOLDEN_LIBRARY_DIR.exists():
        print(f"[build] ERROR: {GOLDEN_LIBRARY_DIR} does not exist.")
        sys.exit(1)

    video_files = [
        f for f in sorted(GOLDEN_LIBRARY_DIR.iterdir())
        if f.suffix in VIDEO_EXTENSIONS
    ]

    if not video_files:
        print(
            f"[build] No video files found in {GOLDEN_LIBRARY_DIR}.\n"
            f"        Supported extensions: {', '.join(VIDEO_EXTENSIONS)}"
        )
        sys.exit(1)

    print(f"[build] Found {len(video_files)} reference video(s):\n")

    # Load the model once and reuse it across all reference videos.
    detector = PoseDetector(
        static_image_mode=False,
        model_complexity=1,
        min_detection_confidence=0.5,
    )

    success_count = 0
    skip_count    = 0

    try:
        for video_path in video_files:
            json_path = video_path.with_suffix(".json")

            print(f"  Processing: {video_path.name}")

            # Skip if JSON already exists and is non-empty — use --force flag
            # (sys.argv) to regenerate if the reference video was updated.
            if json_path.exists() and "--force" not in sys.argv:
                existing = json.loads(json_path.read_text())
                if existing:
                    print(f"    ↳ {json_path.name} already exists ({len(existing)} angles) — skipping.")
                    print(f"      Run with --force to regenerate.\n")
                    skip_count += 1
                    continue

            angles = extract_angles_from_video(video_path, detector)

            if not angles:
                print(
                    f"    ✗ No angles extracted — pose was never detected.\n"
                    f"      Check that the video shows a clear lateral view of the athlete.\n"
                )
                skip_count += 1
                continue

            if len(angles) < 5:
                print(
                    f"    ✗ Only {len(angles)} angles extracted — too few for reliable DTW.\n"
                    f"      Ensure the video contains at least one full rep.\n"
                )
                skip_count += 1
                continue

            # Write the angle series as a JSON array
            json_path.write_text(
                json.dumps(angles, indent=2),
                encoding="utf-8",
            )

            print(
                f"    ✓ Saved {json_path.name} "
                f"(min={min(angles):.1f}°  max={max(angles):.1f}°  "
                f"frames={len(angles)})\n"
            )
            success_count += 1

    finally:
        detector.close()

    print("─" * 50)
    print(f"[build] Complete: {success_count} built, {skip_count} skipped.")

    if success_count > 0:
        print(
            "[build] Restart uvicorn — the new JSON files will load automatically."
        )
    else:
        print(
            "[build] ⚠  No JSON files were produced.\n"
            "         Check that your reference videos have clear pose visibility."
        )


if __name__ == "__main__":
    build_library()
