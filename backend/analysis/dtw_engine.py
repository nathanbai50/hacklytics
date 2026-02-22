"""
analysis/dtw_engine.py
-----------------------
Push-up form quality scoring engine.

Scoring approach: 50% raw-angle DTW + 50% heuristic
------------------------------------------------------
Both components are necessary and complementary:

  DTW (Dynamic Time Warping) on RAW angles — captures how closely the
  movement matches a reference rep in terms of depth AND tempo AND
  smoothness. Running DTW on raw (un-normalised) angles means a shallow
  rep that doesn't reach the golden rep's depth produces a large per-frame
  angle difference, giving a low DTW score. A fast rep that reaches the
  same depth warps to match the golden and scores well.

  Heuristic (absolute biomechanics) — directly measures depth, lockout,
  and range of motion against fixed standards. Catches cases where a
  rep's global shape matches the reference but specific biomechanical
  criteria are missed. Also the sole scorer when no library exists.

  Previous mistake: z-score and min-max normalisation both scaled each
  series independently, making every U-shaped curve look identical regardless
  of depth. Raw angles preserve the actual degree values so a shallow rep
  (148° bottom) is genuinely far from a deep rep (88° bottom).

Max acceptable distance = 20.0°
  At 15fps, a rep with a 20° per-frame average error vs the golden is
  fundamentally mismatched. Shallow reps score ~28, good reps score ~90+.

Dependencies:
    pip install fastdtw scipy numpy
"""

import math
import numpy as np
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean


PENALTY_DISTANCE: float = 9999.0

# Per-frame angle difference (degrees) that maps to a score of 0.
# A 20° average error per frame means the rep shape is fundamentally wrong.
DTW_MAX_DIST_DEGREES: float = 20.0

# Blend weights — must sum to 1.0
DTW_WEIGHT:       float = 0.50
HEURISTIC_WEIGHT: float = 0.50


# ---------------------------------------------------------------------------
# 1. Core DTW distance — raw angles, no normalisation
# ---------------------------------------------------------------------------

def calculate_dtw_distance(
    user_angles: list[float],
    golden_angles: list[float],
) -> float:
    """Return a path-normalised DTW distance in raw degrees.

    No normalisation is applied. Both series are compared in the original
    angle space so that a shallow rep genuinely produces a large distance
    from a deep golden rep.

    DTW's warping handles tempo differences: a fast rep with correct depth
    warps to match the golden and produces a small distance; a shallow rep
    at any tempo cannot warp its way to the correct depth, producing a large
    distance.

    Returns:
        Mean per-frame DTW distance in degrees, or PENALTY_DISTANCE on error.
    """
    if not user_angles or not golden_angles:
        return PENALTY_DISTANCE

    u = np.array(user_angles,   dtype=float).reshape(-1, 1)
    g = np.array(golden_angles, dtype=float).reshape(-1, 1)

    if not np.all(np.isfinite(u)) or not np.all(np.isfinite(g)):
        return PENALTY_DISTANCE

    try:
        distance, path = fastdtw(u, g, dist=euclidean)
        mean_dist = float(distance) / len(path)
        print(f"    [dtw] raw={distance:.2f}°  path_len={len(path)}  mean={mean_dist:.2f}°")
        return mean_dist
    except Exception as exc:
        print(f"    [dtw] error: {exc}")
        return PENALTY_DISTANCE


# ---------------------------------------------------------------------------
# 2. DTW distance → 0-100 score
# ---------------------------------------------------------------------------

def calculate_form_score(
    dtw_distance: float,
    max_acceptable_distance: float = DTW_MAX_DIST_DEGREES,
) -> int:
    """Map a raw-degree DTW distance to a 0-100 score.

    0° difference  → 100 (perfect match)
    20°+ per frame → 0   (fundamental mismatch)
    """
    if max_acceptable_distance <= 0:
        return 0
    if dtw_distance <= 0.0:
        return 100
    raw = 100.0 * (1.0 - dtw_distance / max_acceptable_distance)
    return max(0, min(100, int(raw)))


# ---------------------------------------------------------------------------
# 3. Heuristic scorer — absolute biomechanics
# ---------------------------------------------------------------------------

def score_rep_heuristic(rep_elbow_angles: list[float]) -> tuple[int, list[str]]:
    """Score a single rep against absolute biomechanical standards.

    Scoring breakdown (100 pts)
    ----------------------------
    Depth (50 pts)   — primary quality signal.
        100%: elbow ≤ 90°   (chest near floor)
          0%: elbow ≥ 140°  (barely any bend)

    Lockout (30 pts) — confirms full arm extension.
        100%: elbow ≥ 160°
          0%: elbow ≤ 130°

    Range of motion (20 pts) — total arc.
        100%: arc ≥ 70°
          0%: arc ≤ 20°

    Returns:
        (score: int 0–100, errors: list[str])
    """
    if not rep_elbow_angles:
        return 0, ["no angle data"]

    min_angle = min(rep_elbow_angles)
    max_angle = max(rep_elbow_angles)
    arc       = max_angle - min_angle

    errors: list[str] = []
    points: float = 0.0

    # Depth — 50 pts
    DEPTH_FULL, DEPTH_ZERO = 90.0, 140.0
    if min_angle <= DEPTH_FULL:
        points += 50.0
    elif min_angle >= DEPTH_ZERO:
        errors.append("insufficient depth")
    else:
        depth_pct = 1.0 - (min_angle - DEPTH_FULL) / (DEPTH_ZERO - DEPTH_FULL)
        points += 50.0 * depth_pct
        if depth_pct < 0.5:
            errors.append("insufficient depth")

    # Lockout — 30 pts
    LOCK_FULL, LOCK_ZERO = 160.0, 130.0
    if max_angle >= LOCK_FULL:
        points += 30.0
    elif max_angle <= LOCK_ZERO:
        errors.append("incomplete lockout")
    else:
        lock_pct = (max_angle - LOCK_ZERO) / (LOCK_FULL - LOCK_ZERO)
        points += 30.0 * lock_pct
        if lock_pct < 0.5:
            errors.append("incomplete lockout")

    # Range of motion — 20 pts
    ARC_FULL, ARC_ZERO = 70.0, 20.0
    if arc >= ARC_FULL:
        points += 20.0
    elif arc <= ARC_ZERO:
        errors.append("very limited range of motion")
    else:
        arc_pct = (arc - ARC_ZERO) / (ARC_FULL - ARC_ZERO)
        points += 20.0 * arc_pct

    score = max(0, min(100, int(points)))
    print(
        f"    [heuristic] min={min_angle:.1f}°  max={max_angle:.1f}°  "
        f"arc={arc:.1f}°  pts={points:.1f}  score={score}  errors={errors}"
    )
    return score, errors


# ---------------------------------------------------------------------------
# 4. Blended per-rep score
# ---------------------------------------------------------------------------

def score_rep_blended(
    user_rep_angles: list[float],
    golden_angles: list[float],
) -> tuple[int, list[str]]:
    """Return a blended score combining raw-angle DTW and heuristic.

    DTW (50%): how closely depth, tempo, and smoothness match the reference.
    Heuristic (50%): did the rep meet absolute depth/lockout standards?

    Returns:
        (blended_score: int 0–100, errors: list[str])
    """
    dtw_dist  = calculate_dtw_distance(user_rep_angles, golden_angles)
    dtw_score = calculate_form_score(dtw_dist)
    h_score, errors = score_rep_heuristic(user_rep_angles)

    blended = max(0, min(100, round(DTW_WEIGHT * dtw_score + HEURISTIC_WEIGHT * h_score)))
    print(
        f"    [blend] dtw={dtw_score}  heuristic={h_score}  "
        f"blended={blended}"
    )
    return blended, errors


# ---------------------------------------------------------------------------
# 5. Library evaluation
# ---------------------------------------------------------------------------

def evaluate_against_library(
    user_rep_angles: list[float],
    golden_library: dict[str, list[float]],
    max_acceptable_distance: float = DTW_MAX_DIST_DEGREES,
) -> tuple[str, float, int]:
    """Find the best-matching reference and return a blended score.

    Picks the reference with the lowest raw-angle DTW distance (best
    shape + depth match), then computes the blended score against it.

    Falls back to heuristic-only when no library exists.

    Returns:
        (best_match_name: str, dtw_distance: float, blended_score: int)
    """
    if not user_rep_angles:
        return ("no_reference", PENALTY_DISTANCE, 0)

    # No library — heuristic only
    if not golden_library:
        print("    [evaluate] No library → heuristic only")
        score, _ = score_rep_heuristic(user_rep_angles)
        return ("heuristic", 0.0, score)

    # Find closest reference by raw DTW distance
    best_name:     str   = "no_reference"
    best_distance: float = float("inf")

    for ref_name, ref_angles in golden_library.items():
        if not ref_angles or not isinstance(ref_angles, list):
            continue
        dist = calculate_dtw_distance(user_rep_angles, ref_angles)
        print(f"    [evaluate] vs '{ref_name}': {dist:.2f}°")
        if dist < best_distance:
            best_distance = dist
            best_name     = ref_name

    if best_name == "no_reference" or not math.isfinite(best_distance):
        # All library entries failed — fall back to heuristic
        score, _ = score_rep_heuristic(user_rep_angles)
        return ("no_reference", PENALTY_DISTANCE, score)

    # Blended score against best-matching reference
    best_ref_angles = golden_library[best_name]
    final_score, _ = score_rep_blended(user_rep_angles, best_ref_angles)
    return (best_name, best_distance, final_score)
