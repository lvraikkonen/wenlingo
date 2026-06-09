from app.prompts.registry import PromptSpec, register_prompt
from app.prompts.system import PRIMARY_COACH_SYSTEM_PROMPT


ESSAY_REVISION_COMPARISON_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="essay_revision_comparison",
        version="v0.5b-2026-06-08",
        system_prompt_key="wenlingo_primary_coach",
        system_prompt=PRIMARY_COACH_SYSTEM_PROMPT,
        response_contract=(
            "Return a JSON object with exactly these fields: "
            "encouragement: non-empty string; "
            "improved_dimensions: array of 1 to 3 non-empty strings; "
            "evidence: array of 1 to 3 non-empty strings quoted or summarized from the revision; "
            "next_step: non-empty string with one small coaching action."
        ),
    )
)
