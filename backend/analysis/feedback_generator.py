"""
analysis/feedback_generator.py
--------------------------------
Generates personalized push-up coaching feedback using Google's Gemini API.
"""

import os
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

FALLBACK_FEEDBACK = "Good effort! Keep working on your depth and form."

def generate_coach_feedback(
    rep_count: int,
    dtw_score: float,
    specific_errors: list,
    avg_depth: float
) -> str:
    """
    Calls Gemini API to generate 2 sentences of motivating, data-driven feedback.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("    [gemini] ERROR: GEMINI_API_KEY not found in environment.")
        return FALLBACK_FEEDBACK

    try:
        client = genai.Client(api_key=api_key)

        # Contextual depth description for the AI
        if avg_depth > 110:
            depth_label = "Shallow (Needs more bend)"
        elif avg_depth > 85:
            depth_label = "Perfect (Hit 90 degrees)"
        else:
            depth_label = "Elite (Deep range of motion)"

        errors_str = ', '.join(specific_errors) if specific_errors else 'None'

        # We put the persona AND the data into one single, inescapable prompt
        prompt = f"""
        Act as a kind but firm athletic coach speaking directly to a user who just finished a push-up set. You are supportive, but you expect them to put in the work and maintain good form.
        
        Data:
        - Reps: {rep_count}
        - Score: {dtw_score:.1f}/100
        - Depth: {avg_depth:.1f}° ({depth_label})
        - Errors: {errors_str}

        Write EXACTLY ONE short sentence of coaching feedback. 
        If Errors is 'None', give them a solid compliment on their form. 
        If there ARE Errors listed, give them a firm, constructive correction so they do better next time.
        CRITICAL: Do not mention depth, hips, or any other corrections unless they are explicitly listed in the Errors data above.
        """

        print("    [gemini] Sending data to Gemini...")
        
        # Stripped out the config block entirely to prevent token cut-offs
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        if response.text:
            # Clean up the text and remove any weird line breaks the AI might add
            feedback = response.text.strip().replace('\n', ' ')
            return feedback
            
        return FALLBACK_FEEDBACK

    except Exception as e:
        print(f"    [gemini] API Error: {e}")
        return FALLBACK_FEEDBACK


# --- Quick Test ---
if __name__ == "__main__":
    print("\n--- TEST RUN ---")
    output = generate_coach_feedback(5, 42.0, ["hips sagging", "insufficient depth"], 125.2)
    print(f"AI OUTPUT: {output}\n")
