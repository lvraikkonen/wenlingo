import re
from typing import Any

from app.services.llm_contracts import (
    MaterialCardsResult,
    MaterialQuestionsResult,
    WritingOutlineResult,
    WritingTopicAnalysis,
)


def _clean_text(value: Any, max_length: int) -> str:
    text = re.sub(r"</?[^>]+>", "", str(value or "")).strip()
    return text[:max_length]


def _source_id(value: Any) -> str | None:
    if value is None:
        return None
    source_id = str(value)
    if not source_id.strip():
        return None
    return source_id


def fallback_topic_analysis(topic_text: str) -> WritingTopicAnalysis:
    topic = _clean_text(topic_text, 24) or "这件事"
    return WritingTopicAnalysis(
        cards=[
            {
                "id": "topic-question",
                "kind": "topic_question",
                "title": "题目在问什么",
                "body": f"围绕“{topic}”，写一次真实经历和变化。",
                "required_points": [],
            },
            {
                "id": "must-include",
                "kind": "must_include",
                "title": "一定要写到什么",
                "body": "写清起因、经过、结果和自己的变化。",
                "required_points": ["起因", "经过", "结果"],
            },
            {
                "id": "shine-point",
                "kind": "shine_point",
                "title": "可以写精彩处",
                "body": "选择一个动作、声音或心情，把画面写具体。",
                "required_points": [],
            },
        ],
        suggested_focus=f"先写清楚“{topic}”里最重要的一个过程。",
    )


def fallback_material_questions() -> MaterialQuestionsResult:
    return MaterialQuestionsResult(
        questions=[
            {
                "id": "q1",
                "text": "这件事是怎么开始的？",
                "hint": "写真实发生的时间、地点或起因。",
                "order": 1,
            },
            {
                "id": "q2",
                "text": "过程中哪个动作或画面最清楚？",
                "hint": "可以写看到、听到、做到的一处细节。",
                "order": 2,
            },
            {
                "id": "q3",
                "text": "这件事之后你有什么感受或收获？",
                "hint": "只写自己的真实感受，不用总结大道理。",
                "order": 3,
            },
        ],
        encouragement="先回答真实发生的细节。",
    )


def fallback_material_cards(answers: list[dict]) -> MaterialCardsResult:
    usable_answers = []
    for answer in answers:
        source_id = _source_id(answer.get("id"))
        if (
            answer.get("skipped")
            or source_id is None
            or not _clean_text(answer.get("text"), 120)
        ):
            continue
        usable_answers.append((answer, source_id))

    slots = [
        ("card-event", "event"),
        ("card-detail", "detail"),
        ("card-feeling", "feeling_takeaway"),
    ]
    cards = []
    for index, (card_id, category) in enumerate(slots):
        if index < len(usable_answers):
            answer, source_id = usable_answers[index]
            cards.append(
                {
                    "id": card_id,
                    "category": category,
                    "text": _clean_text(answer.get("text"), 120),
                    "source_answer_ids": [source_id],
                    "placeholder": False,
                }
            )
            continue
        cards.append(
            {
                "id": card_id,
                "category": category,
                "text": "",
                "source_answer_ids": [],
                "placeholder": True,
            }
        )
    return MaterialCardsResult(cards=cards, encouragement="先把真实素材收好。")


def fallback_outline(cards: list[dict]) -> WritingOutlineResult:
    valid_cards_by_category = {}
    for card in cards:
        category = card.get("category")
        source_id = _source_id(card.get("id"))
        if (
            category not in {"event", "detail", "feeling_takeaway"}
            or card.get("deleted")
            or card.get("placeholder")
            or source_id is None
            or not _clean_text(card.get("text"), 80)
        ):
            continue
        valid_cards_by_category.setdefault(category, (card, source_id))

    def section(
        section_id: str,
        slot: str,
        heading: str,
        category: str | None,
    ) -> dict:
        card_source = valid_cards_by_category.get(category or "")
        if card_source is None:
            return {
                "id": section_id,
                "slot": slot,
                "heading": heading,
                "note": "",
                "source_card_ids": [],
                "placeholder": True,
            }
        card, source_id = card_source
        return {
            "id": section_id,
            "slot": slot,
            "heading": heading,
            "note": _clean_text(card.get("text"), 80),
            "source_card_ids": [source_id],
            "placeholder": False,
        }

    return WritingOutlineResult(
        sections=[
            section("outline-cause", "cause", "起因", "event"),
            section("outline-process", "process", "经过", "detail"),
            section("outline-result", "result", "结果", None),
            section("outline-reflection", "reflection", "感受", "feeling_takeaway"),
        ],
        tip="每一段只抓一个真实重点。",
    )
