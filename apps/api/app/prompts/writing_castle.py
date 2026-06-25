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
            "that order. Ask for event, concrete detail, and feeling/takeaway. "
            "text <= 60 chars, hint <= 80 chars, encouragement <= 40 chars. "
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
            '{"cards":[{"id":"card-event","category":"event","text":"",'
            '"source_answer_ids":[],"placeholder":true},{"id":"card-detail",'
            '"category":"detail","text":"","source_answer_ids":[],'
            '"placeholder":true},{"id":"card-feeling",'
            '"category":"feeling_takeaway","text":"","source_answer_ids":[],'
            '"placeholder":true}],"encouragement":""}. cards must contain exactly '
            "3 objects in that order with categories event, detail, "
            "feeling_takeaway. Use source_answer_ids only from "
            "payload.answers[*].id. Every non-placeholder card must have non-empty "
            "text and at least one source_answer_ids item. Empty or skipped child "
            "answers must become placeholder cards with empty text and empty "
            "source_answer_ids. text <= 120 chars, encouragement <= 40 chars. "
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
            '{"sections":[{"id":"outline-cause","slot":"cause","heading":"起因",'
            '"note":"","source_card_ids":[],"placeholder":true},'
            '{"id":"outline-process","slot":"process","heading":"经过",'
            '"note":"","source_card_ids":[],"placeholder":true},'
            '{"id":"outline-result","slot":"result","heading":"结果",'
            '"note":"","source_card_ids":[],"placeholder":true},'
            '{"id":"outline-reflection","slot":"reflection","heading":"感受",'
            '"note":"","source_card_ids":[],"placeholder":true}],"tip":""}. '
            "sections must contain exactly 4 objects in that order with slots "
            "cause, process, result, reflection. Use source_card_ids only from "
            "payload.cards[*].id. Every non-placeholder section with story note "
            "must have at least one source_card_ids item. Empty source material "
            "must become placeholder sections with empty note and empty "
            "source_card_ids. heading <= 12 chars, note <= 80 chars, tip <= 60 "
            "chars. Do not include any keys not shown. " + NO_GHOSTWRITE
        ),
    )
)
