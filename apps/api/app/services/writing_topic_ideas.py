from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import update
from sqlmodel import Session

from app.domain.models import Essay, StudentProfile, WritingTopicIdeaBatch, utcnow
from app.services.llm_contracts import WritingTopicIdeasResult
from app.services.writing_castle_scaffold import resolve_scaffold_snapshot
from app.services.writing_castle_state import (
    attach_scaffold_snapshot,
    init_material_card_state,
    init_outline_state,
)

AI_TOPIC_ORIGIN = "ai_topic_idea"
TEACHER_TOPIC_ORIGIN = "teacher_provided"
IDEA_BATCH_TTL_MINUTES = 30


def _as_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def allowed_topic_variants() -> dict[str, tuple[str, ...]]:
    return {
        "generic_narrative": ("default", "learned_skill"),
        "person_portrait": ("default", "self"),
        "imaginative_story": ("default", "invention_design"),
        "expository_introduction": ("default", "experiment_process"),
        "place_scenery": (
            "default",
            "my_paradise",
            "travel_writing",
            "scene_description",
            "place_recommendation",
        ),
        "animal_object_observation": (
            "default",
            "observation_diary",
            "plant_friend",
            "animal_friend",
            "beloved_object",
        ),
        "practical_writing": (
            "default",
            "diary",
            "letter",
            "proposal",
            "heartfelt_letter",
        ),
        "story_adaptation": ("default", "story_continuation", "story_rewrite"),
    }


def _supported_topic_types(supported_choices: list[dict[str, Any]]) -> set[str]:
    return {
        str(choice.get("topic_type") or "").strip()
        for choice in supported_choices
        if isinstance(choice, dict)
    }


def validate_writing_topic_ideas(
    output: WritingTopicIdeasResult,
    *,
    supported_choices: list[dict[str, Any]],
    allowed_variants: dict[str, tuple[str, ...]],
) -> None:
    supported_topic_types = _supported_topic_types(supported_choices)
    for idea in output.ideas:
        if idea.topic_type not in supported_topic_types:
            raise ValueError(f"unsupported topic_type: {idea.topic_type}")
        variants = allowed_variants.get(idea.topic_type, ())
        if idea.topic_variant not in variants:
            raise ValueError(
                f"unsupported topic_variant: {idea.topic_type}.{idea.topic_variant}"
            )
        resolve_scaffold_snapshot(
            idea.topic_type,
            idea.topic_variant,
            "ai_suggested",
        )


def create_idea_batch(
    session: Session,
    *,
    student: StudentProfile,
    ideas: WritingTopicIdeasResult,
    interest_text: str,
) -> WritingTopicIdeaBatch:
    batch = WritingTopicIdeaBatch(
        student_id=student.id,
        grade_label=student.grade_label,
        interest_input_present=bool(interest_text.strip()),
        ideas=[idea.model_dump() for idea in ideas.ideas],
        expires_at=utcnow() + timedelta(minutes=IDEA_BATCH_TTL_MINUTES),
    )
    session.add(batch)
    session.flush()
    return batch


def select_idea_from_batch(
    *,
    batch: WritingTopicIdeaBatch,
    selected_idea_id: str,
) -> dict[str, Any]:
    selected = next((idea for idea in batch.ideas if idea.get("id") == selected_idea_id), None)
    if selected is None:
        raise HTTPException(status_code=400, detail="selected idea is not in idea batch")
    return selected


def create_or_return_ai_topic_essay(
    session: Session,
    *,
    student: StudentProfile,
    batch: WritingTopicIdeaBatch,
    selected_idea_id: str,
) -> tuple[Essay, dict[str, Any], bool]:
    if batch.student_id != student.id:
        raise HTTPException(status_code=404, detail="idea batch not found")
    selected = select_idea_from_batch(batch=batch, selected_idea_id=selected_idea_id)
    if _as_utc_aware(batch.expires_at) <= utcnow():
        raise HTTPException(status_code=410, detail="idea batch expired")
    if batch.consumed_at is not None:
        if batch.selected_idea_id == selected_idea_id and batch.created_essay_id:
            essay = session.get(Essay, batch.created_essay_id)
            if essay is not None:
                return essay, selected, False
        raise HTTPException(status_code=409, detail="idea batch already consumed")

    reservation = session.exec(
        update(WritingTopicIdeaBatch)
        .where(WritingTopicIdeaBatch.id == batch.id)
        .where(WritingTopicIdeaBatch.consumed_at.is_(None))
        .values(consumed_at=utcnow(), selected_idea_id=selected_idea_id)
    )
    if reservation.rowcount != 1:
        session.refresh(batch)
        if batch.selected_idea_id == selected_idea_id and batch.created_essay_id:
            essay = session.get(Essay, batch.created_essay_id)
            if essay is not None:
                return essay, selected, False
        raise HTTPException(status_code=409, detail="idea batch already consumed")

    snapshot = resolve_scaffold_snapshot(
        selected["topic_type"],
        selected.get("topic_variant") or "default",
        "ai_suggested",
    )
    material = init_material_card_state()
    outline = init_outline_state()
    outline["topic_origin"] = AI_TOPIC_ORIGIN
    outline["selected_topic_idea"] = selected
    outline["topic_requirement"] = {
        "topic_text": selected["title"],
        "child_safe_prompt": selected.get("child_safe_prompt", ""),
        "source": AI_TOPIC_ORIGIN,
    }
    material, outline = attach_scaffold_snapshot(material, outline, snapshot)
    essay = Essay(
        student_id=student.id,
        title=selected["title"],
        status="prewriting_started",
        material_card=material,
        outline=outline,
    )
    session.add(essay)
    session.flush()
    batch.created_essay_id = essay.id
    session.add(batch)
    session.flush()
    return essay, selected, True
