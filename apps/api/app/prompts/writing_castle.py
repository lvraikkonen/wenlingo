from app.prompts.registry import PromptSpec, register_prompt
from app.prompts.system import PRIMARY_COACH_SYSTEM_PROMPT


VERSION = "v0.6a-2026-06-20"
NO_GHOSTWRITE = (
    "Do not write full essay paragraphs. Do not invent people, events, dialogue, "
    "feelings, or lessons. Use only child-provided or explicitly confirmed material."
)

WRITING_TOPIC_ANALYSIS_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="writing_topic_analysis",
        version=VERSION,
        system_prompt_key="wenlingo_primary_coach",
        system_prompt=PRIMARY_COACH_SYSTEM_PROMPT,
        response_contract=(
            "Return WritingTopicAnalysis JSON. cards must contain exactly 3 objects: "
            "topic_question, must_include, shine_point. Each title <= 16 chars, "
            "body <= 80 chars. suggested_focus <= 80 chars. " + NO_GHOSTWRITE
        ),
    )
)

MATERIAL_QUESTIONS_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="material_questions",
        version=VERSION,
        system_prompt_key="wenlingo_primary_coach",
        system_prompt=PRIMARY_COACH_SYSTEM_PROMPT,
        response_contract=(
            "Return MaterialQuestionsResult JSON. questions must contain exactly 3 "
            "objects with id, text, hint, order. Ask for event, concrete detail, "
            "and feeling/takeaway. " + NO_GHOSTWRITE
        ),
    )
)

MATERIAL_CARD_GENERATION_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="material_card_generation",
        version=VERSION,
        system_prompt_key="wenlingo_primary_coach",
        system_prompt=PRIMARY_COACH_SYSTEM_PROMPT,
        response_contract=(
            "Return MaterialCardsResult JSON. cards must contain exactly 3 slots with "
            "categories event, detail, feeling_takeaway. Every non-placeholder card "
            "must include valid source_answer_ids from the payload. Empty child answers "
            "must become placeholder cards with empty text. " + NO_GHOSTWRITE
        ),
    )
)

OUTLINE_GENERATION_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="outline_generation",
        version=VERSION,
        system_prompt_key="wenlingo_primary_coach",
        system_prompt=PRIMARY_COACH_SYSTEM_PROMPT,
        response_contract=(
            "Return WritingOutlineResult JSON. sections must contain exactly 4 slots: "
            "cause, process, result, reflection. Every story-specific section must "
            "include valid source_card_ids from the payload. Empty source material "
            "must become placeholder sections. " + NO_GHOSTWRITE
        ),
    )
)
