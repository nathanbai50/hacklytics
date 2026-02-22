"""
core/pose_detector.py
---------------------
Headless pose landmark extraction module for the push-up form analysis pipeline.

Responsibilities:
  - Load the MediaPipe Pose model exactly once (inside __init__) so the
    expensive model-load cost is paid only at startup, not per-frame.
  - Accept a single RGB numpy frame (produced by core/video_handler.py) and
    run inference through MediaPipe's Pose solution.
  - Extract a curated 5-point skeleton (shoulder, elbow, wrist, hip, ankle)
    from the RIGHT side of the body and return them as a plain dict.
  - Return None for frames where no person is detected, so the caller can
    decide how to handle detection gaps (skip, interpolate, etc.).
  - Expose a close() method so the model's GPU/CPU resources are freed cleanly
    when the analysis session ends.

This module is intentionally display-free — no cv2.imshow, no drawing utils.
All it does is ingest pixels and emit structured numbers.

Dependencies:
    pip install mediapipe numpy
"""

from typing import Optional

import mediapipe as mp
import numpy as np


# ---------------------------------------------------------------------------
# Landmark index constants
# ---------------------------------------------------------------------------
# MediaPipe's 33-point full-body skeleton uses fixed integer indices.
# We alias the ones we care about here so the extraction logic below reads
# as plain English rather than magic numbers.
#
# Full reference:
#   https://developers.google.com/mediapipe/solutions/vision/pose_landmarker
#
# We default to the RIGHT side of the body because standard push-up analysis
# videos are typically filmed from the athlete's right (camera left), giving
# a clean lateral profile of the right limb chain.

_PoseLandmark = mp.solutions.pose.PoseLandmark  # short alias for readability

LANDMARK_INDICES: dict[str, int] = {
    "shoulder": _PoseLandmark.RIGHT_SHOULDER.value,   # 12
    "elbow":    _PoseLandmark.RIGHT_ELBOW.value,      # 14
    "wrist":    _PoseLandmark.RIGHT_WRIST.value,      # 16
    "hip":      _PoseLandmark.RIGHT_HIP.value,        # 24
    "ankle":    _PoseLandmark.RIGHT_ANKLE.value,      # 28
}


# ---------------------------------------------------------------------------
# PoseDetector class
# ---------------------------------------------------------------------------

class PoseDetector:
    """Wraps MediaPipe Pose for single-frame landmark extraction.

    Usage pattern (mirrors the video pipeline):

        detector = PoseDetector()
        try:
            for rgb_frame in extract_frames(video_path, target_fps=15):
                landmarks = detector.extract_landmarks(rgb_frame)
                if landmarks is not None:
                    process(landmarks)  # feed to DTW scorer, etc.
        finally:
            detector.close()

    Attributes:
        pose: The underlying `mediapipe.solutions.pose.Pose` inference object.
              Exposed as a public attribute so callers can access raw results
              if they ever need more than the 5 curated points.
    """

    def __init__(
        self,
        static_image_mode: bool = False,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        """Initialise and load the MediaPipe Pose model into memory.

        This constructor is deliberately lightweight on parameters — only the
        three settings that materially affect accuracy vs. speed are exposed.

        Args:
            static_image_mode:
                False  → treat input as a video stream; MediaPipe reuses the
                          previous frame's pose as a prior, which is faster and
                          more temporally stable (correct for us).
                True   → treat every frame as an independent image; higher
                          recall but ~3× slower (only useful for photo batches).

            model_complexity:
                0 → lite model  — fastest, least accurate (~25 ms/frame CPU)
                1 → full model  — good balance (default, ~40 ms/frame CPU)
                2 → heavy model — most accurate, ~80 ms/frame CPU

            min_detection_confidence:
                Threshold [0, 1] for the initial person-detection stage.
                0.5 is the MediaPipe default; lower it if you're missing
                detections on partially cropped athletes.

            min_tracking_confidence:
                Threshold [0, 1] for the landmark-tracking stage on subsequent
                frames.  Falls back to full detection when tracking drops below
                this value.
        """
        # Initialise the MediaPipe drawing/pose namespaces we'll need.
        self._mp_pose = mp.solutions.pose

        # Instantiate the Pose model.  Using it as a plain object (not a
        # context manager) gives us explicit control over its lifetime via
        # close(), which is important in a long-lived server process.
        self.pose = self._mp_pose.Pose(
            static_image_mode=static_image_mode,
            model_complexity=model_complexity,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        print(
            f"[PoseDetector] Model loaded — complexity={model_complexity}, "
            f"static_image_mode={static_image_mode}, "
            f"min_detection_confidence={min_detection_confidence}"
        )

    # ------------------------------------------------------------------
    # Primary method
    # ------------------------------------------------------------------

    def extract_landmarks(
        self, rgb_frame: np.ndarray
    ) -> Optional[dict[str, tuple[float, float]]]:
        """Run pose inference on one RGB frame and return curated landmarks.

        The MediaPipe Pose model returns (x, y, z, visibility) for all 33
        body landmarks.  We discard z (depth estimate) and visibility scores
        here; the DTW scoring module only needs 2-D screen coordinates for
        joint-angle and trajectory comparisons.

        Coordinate system:
            Both x and y are *normalised* to [0.0, 1.0] relative to the
            frame's width and height respectively.  (0, 0) is the top-left
            corner.  Pixel coordinates can be recovered with:
                px = x * frame_width
                py = y * frame_height

        Args:
            rgb_frame: uint8 numpy array of shape (H, W, 3) in RGB order.
                       Frames from core/video_handler.py are already in this
                       format after the BGR→RGB conversion.

        Returns:
            A dict with exactly 5 keys if a pose is detected:
                {
                    "shoulder": (x: float, y: float),
                    "elbow":    (x: float, y: float),
                    "wrist":    (x: float, y: float),
                    "hip":      (x: float, y: float),
                    "ankle":    (x: float, y: float),
                }
            None if MediaPipe finds no person in the frame.
        """
        # ---- Run inference --------------------------------------------
        # `process()` expects a non-writeable RGB array.  MediaPipe sets the
        # writeable flag itself internally, but being explicit here avoids a
        # silent copy on some NumPy versions.
        rgb_frame.flags.writeable = False
        results = self.pose.process(rgb_frame)
        rgb_frame.flags.writeable = True  # restore for any downstream use

        # ---- Guard: no detection -------------------------------------
        # `pose_landmarks` is None when the person-detector stage fires below
        # `min_detection_confidence`, or when the frame is completely empty.
        if results.pose_landmarks is None:
            return None

        # ---- Extract the 5 target landmarks --------------------------
        # `pose_landmarks.landmark` is a repeated protobuf field indexable
        # by integer.  We use our pre-built LANDMARK_INDICES dict to map
        # human-readable joint names to their MediaPipe integer positions.
        all_landmarks = results.pose_landmarks.landmark

        extracted: dict[str, tuple[float, float]] = {
            joint_name: (
                all_landmarks[index].x,  # normalised horizontal position
                all_landmarks[index].y,  # normalised vertical position
            )
            for joint_name, index in LANDMARK_INDICES.items()
        }

        return extracted

    # ------------------------------------------------------------------
    # Resource management
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release the MediaPipe Pose model and free its allocated resources.

        Call this when you have finished processing an entire video (or in a
        `finally` block wrapping the analysis pipeline).  Failing to call
        close() in a long-running server will gradually exhaust GPU memory
        if multiple analysis sessions are created.

        After close() is called this instance must not be used again; create
        a new PoseDetector for the next session.
        """
        self.pose.close()
        print("[PoseDetector] Pose model closed and resources released.")

    # ------------------------------------------------------------------
    # Context-manager support (bonus: allows `with PoseDetector() as d:`)
    # ------------------------------------------------------------------

    def __enter__(self) -> "PoseDetector":
        """Support usage as a context manager for automatic cleanup."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Ensure close() is called when exiting a `with` block."""
        self.close()
        # Return False (implicitly) so any exception propagates normally.


# ---------------------------------------------------------------------------
# Smoke test — run directly to validate against a real video file:
#   python -m core.pose_detector path/to/test.mp4
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # Import here (not at module level) to keep pose_detector free of a
    # hard dependency on video_handler when used standalone.
    from core.video_handler import extract_frames

    if len(sys.argv) < 2:
        print("Usage: python -m core.pose_detector <path_to_video>")
        sys.exit(1)

    video_path = sys.argv[1]
    detected = 0
    missed = 0

    # Using the context manager ensures close() is always called.
    with PoseDetector(model_complexity=1) as detector:
        for frame_idx, rgb_frame in enumerate(extract_frames(video_path, target_fps=15)):
            landmarks = detector.extract_landmarks(rgb_frame)

            if landmarks is not None:
                detected += 1
                if frame_idx < 3:
                    # Print the first few detections so we can sanity-check values.
                    print(f"  Frame {frame_idx:>4}: {landmarks}")
            else:
                missed += 1

    total = detected + missed
    pct = (detected / total * 100) if total > 0 else 0
    print(f"\nDetection rate: {detected}/{total} frames ({pct:.1f}%)")
    