from app.prompts.registry import PromptSpec, register_prompt
from app.prompts.system import SENTENCE_CHALLENGE_SYSTEM_PROMPT


SENTENCE_CHALLENGE_GENERATION_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="sentence_challenge_generation",
        version="v0.5b-2026-06-08",
        system_prompt_key="wenlingo_sentence_challenge",
        system_prompt=SENTENCE_CHALLENGE_SYSTEM_PROMPT,
        response_contract=(
            "Return a JSON object with exactly these fields: "
            "source_sentence: 5 to 25 Chinese characters, child-safe daily life content; "
            "challenge_prompt: 10 to 60 Chinese characters, task only, no answer; "
            "hint: 10 to 80 Chinese characters, observation angle only, no full answer; "
            "target_skill: one of expand_sentence, action_expression, feeling; "
            "focus: one of 扩句, 动作描写, 心理感受; "
            "difficulty_label: one of 四年级基础, 四年级进阶; "
            "grade_label: 四年级."
        ),
    )
)

SENTENCE_CHALLENGE_FEEDBACK_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="sentence_challenge_feedback",
        version="v0.5b-2026-06-08",
        system_prompt_key="wenlingo_sentence_challenge",
        system_prompt=SENTENCE_CHALLENGE_SYSTEM_PROMPT,
        response_contract=(
            "Return a JSON object with exactly these fields: "
            "encouragement: 8 to 30 Chinese characters, positive; "
            "highlight: 10 to 60 Chinese characters, one concrete strength; "
            "suggestion: 10 to 60 Chinese characters, one next-step suggestion; "
            "example_upgrade: 10 to 80 Chinese characters, one upgraded example sentence."
        ),
    )
)
