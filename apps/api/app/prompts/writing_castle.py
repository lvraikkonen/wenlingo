from app.prompts.registry import PromptSpec, register_prompt
from app.prompts.system import PRIMARY_COACH_SYSTEM_PROMPT


VERSION = "v0.6b-2026-06-25"
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
            "Return only this exact JSON object with no markdown: "
            '{"cards":[{"id":"topic-question","kind":"topic_question","title":"",'
            '"body":"","required_points":[]},{"id":"must-include",'
            '"kind":"must_include","title":"","body":"","required_points":[]},'
            '{"id":"shine-point","kind":"shine_point","title":"","body":"",'
            '"required_points":[]}],"suggested_focus":""}. '
            "cards must contain exactly 3 objects in that order. kind values must "
            "be exactly topic_question, must_include, shine_point. title <= 16 "
            "chars, body <= 80 chars, suggested_focus <= 80 chars. "
            "required_points is an array of 0-3 short strings. "
            "Response model: WritingTopicAnalysis. "
            "Do not include any keys not shown. " + NO_GHOSTWRITE
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
            "Return only this exact JSON object with no markdown: "
            '{"questions":[{"id":"q1","text":"","hint":"","order":1},'
            '{"id":"q2","text":"","hint":"","order":2},'
            '{"id":"q3","text":"","hint":"","order":3}],'
            '"encouragement":""}. questions must contain exactly 3 objects in '
            "that order. Ask about the first three payload.scaffold.material_slots "
            "when scaffold slots are present. "
            "text <= 60 chars, hint <= 80 chars, encouragement <= 40 chars. "
            "Response model: MaterialQuestionsResult. "
            "Do not include any keys not shown. " + NO_GHOSTWRITE
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
            "Return only this exact JSON object with no markdown: "
            '{"cards":[{"id":"card-<slot-id>","category":"<material_slot_id>","text":"",'
            '"source_answer_ids":[],"source_refs":[],"placeholder":true},'
            '{"id":"card-<slot-id>","category":"<material_slot_id>","text":"",'
            '"source_answer_ids":[],"source_refs":[],'
            '"placeholder":true}],"encouragement":""}. cards must contain '
            "1-8 objects matching the relevant payload.scaffold.material_slots order. "
            "Use payload.scaffold.material_slots[*].id as material card category values. "
            "Do not create category or slot values that are absent from payload.scaffold. "
            "Use source_answer_ids only from "
            "payload.answers[*].id. Every non-placeholder card must have non-empty "
            "text and at least one source_answer_ids or source_refs item. Empty or skipped child "
            "answers must become placeholder cards with empty text and empty "
            "source_answer_ids and source_refs. text <= 120 chars, encouragement <= 40 chars. "
            "Response model: MaterialCardsResult. "
            "Do not include any keys not shown. " + NO_GHOSTWRITE
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
            "Return only this exact JSON object with no markdown: "
            '{"sections":[{"id":"outline-<section-id>","slot":"<outline_section_id>","heading":"",'
            '"note":"","source_card_ids":[],"placeholder":true},'
            '{"id":"outline-<section-id>","slot":"<outline_section_id>","heading":"",'
            '"note":"","source_card_ids":[],"placeholder":true}],"tip":""}. '
            "sections must contain 1-6 objects matching the relevant payload.scaffold.outline_sections order. "
            "Use payload.scaffold.outline_sections[*].id as outline section slot values. "
            "Do not create category or slot values that are absent from payload.scaffold. "
            "Use source_card_ids only from "
            "payload.cards[*].id. Every non-placeholder section with story note "
            "must have at least one source_card_ids item. Empty source material "
            "must become placeholder sections with empty note and empty "
            "source_card_ids. heading <= 12 chars, note <= 80 chars, tip <= 60 "
            "chars. Response model: WritingOutlineResult. "
            "Do not include any keys not shown. " + NO_GHOSTWRITE
        ),
    )
)
