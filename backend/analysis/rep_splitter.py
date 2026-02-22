"""
analysis/rep_splitter.py
------------------------
Counts and isolates individual push-up repetitions from a 1-D elbow-angle
time series produced by the geometry module.

Core algorithm  (valley-based, not peak-based)
----------------------------------------------
Previous versions found lockout PEAKS and counted the gaps between them.
This caused undercounting for three reasons:

  1. The final lockout is often a plateau (not a true local maximum), so
     find_peaks missed it and dropped the last rep entirely.
  2. N reps require N+1 clean peaks — one missed mid-set peak lost TWO
     reps simultaneously.
  3. A shaky lockout could split one peak into two, shifting all boundaries.

The new approach finds VALLEYS (bottoms of reps) instead.  Each rep produces
exactly one deep dip regardless of what the tops look like, and the final rep
is captured even if the set ends with a plateau hold.

Algorithm:
  1. Invert the signal and call find_peaks to locate valleys.
  2. Filter: keep only valleys that dip below VALLEY_DEPTH_THRESHOLD.
  3. Build rep slice boundaries as midpoints between consecutive valleys,
     using the signal edges as outer boundaries.
  4. Validate each slice: must contain at least one frame above
     LOCKOUT_MIN_ANGLE to confirm real arm extension occurred.

Dependencies:
    pip install scipy numpy
"""

import numpy as np
from scipy.signal import find_peaks


# ---------------------------------------------------------------------------
# Tuning constants — PRIMARY pass
# ---------------------------------------------------------------------------

# A valley must dip BELOW this angle to count as a rep bottom.
#
# *** THE KEY INSIGHT ***
# This must be significantly HIGHER than LOCKOUT_MIN_ANGLE to create a real
# detection window.  The required movement arc is:
#
#   top of rep (>= LOCKOUT_MIN_ANGLE)  ...descends...  bottom of rep (<= VALLEY_DEPTH_THRESHOLD)
#
# Old values: LOCKOUT=130, VALLEY=140 → only 10° window.
# A shallow rep peaking at 150° and bottoming at 145° passed the lockout
# check (150 > 130 ✓) but failed the valley check (145 not < 140 ✗),
# so it disappeared silently.
#
# New values: LOCKOUT=145, VALLEY=165 → 20° window.
# Any rep that bends even modestly past the top position is detected.
# The scorer penalises lack of depth; this module just finds movement.
VALLEY_DEPTH_THRESHOLD: float = 165.0

# Each rep slice must reach ABOVE this angle somewhere to confirm arm
# extension at the top.  Set 20° below VALLEY_DEPTH_THRESHOLD so the
# detection window is always wide enough for real, shallow reps.
LOCKOUT_MIN_ANGLE: float = 145.0

# Minimum depth a valley must drop below its local surroundings (degrees).
# Lowered to 8° — the VALLEY_DEPTH_THRESHOLD above is the real quality gate.
VALLEY_PROMINENCE: float = 8.0

# Minimum frames between consecutive valley bottoms.
# 10 frames @ 15 fps = 0.67 s minimum rep duration.
VALLEY_MIN_DISTANCE: int = 10

# ---------------------------------------------------------------------------
# Tuning constants — FALLBACK pass (last resort when primary finds 0)
# ---------------------------------------------------------------------------
# Catches someone who barely bends their arms at all.
# Window: any dip below 175° (almost any movement) with peak above 120°.
FALLBACK_VALLEY_DEPTH_THRESHOLD: float = 175.0
FALLBACK_LOCKOUT_MIN_ANGLE:       float = 120.0
FALLBACK_VALLEY_PROMINENCE:       float = 4.0
FALLBACK_VALLEY_MIN_DISTANCE:     int   = 6


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def segment_reps(
    elbow_angles: list[float],
    valley_depth_threshold: float = VALLEY_DEPTH_THRESHOLD,
    lockout_min_angle: float = LOCKOUT_MIN_ANGLE,
    valley_prominence: float = VALLEY_PROMINENCE,
    valley_min_distance: int = VALLEY_MIN_DISTANCE,
) -> list[list[float]]:
    """Segment a raw elbow-angle time series into individual push-up reps.

    Uses valley detection (rep bottoms) rather than peak detection (lockouts)
    so that the final rep is never dropped due to a missing terminal peak,
    and one missed lockout never causes two reps to be lost simultaneously.

    Args:
        elbow_angles:           1-D list of elbow angles (degrees) in order.
        valley_depth_threshold: Valley must drop below this to count as a rep.
        lockout_min_angle:      Each rep slice must reach above this at some
                                point to confirm real arm extension occurred.
        valley_prominence:      Minimum prominence for valley detection.
        valley_min_distance:    Minimum frames between consecutive valleys.

    Returns:
        List of rep angle slices (each a plain Python list of floats).
        Returns [] only when no push-up movement is detectable at all.
    """
    if not elbow_angles or len(elbow_angles) < 2:
        return []

    angles = np.array(elbow_angles, dtype=float)

    if not np.all(np.isfinite(angles)):
        angles = _interpolate_nans(angles)

    # ---- Pass 1: primary tolerant detection --------------------------------
    reps = _detect_reps_by_valleys(
        angles,
        valley_depth_threshold=valley_depth_threshold,
        lockout_min_angle=lockout_min_angle,
        valley_prominence=valley_prominence,
        valley_min_distance=valley_min_distance,
    )

    if reps:
        return reps

    # ---- Pass 2: fallback ultra-permissive ---------------------------------
    print(
        "[rep_splitter] Primary pass found 0 reps — retrying with "
        "fallback (permissive) thresholds."
    )
    reps = _detect_reps_by_valleys(
        angles,
        valley_depth_threshold=FALLBACK_VALLEY_DEPTH_THRESHOLD,
        lockout_min_angle=FALLBACK_LOCKOUT_MIN_ANGLE,
        valley_prominence=FALLBACK_VALLEY_PROMINENCE,
        valley_min_distance=FALLBACK_VALLEY_MIN_DISTANCE,
    )

    if reps:
        print(f"[rep_splitter] Fallback found {len(reps)} rep(s).")
    else:
        print("[rep_splitter] Fallback also found 0 — no push-up movement detected.")

    return reps


def count_reps(segmented_reps: list[list[float]]) -> int:
    """Return the number of valid reps from segment_reps output."""
    if not segmented_reps:
        return 0
    return len(segmented_reps)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_reps_by_valleys(
    angles: np.ndarray,
    valley_depth_threshold: float,
    lockout_min_angle: float,
    valley_prominence: float,
    valley_min_distance: int,
) -> list[list[float]]:
    """Core valley-based rep detection used by both passes.

    Steps:
        1. Invert the signal and call find_peaks to locate valleys.
        2. Filter: keep only valleys below valley_depth_threshold.
        3. Build rep boundaries as midpoints between consecutive valleys,
           with signal edges as outer boundaries for the first/last rep.
        4. Validate each slice: must reach above lockout_min_angle.

    The midpoint boundary approach means:
        - The first rep starts at frame 0 (captures the initial lockout).
        - The last rep ends at the final frame (captures terminal plateau holds).
        - No rep is ever dropped because a terminal peak was missed.
    """
    n = len(angles)

    # find_peaks finds maxima — negate to find minima (valleys).
    valley_indices, _ = find_peaks(
        -angles,
        prominence=valley_prominence,
        distance=valley_min_distance,
    )

    if len(valley_indices) == 0:
        return []

    # Keep only valleys that genuinely dip below the depth threshold.
    deep_valleys = [
        idx for idx in valley_indices
        if angles[idx] <= valley_depth_threshold
    ]

    if not deep_valleys:
        return []

    print(
        f"  [rep_splitter] {len(deep_valleys)} valley(s) at indices "
        f"{deep_valleys}, depths: {[round(float(angles[i]), 1) for i in deep_valleys]}"
    )

    # Build slice boundaries: midpoints between consecutive valley centres.
    #
    # Example — 4 valleys at [22, 52, 82, 112] in a 140-frame signal:
    #   Rep 1:  frames   0 → 36
    #   Rep 2:  frames  37 → 66
    #   Rep 3:  frames  67 → 96
    #   Rep 4:  frames  97 → 139   ← includes terminal plateau, no peak needed
    boundaries = [0]
    for i in range(len(deep_valleys) - 1):
        midpoint = (deep_valleys[i] + deep_valleys[i + 1]) // 2
        boundaries.append(midpoint)
    boundaries.append(n)

    valid_reps: list[list[float]] = []

    for i, valley_idx in enumerate(deep_valleys):
        start = boundaries[i]
        end   = boundaries[i + 1]
        rep_slice = angles[start:end]

        # Validate: at least one frame must reach lockout_min_angle,
        # confirming the arm was reasonably extended at some point.
        if float(np.max(rep_slice)) >= lockout_min_angle:
            valid_reps.append(rep_slice.tolist())
        else:
            print(
                f"  [rep_splitter] Dropping slice [{start}:{end}] — "
                f"max angle {np.max(rep_slice):.1f}° never reached "
                f"{lockout_min_angle}° lockout threshold"
            )

    return valid_reps


def _interpolate_nans(angles: np.ndarray) -> np.ndarray:
    """Replace NaN/Inf values with linear interpolation.

    MediaPipe occasionally drops a frame (occlusion, motion blur).
    Patching the gap keeps the rest of the signal usable.
    """
    result = angles.copy()
    finite_mask = np.isfinite(result)

    if not np.any(finite_mask):
        return np.zeros_like(result)

    indices = np.arange(len(result))
    result[~finite_mask] = np.interp(
        indices[~finite_mask],
        indices[finite_mask],
        result[finite_mask],
    )
    return result


# ---------------------------------------------------------------------------
# Smoke tests — run directly:
#   python -m analysis.rep_splitter
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Rep Splitter — Smoke Tests")
    print("=" * 60)

    def make_rep(start: float = 175.0, bottom: float = 85.0, n_points: int = 30) -> list:
        descent = np.linspace(start, bottom, n_points // 2)
        ascent  = np.linspace(bottom, start, n_points // 2)
        return np.concatenate([descent, ascent]).tolist()

    # ---- Test 1: 4-rep signal with terminal plateau (the classic undercount bug)
    # Old peak-based code would count 3 because the final plateau isn't a peak.
    signal = (
        [175.0] * 5
        + make_rep() + [175.0] * 3
        + make_rep() + [175.0] * 3
        + make_rep() + [175.0] * 3
        + make_rep()
        + [175.0] * 20   # terminal plateau hold — NOT a clean peak
    )
    rng = np.random.default_rng(seed=42)
    noisy = (np.array(signal) + rng.normal(0, 1.5, len(signal))).tolist()
    reps = segment_reps(noisy)
    print(f"\n[Test 1] 4-rep signal with terminal plateau")
    print(f"  Detected: {count_reps(reps)}  (expected 4 — old code returned 3)")
    for i, r in enumerate(reps):
        print(f"    Rep {i+1}: {len(r)} frames  min={min(r):.1f}°  max={max(r):.1f}°")
    assert count_reps(reps) == 4, f"Expected 4, got {count_reps(reps)}"

    # ---- Test 2: no inter-rep pause (reps run directly into each other)
    continuous = make_rep() + make_rep() + make_rep()
    cont_reps = segment_reps(continuous)
    print(f"\n[Test 2] 3 continuous reps (no pause between)")
    print(f"  Detected: {count_reps(cont_reps)}  (expected 3)")
    assert count_reps(cont_reps) == 3, f"Expected 3, got {count_reps(cont_reps)}"

    # ---- Test 3: beginner shallow reps (only reaches 120°)
    shallow_rep = make_rep(start=155.0, bottom=120.0, n_points=30)
    shallow_sig = [155.0] * 5 + shallow_rep + [155.0] * 3 + shallow_rep + [155.0] * 5
    shallow_reps = segment_reps(shallow_sig)
    print(f"\n[Test 3] Beginner shallow reps (bottom=120°)")
    print(f"  Detected: {count_reps(shallow_reps)}  (expected ≥ 1)")
    assert count_reps(shallow_reps) >= 1

    # ---- Test 4: beginner weak lockout (peaks only reach 135°)
    weak_rep = make_rep(start=135.0, bottom=100.0, n_points=30)
    weak_sig = [135.0] * 5 + weak_rep + [135.0] * 3 + weak_rep + [135.0] * 5
    weak_reps = segment_reps(weak_sig)
    print(f"\n[Test 4] Beginner weak lockout (peaks=135°)")
    print(f"  Detected: {count_reps(weak_reps)}  (expected ≥ 1)")
    assert count_reps(weak_reps) >= 1

    # ---- Test 5: flat signal — no reps
    flat_reps = segment_reps([170.0] * 60)
    assert flat_reps == [], f"Flat signal must return [], got {len(flat_reps)}"
    print(f"\n[Test 5] Flat signal → [] ✓")

    # ---- Test 6: empty input
    assert segment_reps([]) == []
    assert count_reps([]) == 0
    print(f"[Test 6] Empty input → [] ✓")

    # ---- Test 7: NaN handling
    nan_sig = signal[:20] + [float("nan")] * 3 + signal[23:]
    nan_reps = segment_reps(nan_sig)
    print(f"\n[Test 7] Signal with NaN frames → {count_reps(nan_reps)} reps (no crash ✓)")

    print("\n" + "=" * 60)
    print("All tests passed ✓")
    print("=" * 60)
    