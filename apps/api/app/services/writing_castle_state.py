from copy import deepcopy
from datetime import timezone
from typing import Any

from app.domain.models import utcnow
from app.services.writing_castle_scaffold import SCHEMA_VERSION as CURRENT_SCHEMA_VERSION
from app.services.writing_castle_sources import (
    normalize_source_refs,
    validate_expository_fact_sources,
    validate_slot_level_source_policy,
)

LEGACY_SCHEMA_VERSION = "v0.6a.1"
SCHEMA_VERSION = CURRENT_SCHEMA_VERSION

PREWRITING_STARTED_STATUS = "prewriting_started"
TOPIC_READY_STATUS = "topic_ready"
MATERIALS_READY_STATUS = "materials_ready"
OUTLINE_READY_STATUS = "outline_ready"
REVISION_REQUESTED_STATUS = "revision_requested"
SETTLED_ESSAY_STATUS = "settled"

MATERIAL_CARD_CATEGORIES = ("event", "detail", "feeling_takeaway")
OUTLINE_SLOTS = ("cause", "process", "result", "reflection")
_PREWRITING_STATUS_RANK = {
    PREWRITING_STARTED_STATUS: 0,
    TOPIC_READY_STATUS: 1,
    MATERIALS_READY_STATUS: 2,
    OUTLINE_READY_STATUS: 3,
}


def _now_iso() -> str:
    return utcnow().astimezone(timezone.utc).isoformat()


def _is_supported_schema(value: dict[str, Any] | None) -> bool:
    return isinstance(value, dict) and value.get("schema_version") in {
        LEGACY_SCHEMA_VERSION,
        SCHEMA_VERSION,
    }


def _is_legacy_schema(value: dict[str, Any] | None) -> bool:
    return isinstance(value, dict) and value.get("schema_version") == LEGACY_SCHEMA_VERSION


def init_material_card_state(*, schema_version: str = SCHEMA_VERSION) -> dict[str, Any]:
    state = {
        "schema_version": schema_version,
        "questions": [],
        "answers": [],
        "cards": [],
        "step_state": {
            "questions_status": "not_started",
            "cards_status": "not_started",
        },
    }
    if schema_version == SCHEMA_VERSION:
        state["scaffold_ref"] = None
    return state


def init_outline_state(*, schema_version: str = SCHEMA_VERSION) -> dict[str, Any]:
    state = {
        "schema_version": schema_version,
        "topic_origin": "teacher_provided",
        "selected_topic_idea": None,
        "topic_requirement": {},
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
    if schema_version == SCHEMA_VERSION:
        state["scaffold"] = None
    return state


def normalize_material_state(value: dict[str, Any] | None) -> dict[str, Any]:
    if not _is_supported_schema(value):
        return init_material_card_state()
    schema_version = value["schema_version"]
    normalized = init_material_card_state(schema_version=schema_version)
    normalized.update(deepcopy(value))
    normalized["step_state"] = {
        **init_material_card_state(schema_version=schema_version)["step_state"],
        **deepcopy(value.get("step_state", {})),
    }
    if schema_version == SCHEMA_VERSION:
        normalized["scaffold_ref"] = deepcopy(value.get("scaffold_ref"))
    return normalized


def normalize_outline_state(value: dict[str, Any] | None) -> dict[str, Any]:
    if not _is_supported_schema(value):
        return init_outline_state()
    schema_version = value["schema_version"]
    normalized = init_outline_state(schema_version=schema_version)
    normalized.update(deepcopy(value))
    normalized["topic_analysis"] = {
        **init_outline_state(schema_version=schema_version)["topic_analysis"],
        **deepcopy(value.get("topic_analysis", {})),
    }
    normalized["child_topic_focus"] = {
        **init_outline_state(schema_version=schema_version)["child_topic_focus"],
        **deepcopy(value.get("child_topic_focus", {})),
    }
    normalized["step_state"] = {
        **init_outline_state(schema_version=schema_version)["step_state"],
        **deepcopy(value.get("step_state", {})),
    }
    if schema_version == SCHEMA_VERSION:
        normalized["scaffold"] = deepcopy(value.get("scaffold"))
    return normalized


def _scaffold_ref(snapshot: dict[str, Any]) -> dict[str, str]:
    return {
        "topic_type": snapshot["topic_type"],
        "topic_variant": snapshot["topic_variant"],
        "scaffold_template_version": snapshot["scaffold_template_version"],
    }


def _validate_scaffold_slot_list(snapshot: dict[str, Any], key: str) -> None:
    entries = snapshot.get(key)
    if entries is None:
        return
    if not isinstance(entries, list):
        raise ValueError(f"malformed scaffold {key}")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"malformed scaffold {key}")
        slot_id = entry.get("id")
        if slot_id is None or not str(slot_id).strip():
            raise ValueError(f"malformed scaffold {key}")


def _validate_scaffold_slot_shape(snapshot: dict[str, Any]) -> None:
    _validate_scaffold_slot_list(snapshot, "material_slots")
    _validate_scaffold_slot_list(snapshot, "outline_sections")


def attach_scaffold_snapshot(
    material: dict[str, Any],
    outline: dict[str, Any],
    snapshot: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated_material = normalize_material_state(material)
    updated_outline = normalize_outline_state(outline)
    if updated_material.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("cannot attach v0.6b scaffold to legacy material state")
    if updated_outline.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("cannot attach v0.6b scaffold to legacy outline state")
    updated_material["scaffold_ref"] = _scaffold_ref(snapshot)
    updated_material.pop("scaffold", None)
    updated_outline["scaffold"] = deepcopy(snapshot)
    return updated_material, updated_outline


def has_resolved_scaffold(material: dict[str, Any], outline: dict[str, Any]) -> bool:
    return bool(
        isinstance(material, dict)
        and isinstance(outline, dict)
        and material.get("schema_version") == SCHEMA_VERSION
        and outline.get("schema_version") == SCHEMA_VERSION
        and isinstance(material.get("scaffold_ref"), dict)
        and isinstance(outline.get("scaffold"), dict)
    )


def resolve_essay_scaffold(essay: Any) -> dict[str, Any] | None:
    material = normalize_material_state(getattr(essay, "material_card", None))
    outline = normalize_outline_state(getattr(essay, "outline", None))
    if _is_legacy_schema(material) and _is_legacy_schema(outline):
        return None
    snapshot = outline.get("scaffold")
    ref = material.get("scaffold_ref")
    if not isinstance(snapshot, dict) or not isinstance(ref, dict):
        raise ValueError("resolved scaffold is required")
    expected = _scaffold_ref(snapshot)
    if ref != expected:
        raise ValueError("scaffold_ref mismatch")
    _validate_scaffold_slot_shape(snapshot)
    return deepcopy(snapshot)


def assert_prewriting_editable(status: str) -> None:
    if status in {REVISION_REQUESTED_STATUS, SETTLED_ESSAY_STATUS}:
        raise ValueError("prewriting is closed")


def _advance_prewriting_status(status: str, target_status: str) -> str:
    current_rank = _PREWRITING_STATUS_RANK.get(status, -1)
    target_rank = _PREWRITING_STATUS_RANK[target_status]
    return status if current_rank >= target_rank else target_status


def next_status_after_topic(status: str) -> str:
    assert_prewriting_editable(status)
    return _advance_prewriting_status(status, TOPIC_READY_STATUS)


def next_status_after_materials(status: str) -> str:
    assert_prewriting_editable(status)
    return _advance_prewriting_status(status, MATERIALS_READY_STATUS)


def next_status_after_outline(status: str) -> str:
    assert_prewriting_editable(status)
    return _advance_prewriting_status(status, OUTLINE_READY_STATUS)


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
    if not updated["answers"]:
        updated["step_state"]["questions_status"] = "not_started"
    else:
        updated["step_state"]["questions_status"] = (
            "skipped" if skipped_count == len(updated["answers"]) else "answered"
        )
    return updated


def _card_source_refs(card: dict[str, Any], *, require_v06b_source_refs: bool) -> list[dict[str, Any]]:
    if isinstance(card.get("source_refs"), list):
        return normalize_source_refs(card.get("source_refs"))
    if require_v06b_source_refs:
        raise ValueError("v0.6b material cards require source_refs")
    return [
        {"source_type": "real_experience", "answer_id": source_id}
        for source_id in card.get("source_answer_ids", [])
    ]


def _material_slot_content_kinds(
    material: dict[str, Any],
    scaffold: dict[str, Any] | None,
) -> dict[str, str]:
    if not isinstance(scaffold, dict):
        return {}
    ref = material.get("scaffold_ref")
    if isinstance(ref, dict) and _scaffold_ref(scaffold) != ref:
        raise ValueError("scaffold_ref mismatch")
    return {
        str(slot.get("id")): str(slot.get("content_kind") or "")
        for slot in scaffold.get("material_slots", [])
        if isinstance(slot, dict) and str(slot.get("id") or "").strip()
    }


def _cards_with_normalized_source_refs(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_cards = []
    for card in cards:
        normalized = deepcopy(card)
        if isinstance(normalized.get("source_refs"), list):
            normalized["source_refs"] = normalize_source_refs(normalized["source_refs"])
        normalized_cards.append(normalized)
    return normalized_cards


def validate_card_sources(
    material: dict[str, Any],
    cards: list[dict[str, Any]],
    *,
    scaffold: dict[str, Any] | None = None,
) -> None:
    normalized_material = normalize_material_state(material)
    require_v06b_source_refs = normalized_material.get("schema_version") == SCHEMA_VERSION
    content_kinds = _material_slot_content_kinds(normalized_material, scaffold)
    answer_ids = {
        answer["id"]
        for answer in normalized_material["answers"]
        if not answer.get("skipped")
        and str(answer.get("id") or "").strip()
        and str(answer.get("text") or "").strip()
    }
    source_ref_answer_ids: set[str] = set()
    for card in cards:
        source_answer_ids = card.get("source_answer_ids", [])
        raw_source_refs = card.get("source_refs")
        card_text = str(card.get("text") or "")
        if card.get("placeholder") and not card_text.strip() and not source_answer_ids and raw_source_refs is None:
            refs = []
        else:
            refs = _card_source_refs(card, require_v06b_source_refs=require_v06b_source_refs)
        if not card.get("placeholder") and not refs and require_v06b_source_refs:
            raise ValueError("v0.6b material cards require source_refs")
        if not card.get("placeholder") and not source_answer_ids and not refs:
            raise ValueError("non-placeholder material cards require source refs")
        if (
            card.get("placeholder")
            and card_text.strip()
            and not source_answer_ids
            and not refs
        ):
            raise ValueError("placeholder material cards without sources cannot contain story content")
        category = str(card.get("category") or "")
        if (
            not card.get("placeholder")
            and require_v06b_source_refs
            and content_kinds
            and category not in content_kinds
        ):
            raise ValueError(f"unknown material card category: {category}")
        if not card.get("placeholder") and isinstance(scaffold, dict):
            validate_slot_level_source_policy(
                topic_type=str(scaffold.get("topic_type") or ""),
                slot_id=category,
                source_refs=refs,
            )
        if (
            not card.get("placeholder")
            and content_kinds.get(category) == "factual"
        ):
            validate_expository_fact_sources(card_text, refs)
        source_ref_answer_ids.update(
            str(ref.get("answer_id") or "").strip()
            for ref in refs
            if "answer_id" in ref and str(ref.get("answer_id") or "").strip()
        )
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
    unknown_source_ref_answer_ids = sorted(
        source_id for source_id in source_ref_answer_ids if source_id not in answer_ids
    )
    if unknown_source_ref_answer_ids:
        raise ValueError(f"unknown source_ref answer_ids: {', '.join(unknown_source_ref_answer_ids)}")


def merge_material_cards(
    material: dict[str, Any],
    cards: list[dict[str, Any]],
    *,
    status: str = "generated",
    scaffold: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = normalize_material_state(material)
    validate_card_sources(updated, cards, scaffold=scaffold)
    updated["cards"] = _cards_with_normalized_source_refs(cards)
    updated["step_state"]["cards_status"] = status
    return updated


def confirm_material_cards(
    material: dict[str, Any],
    cards: list[dict[str, Any]],
    *,
    scaffold: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return merge_material_cards(material, cards, status="confirmed", scaffold=scaffold)


def validate_outline_sources(
    material: dict[str, Any],
    sections: list[dict[str, Any]],
    *,
    allow_child_edited_without_sources: bool = False,
) -> None:
    card_ids = {
        card["id"]
        for card in normalize_material_state(material)["cards"]
        if not card.get("deleted") and not card.get("placeholder")
    }
    source_card_ids_by_section: list[list[str]] = []
    for section in sections:
        source_card_ids = section.get("source_card_ids", [])
        if not isinstance(source_card_ids, list):
            raise ValueError("source_card_ids must be a list of strings")
        normalized_source_card_ids = []
        for source_id in source_card_ids:
            if not isinstance(source_id, str) or not source_id.strip():
                raise ValueError("source_card_ids must be a list of strings")
            normalized_source_card_ids.append(source_id.strip())
        source_card_ids_by_section.append(normalized_source_card_ids)
        raw_note = section.get("note", "")
        if raw_note is None:
            note = ""
        elif not isinstance(raw_note, str):
            raise ValueError("note must be a string")
        else:
            note = raw_note
        child_edited_without_sources_allowed = (
            allow_child_edited_without_sources
            and section.get("child_edited")
            and not normalized_source_card_ids
        )
        if (
            not section.get("placeholder")
            and note.strip()
            and not normalized_source_card_ids
            and not child_edited_without_sources_allowed
        ):
            raise ValueError("story-specific outline sections require source_card_ids")
    unknown = sorted(
        {
            source_id
            for source_card_ids in source_card_ids_by_section
            for source_id in source_card_ids
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
    allow_child_edited_without_sources: bool = False,
) -> dict[str, Any]:
    validate_outline_sources(
        material,
        sections,
        allow_child_edited_without_sources=allow_child_edited_without_sources,
    )
    updated = normalize_outline_state(outline)
    updated["sections"] = deepcopy(sections)
    updated["step_state"]["outline_status"] = status
    return updated
