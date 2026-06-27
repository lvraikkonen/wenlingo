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


def _valid_scaffold_entries(scaffold: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(scaffold, dict):
        return []
    entries = scaffold.get(key) or []
    if not isinstance(entries, list):
        return []

    valid_entries = []
    saw_malformed = False
    for entry in entries:
        if not isinstance(entry, dict) or _source_id(entry.get("id")) is None:
            saw_malformed = True
            continue
        valid_entries.append(entry)

    if valid_entries and saw_malformed:
        raise ValueError(f"malformed scaffold {key}")
    return valid_entries


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


def _usable_answers(answers: list[dict]) -> list[tuple[dict, str]]:
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
    return usable_answers


def _usable_cards(cards: list[dict]) -> list[tuple[dict, str]]:
    usable_cards = []
    for card in cards:
        source_id = _source_id(card.get("id"))
        if (
            card.get("deleted")
            or card.get("placeholder")
            or source_id is None
            or not _clean_text(card.get("text"), 80)
        ):
            continue
        usable_cards.append((card, source_id))
    return usable_cards


def _source_refs_for_answer(answer: dict, scaffold: dict[str, Any], slot: dict[str, Any]) -> list[dict[str, Any]]:
    existing_refs = answer.get("source_refs")
    if isinstance(existing_refs, list):
        reusable_refs = [ref for ref in existing_refs[:3] if isinstance(ref, dict)]
        if reusable_refs:
            return reusable_refs

    answer_id = _source_id(answer.get("id"))
    if answer_id is None:
        return []

    cleaned_text = _clean_text(answer.get("text"), 120)
    topic_type = scaffold.get("topic_type")
    if topic_type == "imaginative_story":
        return [{"source_type": "imagined_setting", "answer_id": answer_id}]
    if topic_type == "expository_introduction":
        return [
            {
                "source_type": "child_confirmed",
                "confirmation_id": answer_id,
                "confirmed_text": cleaned_text,
            }
        ]
    if topic_type == "person_portrait":
        return [{"source_type": "observation", "answer_id": answer_id}]
    return [{"source_type": "real_experience", "answer_id": answer_id}]


def _card_from_slot(
    slot: dict[str, Any],
    answer_source: tuple[dict, str] | None,
    order: int,
    scaffold: dict[str, Any],
) -> dict:
    slot_id = str(slot.get("id") or f"slot-{order}")
    if answer_source is None:
        return {
            "id": f"card-{slot_id}",
            "category": slot_id,
            "text": "",
            "source_answer_ids": [],
            "source_refs": [],
            "placeholder": True,
        }
    answer, source_id = answer_source
    return {
        "id": f"card-{slot_id}",
        "category": slot_id,
        "text": _clean_text(answer.get("text"), 120),
        "source_answer_ids": [source_id],
        "source_refs": _source_refs_for_answer(answer, scaffold, slot),
        "placeholder": False,
    }


def _section_from_scaffold(
    section: dict[str, Any],
    card_source: tuple[dict, str] | None,
) -> dict:
    section_id = str(section.get("id") or "section")
    heading = _clean_text(section.get("heading") or section.get("label") or "段落", 12)
    if section.get("content_kind") == "structural" or card_source is None:
        return {
            "id": f"outline-{section_id}",
            "slot": section_id,
            "heading": heading,
            "note": "",
            "source_card_ids": [],
            "placeholder": True,
        }
    card, source_id = card_source
    return {
        "id": f"outline-{section_id}",
        "slot": section_id,
        "heading": heading,
        "note": _clean_text(card.get("text"), 80),
        "source_card_ids": [source_id],
        "placeholder": False,
    }


def _legacy_fallback_material_questions() -> MaterialQuestionsResult:
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


def fallback_material_questions(scaffold: dict[str, Any] | None = None) -> MaterialQuestionsResult:
    slots = _valid_scaffold_entries(scaffold, "material_slots")
    if not slots:
        return _legacy_fallback_material_questions()
    return MaterialQuestionsResult(
        questions=[
            {
                "id": f"q-{slot['id']}",
                "text": f"{_clean_text(slot.get('label'), 48)}可以怎么写？",
                "hint": "写孩子自己知道、观察到或确认的内容。",
                "order": order,
            }
            for order, slot in enumerate(slots[:3], start=1)
            if slot.get("id")
        ],
        encouragement="先把自己的素材说清楚。",
    )


def _legacy_fallback_material_cards(answers: list[dict]) -> MaterialCardsResult:
    usable_answers = _usable_answers(answers)
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


def fallback_material_cards(
    answers: list[dict],
    scaffold: dict[str, Any] | None = None,
) -> MaterialCardsResult:
    slots = _valid_scaffold_entries(scaffold, "material_slots")
    if not slots:
        return _legacy_fallback_material_cards(answers)

    usable_answers = _usable_answers(answers)
    return MaterialCardsResult(
        cards=[
            _card_from_slot(
                slot,
                usable_answers[index] if index < len(usable_answers) else None,
                index + 1,
                scaffold or {},
            )
            for index, slot in enumerate(slots[:8])
            if slot.get("id")
        ],
        encouragement="先把自己的素材收好。",
    )


def _legacy_fallback_outline(cards: list[dict]) -> WritingOutlineResult:
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


def fallback_outline(
    cards: list[dict],
    scaffold: dict[str, Any] | None = None,
) -> WritingOutlineResult:
    sections = _valid_scaffold_entries(scaffold, "outline_sections")
    if not sections:
        return _legacy_fallback_outline(cards)

    usable_cards = _usable_cards(cards)
    content_card_index = 0
    outline_sections = []
    for section in sections[:6]:
        if not section.get("id"):
            continue
        card_source = None
        if section.get("content_kind") != "structural" and content_card_index < len(usable_cards):
            card_source = usable_cards[content_card_index]
            content_card_index += 1
        outline_sections.append(_section_from_scaffold(section, card_source))

    return WritingOutlineResult(
        sections=outline_sections,
        tip="每一段只抓一个真实重点。",
    )
