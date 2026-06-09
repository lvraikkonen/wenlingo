from app.prompts.registry import PromptSpec, register_prompt
from app.prompts.system import PRIMARY_COACH_SYSTEM_PROMPT


SENTENCE_UPGRADE_FEEDBACK_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="sentence_upgrade_feedback",
        version="v0.5b-2026-06-08",
        system_prompt_key="wenlingo_primary_coach",
        system_prompt=PRIMARY_COACH_SYSTEM_PROMPT,
        response_contract=(
            "Return a JSON object with exactly these fields: "
            "encouragement: non-empty string; "
            "specific_improvement: non-empty string describing what improved; "
            "next_step: non-empty string with one small coaching action; "
            "ability_delta: object mapping ability names to integer deltas; "
            "problem_monsters: array of 1 to 3 non-empty strings."
        ),
    )
)
