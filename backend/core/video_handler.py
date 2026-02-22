"""
core/video_handler.py
---------------------
Handles all video I/O for the push-up form analysis pipeline.

Responsibilities:
  - Open a video file safely, raising clear errors on failure.
  - Downsample frames from the native FPS to a target FPS using modulo logic,
    keeping memory usage flat regardless of video length or resolution.
  - Convert every yielded frame from BGR (OpenCV native) to RGB (MediaPipe
    required) before handing it to the caller.
  - Guarantee `VideoCapture.release()` via try/finally to prevent fd/RAM leaks.

Dependencies:
    pip install opencv-python-headless numpy
"""

import os
from typing import Generator

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Public generator
# ---------------------------------------------------------------------------

def extract_frames(
    video_path: str,
    target_fps: int = 15,
) -> Generator[np.ndarray, None, None]:
    """Yield RGB frames from a video file at approximately `target_fps`.

    This is intentionally a *generator* rather than a function that returns a
    list.  Generators are lazy — they produce one frame at a time and discard
    it once the caller is done with it.  A 60-second 1080p video at 30 fps is
    ~8 GB of raw pixel data; returning all of that as a list would crash the
    server instantly.  With a generator the working memory stays flat at
    roughly one frame (~6 MB for 1080p RGB).

    Downsampling strategy
    ---------------------
    We calculate a ``frame_interval`` — how many source frames we must advance
    to hit the target cadence:

        frame_interval = round(native_fps / target_fps)

    We then yield frame N only when ``N % frame_interval == 0``.  This is an
    O(1) check per frame and requires no buffering.

    Edge cases handled:
      - ``target_fps >= native_fps``: ``frame_interval`` clamps to 1, so every
        frame is yielded (no upsampling is attempted).
      - ``native_fps`` reported as 0 by a corrupt or container-less file:
        we fall back to yielding every frame rather than dividing by zero.

    Args:
        video_path:  Absolute or relative path to an .mp4 or .mov video file.
        target_fps:  Desired output cadence in frames-per-second.  Defaults to
                     15, which is sufficient for pose estimation while keeping
                     the downstream ML workload light.

    Yields:
        np.ndarray of shape (H, W, 3) in RGB colour order, dtype uint8.

    Raises:
        FileNotFoundError: If ``video_path`` does not exist on disk.
        ValueError:        If OpenCV cannot open the file (corrupt, unsupported
                           codec, zero-byte file, etc.).
    """

    # ------------------------------------------------------------------
    # 1. Pre-flight: verify the file exists before handing it to OpenCV.
    #    os.path.exists is cheaper than letting cv2 open and silently fail.
    # ------------------------------------------------------------------
    if not os.path.exists(video_path):
        raise FileNotFoundError(
            f"Video file not found: '{video_path}'. "
            "Check that the upload was saved correctly before calling extract_frames()."
        )

    # ------------------------------------------------------------------
    # 2. Open the video capture handle.
    # ------------------------------------------------------------------
    cap = cv2.VideoCapture(video_path)

    # `isOpened()` returns False for corrupt files, unsupported codecs,
    # permission errors, and zero-byte uploads — anything OpenCV can't decode.
    if not cap.isOpened():
        raise ValueError(
            f"OpenCV could not open video: '{video_path}'. "
            "The file may be corrupt, use an unsupported codec, or have zero bytes."
        )

    # ------------------------------------------------------------------
    # 3. Read native FPS metadata and derive the frame interval.
    # ------------------------------------------------------------------
    native_fps: float = cap.get(cv2.CAP_PROP_FPS)
    total_frames: int = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Guard against malformed container metadata reporting 0 fps.
    # In that case we yield every frame — better than a ZeroDivisionError.
    if native_fps <= 0:
        print(
            f"[video_handler] WARNING: native FPS reported as {native_fps} for "
            f"'{video_path}'. Defaulting frame_interval to 1 (yield every frame)."
        )
        frame_interval = 1
    else:
        # round() rather than int() gives us the nearest integer interval,
        # which minimises cumulative timing drift over a long video.
        # max(..., 1) ensures we never skip *all* frames when target >= native.
        frame_interval = max(1, round(native_fps / target_fps))

    effective_fps = native_fps / frame_interval
    print(
        f"[video_handler] Opened '{os.path.basename(video_path)}' — "
        f"native: {native_fps:.2f} fps, total frames: {total_frames}, "
        f"frame_interval: {frame_interval}, effective output: ~{effective_fps:.1f} fps"
    )

    # ------------------------------------------------------------------
    # 4. Frame extraction loop — wrapped in try/finally for guaranteed cleanup.
    # ------------------------------------------------------------------
    try:
        frame_index: int = 0  # tracks the raw position in the source video

        while True:
            # `cap.read()` advances the internal seek pointer and decodes one
            # frame.  It returns (False, None) at end-of-stream or on a decode
            # error (e.g. a truncated final GOP in a damaged file).
            success, frame = cap.read()

            if not success:
                # Normal end-of-file — exit the loop cleanly.
                break

            # ---- Downsampling via modulo --------------------------------
            # yield only frames at positions 0, interval, 2*interval, ...
            # All other frames are discarded here; they never leave this scope,
            # so GC reclaims them immediately.
            if frame_index % frame_interval == 0:

                # ---- BGR → RGB conversion ------------------------------
                # OpenCV stores pixels in Blue-Green-Red order (a legacy of
                # early Windows bitmap conventions).  MediaPipe — like most
                # modern vision libraries — expects Red-Green-Blue order.
                # cv2.cvtColor is an in-place C extension call; it's fast and
                # does NOT copy the underlying buffer unless necessary.
                rgb_frame: np.ndarray = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                yield rgb_frame

            frame_index += 1

    finally:
        # ------------------------------------------------------------------
        # 5. Release the VideoCapture handle.
        #
        # `finally` runs in ALL exit scenarios:
        #   (a) Normal loop completion (end of video).
        #   (b) The caller breaks out of the generator early (e.g. with `break`
        #       inside a `for frame in extract_frames(...)` loop).
        #   (c) An exception is raised inside the loop (codec error mid-video).
        #   (d) The caller's GeneratorExit signal (garbage collection).
        #
        # Without this, the OS file descriptor and the decoder's frame buffer
        # remain open until the Python process exits — a classic resource leak.
        # ------------------------------------------------------------------
        cap.release()
        print(
            f"[video_handler] Released VideoCapture for '{os.path.basename(video_path)}' "
            f"after processing {frame_index} source frames."
        )


# ---------------------------------------------------------------------------
# Convenience introspection helper (no side effects, safe to call anytime)
# ---------------------------------------------------------------------------

def get_video_metadata(video_path: str) -> dict:
    """Return basic metadata about a video file without extracting frames.

    Useful for pre-flight validation in the API layer — e.g. rejecting videos
    that are too long before committing to the full pipeline.

    Args:
        video_path: Path to the video file.

    Returns:
        Dict with keys: path, fps, total_frames, duration_seconds,
        width, height.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError:        If OpenCV cannot open the file.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: '{video_path}'.")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"OpenCV could not open video: '{video_path}'.")

    try:
        fps           = cap.get(cv2.CAP_PROP_FPS)
        total_frames  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width         = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height        = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration      = (total_frames / fps) if fps > 0 else 0.0

        return {
            "path":             video_path,
            "fps":              fps,
            "total_frames":     total_frames,
            "duration_seconds": round(duration, 2),
            "width":            width,
            "height":           height,
        }
    finally:
        cap.release()


# ---------------------------------------------------------------------------
# Smoke test — run directly to validate against a real file:
#   python -m core.video_handler path/to/test.mp4
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m core.video_handler <path_to_video>")
        sys.exit(1)

    path = sys.argv[1]

    # Print metadata first
    meta = get_video_metadata(path)
    print(f"\nMetadata: {meta}\n")

    # Extract and count frames at 15 fps
    count = 0
    for rgb_frame in extract_frames(path, target_fps=15):
        count += 1
        if count == 1:
            print(f"First frame shape: {rgb_frame.shape}, dtype: {rgb_frame.dtype}")

    print(f"\nTotal frames yielded at ~15 fps: {count}")
    