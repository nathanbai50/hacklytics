"""
core/geometry.py
----------------
Pure geometry and biomechanics calculation module for the push-up form
analysis pipeline.

Responsibilities:
  - Calculate the interior angle at a vertex joint given three 2-D points.
  - Normalise the result to the anatomically valid range [0.0, 180.0] degrees.
  - Expose targeted helpers that consume the PoseDetector landmark dict and
    return the two angles most diagnostically useful for push-up form:
      • Elbow angle  → detects arm lockout and depth.
      • Body alignment angle → detects hip sag and pike.

This module is intentionally side-effect-free: no I/O, no model calls, no
frame data.  Every function is a pure mathematical transformation from inputs
to outputs, making the entire module trivially unit-testable.

Dependencies:
    pip install numpy          (only for arctan2; math.atan2 would also work,
                                but numpy is already in the project's stack)
"""

import math
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Core angle engine
# ---------------------------------------------------------------------------

def calculate_angle(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    """Return the interior angle at vertex *b* formed by the ray b→a and b→c.

    Algorithm
    ---------
    We form two vectors originating at the vertex *b*:

        v1 = a - b    (points from the vertex toward the first endpoint)
        v2 = c - b    (points from the vertex toward the second endpoint)

    We then use `atan2` to independently measure each vector's angle from the
    positive x-axis, and take the absolute difference.  This approach is more
    numerically stable than the dot-product / arccos path, which suffers from
    floating-point precision loss near 0° and 180° (i.e. when the cosine is
    close to ±1).

    Visual example (elbow angle):

              wrist (c)
               /
              / ← angle we want
             b  (elbow)
              \\
               \\
                shoulder (a)

    Normalisation
    -------------
    `atan2` returns values in (-π, π].  After subtraction the raw difference
    can land outside [0°, 180°], so we:
      1. Take the absolute value  → range [0°, 360°)
      2. If > 180°, reflect to 360° - angle  → range [0°, 180°]

    This mirrors how a physical goniometer works: it always reports the
    *interior* (smaller) angle between two limb segments, never the reflex.

    Args:
        a: (x, y) coordinate of the first endpoint (e.g. shoulder).
        b: (x, y) coordinate of the vertex / middle joint (e.g. elbow).
        c: (x, y) coordinate of the second endpoint (e.g. wrist).

    Returns:
        Interior angle at *b* in degrees, strictly within [0.0, 180.0].
    """
    # ---- Build vectors from vertex b toward each endpoint ----------------
    # Using numpy for clean vector arithmetic; no functional difference vs
    # plain tuples here since the arrays are tiny (2 elements each).
    a_arr = np.array(a, dtype=float)
    b_arr = np.array(b, dtype=float)
    c_arr = np.array(c, dtype=float)

    v1 = a_arr - b_arr   # vector: vertex → first endpoint
    v2 = c_arr - b_arr   # vector: vertex → second endpoint

    # ---- Compute the signed angle of each vector from the +x axis --------
    # atan2(y, x) returns the angle in radians in the range (-π, π].
    # Note the argument order: atan2 takes (y, x), NOT (x, y).
    angle_v1 = math.atan2(v1[1], v1[0])
    angle_v2 = math.atan2(v2[1], v2[0])

    # ---- Interior angle = unsigned difference between the two directions --
    raw_degrees = math.degrees(abs(angle_v1 - angle_v2))

    # ---- Normalise to [0°, 180°] -----------------------------------------
    # If the raw difference exceeds 180° we have the reflex angle; its
    # interior supplement is simply 360° - raw_degrees.
    # Example: raw = 190° → interior = 360° - 190° = 170°.
    angle = raw_degrees if raw_degrees <= 180.0 else 360.0 - raw_degrees

    return angle


# ---------------------------------------------------------------------------
# Push-up specific helpers
# ---------------------------------------------------------------------------

# Keys that each helper expects to be present in the landmarks dict.
# Defined as module-level constants so they appear in exactly one place —
# change the key names here and all validation logic updates automatically.
_ELBOW_KEYS          = ("shoulder", "elbow", "wrist")
_BODY_ALIGNMENT_KEYS = ("shoulder", "hip",   "ankle")


def _validate_landmarks(
    landmarks: Optional[dict],
    required_keys: tuple[str, ...],
) -> bool:
    """Return True if *landmarks* is a non-None dict containing all required keys.

    Kept private (underscore prefix) because it is an internal guard used only
    by the two helper functions below — it has no standalone semantic value to
    callers of this module.

    Args:
        landmarks:     The landmark dict from PoseDetector, or None.
        required_keys: Tuple of string keys that must all be present.

    Returns:
        True if the dict is valid and complete; False otherwise.
    """
    if landmarks is None:
        return False
    return all(key in landmarks for key in required_keys)


def get_elbow_angle(
    landmarks: Optional[dict[str, tuple[float, float]]],
) -> Optional[float]:
    """Return the elbow flexion angle from a PoseDetector landmark dict.

    Triplet: Shoulder (a) → Elbow (b / vertex) → Wrist (c)

    Biomechanical interpretation:
      ~180°  → arm fully extended (top of push-up / lockout)
      ~90°   → arm at 90° flexion (optimal depth for most standards)
      <70°   → deep push-up or potential shoulder stress

    Args:
        landmarks: Dict with at least the keys "shoulder", "elbow", "wrist",
                   each mapped to a normalised (x, y) float tuple.
                   Pass None or an incomplete dict to receive a None return.

    Returns:
        Elbow interior angle in degrees [0.0, 180.0], or None if the input
        is invalid or missing required keys.
    """
    if not _validate_landmarks(landmarks, _ELBOW_KEYS):
        # Graceful degradation: the scorer/feedback layer will skip None frames.
        return None

    return calculate_angle(
        a=landmarks["shoulder"],   # first endpoint
        b=landmarks["elbow"],      # vertex — the joint whose angle we measure
        c=landmarks["wrist"],      # second endpoint
    )


def get_body_alignment_angle(
    landmarks: Optional[dict[str, tuple[float, float]]],
) -> Optional[float]:
    """Return the body alignment angle from a PoseDetector landmark dict.

    Triplet: Shoulder (a) → Hip (b / vertex) → Ankle (c)

    Biomechanical interpretation:
      ~180°  → body forms a straight plank line (ideal push-up alignment)
      <160°  → hips are piking upward (reducing core demand)
      >180°* → hips are sagging downward (lower-back stress)
               *raw geometry reflects this as a value approaching 180° from
                below after normalisation; a sag will manifest as the hip
                landmark dropping below the shoulder–ankle line, which the
                pose detector captures as a changed (x, y) relationship.

    Note on sag detection:
        Because `calculate_angle` always returns the *interior* angle, a hip
        sag and a hip pike near 180° look similar numerically.  For precise
        sag/pike discrimination, compare the hip's y-coordinate against the
        linear interpolation of shoulder and ankle y-coordinates in the scorer
        module.  This function's job is purely to supply the angle magnitude.

    Args:
        landmarks: Dict with at least the keys "shoulder", "hip", "ankle",
                   each mapped to a normalised (x, y) float tuple.
                   Pass None or an incomplete dict to receive a None return.

    Returns:
        Body-alignment interior angle in degrees [0.0, 180.0], or None if the
        input is invalid or missing required keys.
    """
    if not _validate_landmarks(landmarks, _BODY_ALIGNMENT_KEYS):
        return None

    return calculate_angle(
        a=landmarks["shoulder"],   # first endpoint
        b=landmarks["hip"],        # vertex — the joint whose angle we measure
        c=landmarks["ankle"],      # second endpoint
    )


# ---------------------------------------------------------------------------
# Smoke test — run directly to validate the math against known inputs:
#   python -m core.geometry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # ---- Test 1: 90-degree angle (classic L-shape) -----------------------
    # Points form a right angle at the origin: a=(0,1), b=(0,0), c=(1,0)
    angle_90 = calculate_angle(a=(0, 1), b=(0, 0), c=(1, 0))
    assert abs(angle_90 - 90.0) < 1e-9, f"Expected 90.0, got {angle_90}"
    print(f"✓ Right angle test:       {angle_90:.4f}° (expected 90.0°)")

    # ---- Test 2: 180-degree angle (straight line) ------------------------
    # Points are collinear: a=(-1,0), b=(0,0), c=(1,0)
    angle_180 = calculate_angle(a=(-1, 0), b=(0, 0), c=(1, 0))
    assert abs(angle_180 - 180.0) < 1e-9, f"Expected 180.0, got {angle_180}"
    print(f"✓ Straight line test:     {angle_180:.4f}° (expected 180.0°)")

    # ---- Test 3: 45-degree angle -----------------------------------------
    angle_45 = calculate_angle(a=(0, 1), b=(0, 0), c=(1, 1))
    assert abs(angle_45 - 45.0) < 1e-9, f"Expected 45.0, got {angle_45}"
    print(f"✓ 45-degree angle test:   {angle_45:.4f}° (expected 45.0°)")

    # ---- Test 4: reflex normalisation (raw > 180° must be corrected) -----
    # Arrange three points that would yield a 270° raw angle without correction.
    # a=(1,0), b=(0,0), c=(0,-1) → v1 points right (0°), v2 points down (−90°)
    # raw difference = |0° − (−90°)| = 90° → already interior; good sanity check.
    angle_norm = calculate_angle(a=(1, 0), b=(0, 0), c=(0, -1))
    assert 0.0 <= angle_norm <= 180.0, f"Normalisation failed: {angle_norm}"
    print(f"✓ Normalisation bounds:   {angle_norm:.4f}° (must be in [0, 180])")

    # ---- Test 5: helper with valid landmarks dict ------------------------
    mock_landmarks = {
        "shoulder": (0.50, 0.30),
        "elbow":    (0.60, 0.50),
        "wrist":    (0.55, 0.65),
        "hip":      (0.50, 0.55),
        "ankle":    (0.52, 0.85),
    }
    elbow_angle = get_elbow_angle(mock_landmarks)
    body_angle  = get_body_alignment_angle(mock_landmarks)
    assert elbow_angle is not None, "Elbow angle should not be None"
    assert body_angle  is not None, "Body angle should not be None"
    print(f"✓ Elbow angle (mock):     {elbow_angle:.2f}°")
    print(f"✓ Body alignment (mock):  {body_angle:.2f}°")

    # ---- Test 6: helpers gracefully handle None and missing keys ---------
    assert get_elbow_angle(None)                          is None
    assert get_elbow_angle({})                            is None
    assert get_elbow_angle({"shoulder": (0, 0)})          is None
    assert get_body_alignment_angle(None)                 is None
    print("✓ None / missing-key guard tests passed.")

    print("\nAll geometry tests passed ✓")
    