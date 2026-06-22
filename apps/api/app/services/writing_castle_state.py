from copy import deepcopy
from datetime import timezone
from typing import Any

from app.domain.models import utcnow

SCHEMA_VERSION = "v0.6a.1"

PREWRITING_STARTED_STATUS = "prewriting_started"
TOPIC_READY_STATUS = "topic_ready"
MATERIALS_READY_STATUS = "materials_ready"
OUTLINE_READY_STATUS = "outline_ready"
REVISION_REQUESTED_STATUS = "revision_requested"
SETTLED_ESSAY_STATUS = "settled"

MATERIAL_CARD_CATEGORIES = ("event", "detail", "feeling_takeaway")
OUTLINE_SLOTS = ("cause", "process", "result", "reflection")


def _now_iso() -> str:
    return utcnow().astimezone(timezone.utc).isoformat()


def init_material_card_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "questions": [],
        "answers": [],
        "cards": [],
        "step_state": {
            "questions_status": "not_started",
            "cards_status": "not_started",
        },
    }


def init_outline_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "topic_analysis": {"cards": [], "status": "not_started"},
        "child_topic_focus": {
            "text": "",
            "adopted_from_ai": False,
            "skipped": False,
            "updated_at": "",
        },
        "sections": [],
        "step_state": {"outline_status": "not_started"},
    }


def normalize_material_state(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value or value.get("schema_version") != SCHEMA_VERSION:
        return init_material_card_state()
    normalized = init_material_card_state()
    normalized.update(deepcopy(value))
    normalized["step_state"] = {
        **init_material_card_state()["step_state"],
        **value.get("step_state", {}),
    }
    return normalized


def normalize_outline_state(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value or value.get("schema_version") != SCHEMA_VERSION:
        return init_outline_state()
    normalized = init_outline_state()
    normalized.update(deepcopy(value))
    normalized["topic_analysis"] = {
        **init_outline_state()["topic_analysis"],
        **value.get("topic_analysis", {}),
    }
    normalized["child_topic_focus"] = {
        **init_outline_state()["child_topic_focus"],
        **value.get("child_topic_focus", {}),
    }
    normalized["step_state"] = {
        **init_outline_state()["step_state"],
        **value.get("step_state", {}),
    }
    return normalized


def assert_prewriting_editable(status: str) -> None:
    if status in {REVISION_REQUESTED_STATUS, SETTLED_ESSAY_STATUS}:
        raise ValueError("prewriting is closed")


def next_status_after_topic(status: str) -> str:
    assert_prewriting_editable(status)
    return TOPIC_READY_STATUS


def next_status_after_materials(status: str) -> str:
    assert_prewriting_editable(status)
    return MATERIALS_READY_STATUS


def next_status_after_outline(status: str) -> str:
    assert_prewriting_editable(status)
    return OUTLINE_READY_STATUS


def merge_topic_analysis(outline: dict[str, Any], cards: list[dict[str, Any]]) -> dict[str, Any]:
    updated = normalize_outline_state(outline)
    updated["topic_analysis"] = {"cards": deepcopy(cards), "status": "generated"}
    return updated


def merge_topic_focus(
    outline: dict[str, Any],
    *,
    text: str,
    adopted_from_ai: bool,
    skipped: bool,
) -> dict[str, Any]:
    updated = normalize_outline_state(outline)
    updated["child_topic_focus"] = {
        "text": text.strip(),
        "adopted_from_ai": adopted_from_ai,
        "skipped": skipped,
        "updated_at": _now_iso(),
    }
    return updated


def merge_material_questions(
    material: dict[str, Any],
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    updated = normalize_material_state(material)
    updated["questions"] = deepcopy(questions)
    updated["step_state"]["questions_status"] = "generated"
    return updated


def merge_material_answers(
    material: dict[str, Any],
    *,
    answers: list[dict[str, Any]],
) -> dict[str, Any]:
    updated = normalize_material_state(material)
    updated["answers"] = [
        {**deepcopy(answer), "updated_at": answer.get("updated_at") or _now_iso()}
        for answer in answers
    ]
    skipped_count = sum(1 for answer in updated["answers"] if answer.get("skipped"))
    updated["step_state"]["questions_status"] = (
        "skipped" if skipped_count == len(updated["answers"]) else "answered"
    )
    return updated


def validate_card_sources(
    material: dict[str, Any],
    cards: list[dict[str, Any]],
) -> None:
    answer_ids = {answer["id"] for answer in normalize_material_state(material)["answers"]}
    if not answer_ids:
        return
    unknown = sorted(
        {
            source_id
            for card in cards
            for source_id in card.get("source_answer_ids", [])
            if source_id not in answer_ids
        }
    )
    if unknown:
        raise ValueError(f"unknown source_answer_ids: {', '.join(unknown)}")


def merge_material_cards(
    material: dict[str, Any],
    cards: list[dict[str, Any]],
    *,
    status: str = "generated",
) -> dict[str, Any]:
    updated = normalize_material_state(material)
    validate_card_sources(updated, cards)
    updated["cards"] = deepcopy(cards)
    updated["step_state"]["cards_status"] = status
    return updated


def confirm_material_cards(material: dict[str, Any], cards: list[dict[str, Any]]) -> dict[str, Any]:
    return merge_material_cards(material, cards, status="confirmed")


def validate_outline_sources(
    material: dict[str, Any],
    sections: list[dict[str, Any]],
) -> None:
    card_ids = {
        card["id"]
        for card in normalize_material_state(material)["cards"]
        if not card.get("deleted") and not card.get("placeholder")
    }
    unknown = sorted(
        {
            source_id
            for section in sections
            for source_id in section.get("source_card_ids", [])
            if source_id not in card_ids
        }
    )
    if unknown:
        raise ValueError(f"unknown source_card_ids: {', '.join(unknown)}")


def merge_outline_sections(
    outline: dict[str, Any],
    material: dict[str, Any],
    sections: list[dict[str, Any]],
    *,
    status: str = "generated",
) -> dict[str, Any]:
    validate_outline_sources(material, sections)
    updated = normalize_outline_state(outline)
    updated["sections"] = deepcopy(sections)
    updated["step_state"]["outline_status"] = status
    return updated
