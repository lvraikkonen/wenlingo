from app.prompts.registry import PromptSpec, register_prompt
from app.prompts.system import PRIMARY_COACH_SYSTEM_PROMPT


WRITING_CASTLE_VERSION = "v0.6b-2026-06-25"
WRITING_TOPIC_ANALYSIS_VERSION = "v0.6b.1-2026-06-27"
MATERIAL_QUESTIONS_VERSION = "v0.6b.1-2026-06-27"
MATERIAL_CARD_VERSION = "v0.6b.1-2026-06-27"
WRITING_TOPIC_IDEA_GENERATION_VERSION = "v0.6c-2026-06-29"
NO_GHOSTWRITE = (
    "Do not write full essay paragraphs. Do not invent people, events, dialogue, "
    "feelings, or lessons. Use only child-provided or explicitly confirmed material."
)

WRITING_TOPIC_ANALYSIS_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="writing_topic_analysis",
        version=WRITING_TOPIC_ANALYSIS_VERSION,
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
            "If payload.scaffold.topic_type is expository_introduction, do not add external facts, "
            "numbers, habits, labels, or background claims that are absent from payload.topic_text "
            "or child/source input. You may restate factual phrases already present in payload.topic_text "
            "as assignment requirements, but do not expand them into new facts. For 国宝大熊猫, "
            "do not add facts such as 吃竹子, 活化石, 800万年, or 保护动物 unless those words "
            "are already present in the topic or child/source material. "
            "Response model: WritingTopicAnalysis. "
            "Do not include any keys not shown. " + NO_GHOSTWRITE
        ),
    )
)

MATERIAL_QUESTIONS_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="material_questions",
        version=MATERIAL_QUESTIONS_VERSION,
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
            "If payload.scaffold.topic_type is person_portrait, ask from the child's point of view. "
            "Use 你, 自己, and child-observation wording. For self-portrait / 我的自画像, guide the "
            "child to answer as 我 and do not use 这个人, 他, or 她 as the question subject. "
            "For non-self portraits such as teacher, family, or classmate topics, ask what the child "
            "observed, remembered, or chose; 他/她 may appear only inside a child-observation question. "
            "Response model: MaterialQuestionsResult. "
            "Do not include any keys not shown. " + NO_GHOSTWRITE
        ),
    )
)

MATERIAL_CARD_GENERATION_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="material_card_generation",
        version=MATERIAL_CARD_VERSION,
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
            "text, at least one source_answer_ids item, and at least one source_refs item. "
            "Each source_refs item that uses child answer content must include answer_id from "
            "payload.answers[*].id. Empty or skipped child "
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
        version=WRITING_CASTLE_VERSION,
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

WRITING_TOPIC_IDEA_GENERATION_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="writing_topic_idea_generation",
        version=WRITING_TOPIC_IDEA_GENERATION_VERSION,
        system_prompt_key="wenlingo_primary_coach",
        system_prompt=PRIMARY_COACH_SYSTEM_PROMPT,
        response_contract=(
            "Return only this exact JSON object with no markdown: "
            '{"ideas":[{"id":"idea-1","title":"","topic_type":"",'
            '"topic_variant":"default","why_it_fits_child_interest":"",'
            '"practice_focus":"","child_safe_prompt":""},{"id":"idea-2",'
            '"title":"","topic_type":"","topic_variant":"default",'
            '"why_it_fits_child_interest":"","practice_focus":"",'
            '"child_safe_prompt":""},{"id":"idea-3","title":"",'
            '"topic_type":"","topic_variant":"default",'
            '"why_it_fits_child_interest":"","practice_focus":"",'
            '"child_safe_prompt":""}]}. Return exactly 3 ideas. '
            "Use only supported scaffold choices in payload.supported_choices. "
            "Use only allowed variants in payload.allowed_variants for each topic_type. "
            "Do not decide specific real event/person/ending/lesson/dialogue/feeling "
            "for the child. Suggest a safe topic direction and ask the child to choose "
            "or confirm their own material. No newline characters in any field. "
            "title <= 30 CJK characters or 60 total characters. "
            "child_safe_prompt <= 120 characters and asks the child to choose or "
            "confirm their own material. Response model: WritingTopicIdeasResult. "
            "Do not include extra keys. " + NO_GHOSTWRITE
        ),
    )
)
