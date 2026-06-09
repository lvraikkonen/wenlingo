from app.prompts.registry import PromptSpec, register_prompt
from app.prompts.system import PRIMARY_COACH_SYSTEM_PROMPT


ESSAY_FEEDBACK_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="essay_feedback",
        version="v0.5b-2026-06-08",
        system_prompt_key="wenlingo_primary_coach",
        system_prompt=PRIMARY_COACH_SYSTEM_PROMPT,
        response_contract=(
            "Return a JSON object with exactly these fields: "
            "strengths: array of exactly 2 non-empty strings; "
            "improvements: array of 1 to 3 non-empty strings; "
            "problem_monsters: array of 1 to 3 non-empty strings; "
            "sentence_notes: array of 1 to 3 non-empty strings; "
            "revision_tasks: array of exactly 1 object with non-empty instruction and target strings. "
            "Pick the smallest and most important revision task. Do not write a full essay."
        ),
    )
)
