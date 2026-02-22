"""
api/server.py
-------------
FastAPI backend for the push-up form analyzer.

Run with:
    uvicorn api.server:app --reload
"""

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from core.video_handler          import extract_frames
from core.pose_detector          import PoseDetector
from core.geometry               import get_elbow_angle, get_body_alignment_angle
from analysis.rep_splitter       import segment_reps
from analysis.dtw_engine         import evaluate_against_library, score_rep_heuristic
from analysis.feedback_generator import generate_coach_feedback

import os
from pydantic import BaseModel
from google import genai

class WorkoutHistory(BaseModel):
    total_lifetime_sets: int
    recent_scores: list[int]
    recent_reps: list[int]
    average_depth: float
    recent_takeaways: list[str]

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Push-Up Form Analyzer",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UPLOAD_DIR         = Path("data/temp_uploads")
GOLDEN_LIBRARY_DIR = Path("data/golden_library")
ALLOWED_EXTENSIONS = {".mp4", ".mov"}

HIP_SAG_THRESHOLD:           float = 160.0  # degrees — below this = sagging
HIP_SAG_FREQUENCY_THRESHOLD: float = 0.30   # fraction of frames that must sag

# Single source of truth for the DTW scoring scale.
# After z-score normalisation, mean per-frame distance of 1.0 = complete
# shape mismatch.  This is passed through evaluate_against_library →
# calculate_form_score so both functions always agree on the scale.
DTW_MAX_ACCEPTABLE_DISTANCE: float = 1.0


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def create_directories() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    GOLDEN_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    print("[startup] Directories ready.")


# ---------------------------------------------------------------------------
# Golden library loader
# ---------------------------------------------------------------------------

def load_golden_library() -> dict[str, list[float]]:
    """Load all .json reference-rep files from GOLDEN_LIBRARY_DIR.

    Each file must be a JSON array of elbow-angle floats.
    Returns an empty dict if the directory has no .json files — the pipeline
    will fall back to heuristic scoring automatically.
    """
    library: dict[str, list[float]] = {}

    json_files = list(GOLDEN_LIBRARY_DIR.glob("*.json"))
    if not json_files:
        print(
            "[library] ⚠  No .json files found in data/golden_library/. "
            "Heuristic scoring will be used instead of DTW."
        )
        return library

    for json_file in sorted(json_files):
        try:
            angles = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(angles, list) and angles:
                library[json_file.stem] = [float(a) for a in angles]
                print(f"  [library] Loaded '{json_file.stem}' ({len(angles)} frames)")
            else:
                print(f"  [library] WARN: '{json_file.name}' empty or malformed — skipped.")
        except Exception as exc:
            print(f"  [library] WARN: Could not parse '{json_file.name}': {exc}")

    return library


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_analysis_pipeline(file_path: str) -> dict:
    """Full push-up analysis pipeline.

    Stages
    ------
    1. Init PoseDetector + load golden library (may be empty — that's OK).
    2. Extract frames → landmarks → elbow & hip angles.
    3. Segment elbow series into individual reps.
    4. Score each rep via DTW (or heuristics if no library).
       Collect form errors from both heuristics AND hip-sag detection.
    5. Generate Snowflake Cortex coaching feedback with the real error list.
    6. Return structured result dict.

    Always synchronous — called via asyncio.to_thread() from the endpoint.
    """

    # =========================================================================
    # STEP 1 — Initialisation
    # =========================================================================
    print(f"\n{'='*60}")
    print(f"[pipeline] {Path(file_path).name}")
    print(f"{'='*60}")

    detector = PoseDetector(
        static_image_mode=False,
        model_complexity=1,
        min_detection_confidence=0.5,
    )
    print("[pipeline] STEP 1 ✓  PoseDetector ready.")

    golden_library = load_golden_library()
    scoring_mode   = "DTW" if golden_library else "heuristic"
    print(f"[pipeline] STEP 1 ✓  Scoring mode: {scoring_mode}")

    try:
        # =====================================================================
        # STEP 2 — Frame extraction + angle calculation
        # =====================================================================
        print("[pipeline] STEP 2 →  Extracting frames…")

        raw_elbow_angles: list[float] = []
        raw_hip_angles:   list[float] = []
        frames_processed = 0
        frames_detected  = 0

        for rgb_frame in extract_frames(file_path, target_fps=15):
            frames_processed += 1
            landmarks = detector.extract_landmarks(rgb_frame)

            if landmarks is None:
                continue

            frames_detected += 1

            elbow_angle = get_elbow_angle(landmarks)
            hip_angle   = get_body_alignment_angle(landmarks)

            if elbow_angle is not None:
                raw_elbow_angles.append(elbow_angle)
            if hip_angle is not None:
                raw_hip_angles.append(hip_angle)

        print(
            f"[pipeline] STEP 2 ✓  {frames_processed} frames | "
            f"{frames_detected} detected | "
            f"{len(raw_elbow_angles)} elbow | {len(raw_hip_angles)} hip"
        )

        # =====================================================================
        # STEP 3 — Rep segmentation
        # =====================================================================
        print("[pipeline] STEP 3 →  Segmenting reps…")

        segmented_reps: list[list[float]] = segment_reps(raw_elbow_angles)
        rep_count = len(segmented_reps)

        print(f"[pipeline] STEP 3 ✓  Reps found: {rep_count}")

        if rep_count == 0:
            return {
                "status":  "error",
                "message": (
                    "No valid push-ups detected. Ensure your full body is "
                    "visible and complete at least one full rep."
                ),
            }

        # =====================================================================
        # STEP 4 — Scoring + error detection
        #
        # Two error sources are combined here:
        #   A) Heuristic form errors  (depth, lockout, range-of-motion)
        #      — returned directly by evaluate_against_library when no library
        #        exists, or by score_rep_heuristic when called separately.
        #   B) Hip-sag errors  (body alignment angle below threshold).
        #
        # Both are collected into `specific_errors` before the LLM call so the
        # coach receives the real, complete picture of what went wrong.
        # =====================================================================
        print(f"[pipeline] STEP 4 →  Scoring reps ({scoring_mode})…")

        rep_details:        list[dict] = []
        all_scores:         list[int]  = []
        # Use a set to deduplicate errors that appear across multiple reps
        # (e.g. "insufficient depth" on rep 1 AND rep 3 should appear once).
        all_form_errors:    set[str]   = set()
        hip_cursor = 0

        for rep_index, rep_elbow_angles in enumerate(segmented_reps):
            rep_number = rep_index + 1
            print(f"  Rep {rep_number}:")

            # ── A) Score + form errors ───────────────────────────────────
            # evaluate_against_library now always scores via score_rep_heuristic
            # regardless of library state — DTW is only used to pick the best
            # matching reference name. We always call score_rep_heuristic here
            # to get the error list, since evaluate_against_library drops it.
            best_name, best_distance, score = evaluate_against_library(
                user_rep_angles=rep_elbow_angles,
                golden_library=golden_library,
                max_acceptable_distance=DTW_MAX_ACCEPTABLE_DISTANCE,
            )
            all_scores.append(score)

            # Always collect form errors — previously this only ran when
            # best_name == "heuristic", which meant errors were never collected
            # once a golden library existed (best_name was always a ref name).
            _, rep_form_errors = score_rep_heuristic(rep_elbow_angles)
            all_form_errors.update(rep_form_errors)
            print(f"    matched='{best_name}'  DTW={best_distance:.4f}  score={score}  errors={rep_form_errors}")

            # ── B) Hip-sag detection ──────────────────────────────────────
            rep_frame_count = len(rep_elbow_angles)
            rep_hip_slice   = raw_hip_angles[hip_cursor : hip_cursor + rep_frame_count]
            hip_cursor      += rep_frame_count

            min_elbow = min(rep_elbow_angles) if rep_elbow_angles else 0.0
            avg_body  = (sum(rep_hip_slice) / len(rep_hip_slice)) if rep_hip_slice else 180.0

            hip_sag_this_rep = False
            if rep_hip_slice:
                sag_count        = sum(1 for a in rep_hip_slice if a < HIP_SAG_THRESHOLD)
                sag_fraction     = sag_count / len(rep_hip_slice)
                hip_sag_this_rep = sag_fraction >= HIP_SAG_FREQUENCY_THRESHOLD
                if hip_sag_this_rep:
                    print(f"    ⚠ hip sag: {sag_fraction:.0%} of frames")

            rep_details.append({
                "rep_number":      int(rep_number),
                "dtw_score":       int(score),
                "min_elbow_angle": float(round(min_elbow, 1)),
                "avg_body_angle":  float(round(avg_body, 1)),
                # Internal — stripped before response is sent
                "_hip_sag":        hip_sag_this_rep,
            })

        # ── Aggregate errors from both sources ────────────────────────────
        # FIX: read from rep_details["_hip_sag"], not a stale loop variable
        if any(r["_hip_sag"] for r in rep_details):
            all_form_errors.add("hips sagging")

        specific_errors = sorted(all_form_errors)   # deterministic order for LLM

        # Worst-rep-anchored aggregation.
        # Simple mean is gamed by one good rep at the end of a bad set.
        # Instead: blend the mean (70%) with the single worst rep score (30%).
        # This ensures a set of [30, 30, 30, 30, 100] scores ~44 not ~60,
        # while a uniform good set [95, 92, 98] still scores ~94.
        mean_score  = sum(all_scores) / len(all_scores)
        worst_score = min(all_scores)
        average_score: int = round(mean_score * 0.7 + worst_score * 0.3)

        print(
            f"[pipeline] STEP 4 ✓  avg score={average_score}/100 | "
            f"errors={specific_errors or 'none'}"
        )

        # =====================================================================
        # STEP 5 — Snowflake Cortex coaching feedback
        #
        # specific_errors now contains the real, populated error list from
        # both heuristic and hip-sag detection.  The LLM will address them.
        # =====================================================================
        print("[pipeline] STEP 5 →  Generating coaching feedback…")

        # Calculate the average depth across all reps
        if rep_details:
            avg_depth = sum(r["min_elbow_angle"] for r in rep_details) / len(rep_details)
        else:
            avg_depth = 0.0

        coach_feedback: str = generate_coach_feedback(
            rep_count=rep_count,
            dtw_score=float(average_score),
            specific_errors=specific_errors,
            avg_depth=avg_depth  # <--- Pass the new depth variable!
        )

        print(f"[pipeline] STEP 5 ✓  Feedback: \"{coach_feedback}\"")
        # =====================================================================
        # STEP 6 — Build response (matches Swift SetData / RepData models)
        # =====================================================================
        # Strip internal "_hip_sag" key before sending to client
        client_rep_details = [
            {
                "rep_number":      r["rep_number"],
                "dtw_score":       r["dtw_score"],
                "min_elbow_angle": r["min_elbow_angle"],
                "avg_body_angle":  r["avg_body_angle"],
            }
            for r in rep_details
        ]

        print("[pipeline] STEP 6 ✓  Done.")

        return {
            "overall_score":     int(average_score),
            "total_valid_reps":  int(rep_count),
            "coaching_takeaway": str(coach_feedback),
            "rep_data":          client_rep_details,
        }

    except Exception as exc:
        print(f"[pipeline] ✗ {type(exc).__name__}: {exc}")
        return {
            "status":  "error",
            "message": f"Analysis pipeline failed: {str(exc)}",
        }

    finally:
        detector.close()
        print("[pipeline] CLEANUP ✓  PoseDetector released.")
        print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Background cleanup
# ---------------------------------------------------------------------------

def delete_temp_file(file_path: Path) -> None:
    try:
        file_path.unlink(missing_ok=True)
        print(f"[cleanup] Deleted: {file_path.name}")
    except Exception as exc:
        print(f"[cleanup] WARN: {exc}")


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------

@app.post("/analyze")
async def analyze_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Push-up video (.mp4 or .mov)"),
):
    """Accept a video upload, run the full analysis pipeline, return results."""

    # Validate extension
    original_suffix = Path(file.filename).suffix.lower() if file.filename else ""
    if original_suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{original_suffix}'. "
                f"Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    # Persist upload
    save_path = UPLOAD_DIR / f"{uuid.uuid4()}{original_suffix}"
    try:
        contents = await file.read()
        save_path.write_bytes(contents)
        print(f"[endpoint] Saved {save_path.name} ({len(contents):,} bytes)")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}") from exc

    # Run pipeline in thread pool (CPU-bound, not async-native)
    result = await asyncio.to_thread(run_analysis_pipeline, str(save_path))

    # Delete temp file after response is sent
    background_tasks.add_task(delete_temp_file, save_path)

    return result

# ---------------------------------------------------------------------------
# POST /generate_goal
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# POST /generate_goal
# ---------------------------------------------------------------------------
@app.post("/generate_goal")
async def generate_goal(history: WorkoutHistory):
    # 1. Intercept beginners (< 5 sets) and return 0s
    if history.total_lifetime_sets < 5:
        return {
            "rep_goal": 0,
            "score_goal": 0,
            "goal": "Keep pushing! Your AI is analyzing your baseline to generate your next milestone."
        }

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "rep_goal": 0,
            "score_goal": 0,
            "goal": "Set up your API key to get personalized goals!"
        }
        
    client = genai.Client(api_key=api_key)
    
    unique_takeaways = list(set(history.recent_takeaways))
    max_reps = max(history.recent_reps) if history.recent_reps else 0
    avg_score = sum(history.recent_scores) / len(history.recent_scores) if history.recent_scores else 0
    
    # 2. Since the AI only runs for >= 5 sets, it will ALWAYS generate real numbers here
    prompt = f"""
    Act as a kind but firm athletic coach. Look at this user's profile data:
    - Total Lifetime Sets: {history.total_lifetime_sets}
    - Recent Scores: {history.recent_scores} (Avg: {avg_score:.1f})
    - Recent Reps per set: {history.recent_reps} (Max: {max_reps})
    - Average Depth: {history.average_depth:.1f}° (90 is perfect, >110 is shallow)
    - Recent AI Coach Feedback: {unique_takeaways}
    
    Based on this data, calculate their next major milestone and provide a short, firm coaching sentence.
    - rep_goal: A realistic but challenging target (e.g., 2 to 4 reps higher than their current max).
    - score_goal: A target score (e.g., 90 if their average is 80, or 95 if they are already at 90).
    - goal: ONE short, punchy sentence focusing on achieving this new long-term target.

    You MUST respond with ONLY a valid raw JSON object. Do not use markdown blocks like ```json.
    Format exactly like this, but replaced the values with the actual values and goal text:
    {{
        "rep_goal": 15,
        "score_goal": 90,
        "goal": "Your next major milestone is to hit 15 unbroken reps with flawless core stability."
    }}
    """
    
    try:
        print(f"[endpoint] Generating structured JSON goal for user...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        cleaned_text = response.text.strip().removeprefix('```json').removesuffix('```').strip()
        goal_data = json.loads(cleaned_text)
        
        print(f"[endpoint] Goal generated successfully: {goal_data}")
        return goal_data
        
    except json.JSONDecodeError as e:
        print(f"[endpoint] Failed to parse AI JSON: {e} - Raw text: {response.text}")
        return {
            "rep_goal": max_reps + 2,
            "score_goal": 85,
            "goal": "Push for those extra reps today while keeping your form tight."
        }
    except Exception as e:
        print(f"[endpoint] Goal generation failed: {e}")
        return {
            "rep_goal": max_reps + 2,
            "score_goal": 85,
            "goal": "Keep pushing! Focus on clean form and try to beat your last score today."
        }
    