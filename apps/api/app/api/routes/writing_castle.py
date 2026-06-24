from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.auth_deps import (
    ParentContext,
    require_auth_mode_state_change,
    require_essay_for_auth_mode,
    require_student_for_auth_mode,
)
from app.api.deps import AITaskRunner, get_ai_task_runner, get_db_session
from app.api.feedback_state import feedback_reaction_value
from app.api.routes.alpha import record_product_event
from app.core.config import Settings, get_settings
from app.domain.enums import TaskType
from app.domain.models import AbilityProfile, Essay, EssayVersion, StudentProfile
from app.services.abilities import apply_ability_delta
from app.services.ai_tasks import (
    essay_feedback,
    material_card_generation,
    material_questions,
    outline_generation,
    writing_topic_analysis,
)
from app.services.essay_workflow import draft_ability_deltas
from app.services.writing_castle_state import (
    MATERIALS_READY_STATUS,
    OUTLINE_READY_STATUS,
    PREWRITING_STARTED_STATUS,
    REVISION_REQUESTED_STATUS,
    SCHEMA_VERSION,
    SETTLED_ESSAY_STATUS,
    TOPIC_READY_STATUS,
    assert_prewriting_editable,
    confirm_material_cards,
    init_material_card_state,
    init_outline_state,
    merge_material_answers,
    merge_material_cards,
    merge_material_questions,
    merge_outline_sections,
    merge_topic_analysis,
    merge_topic_focus,
    next_status_after_materials,
    next_status_after_outline,
    next_status_after_topic,
    normalize_material_state,
    normalize_outline_state,
)

router = APIRouter(tags=["writing_castle"])
DAILY_LIMIT_ERROR_MESSAGES = {"daily limit exceeded", "daily limit reached"}
OPEN_PREWRITING_STATUSES = {
    PREWRITING_STARTED_STATUS,
    TOPIC_READY_STATUS,
    MATERIALS_READY_STATUS,
    OUTLINE_READY_STATUS,
}
CLOSED_PREWRITING_STATUSES = {
    REVISION_REQUESTED_STATUS,
    SETTLED_ESSAY_STATUS,
}


class ClassroomEssayCreate(BaseModel):
    topic_text: str = Field(min_length=1, max_length=300)


class EmptyGenerateRequest(BaseModel):
    regenerate: bool = False


class TopicFocusSave(BaseModel):
    text: str = Field(default="", max_length=120)
    adopted_from_ai: bool
    skipped: bool


class MaterialAnswerSave(BaseModel):
    answers: list[dict[str, Any]] = Field(default_factory=list)


class MaterialCardsSave(BaseModel):
    cards: list[dict[str, Any]] = Field(default_factory=list)


class OutlineSave(BaseModel):
    sections: list[dict[str, Any]] = Field(default_factory=list)
    skipped: bool


class FirstDraftSubmit(BaseModel):
    draft: str = Field(min_length=20, max_length=3000)


def _is_ai_feedback_failure(log) -> bool:
    return bool(
        log
        and log.validation_ok is False
        and log.error_message
        and log.error_message not in DAILY_LIMIT_ERROR_MESSAGES
    )


def _student_and_ability(session: Session, student_id: str) -> tuple[StudentProfile, AbilityProfile]:
    student = session.get(StudentProfile, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not student or not ability:
        raise HTTPException(status_code=404, detail="student not found")
    return student, ability


def _is_writing_castle_essay(essay: Essay) -> bool:
    if essay.status not in OPEN_PREWRITING_STATUSES | CLOSED_PREWRITING_STATUSES:
        return False
    return (
        essay.material_card.get("schema_version") == SCHEMA_VERSION
        and essay.outline.get("schema_version") == SCHEMA_VERSION
    )


def _prewriting_open(essay: Essay) -> None:
    if not _is_writing_castle_essay(essay):
        raise HTTPException(status_code=404, detail="writing castle essay not found")
    try:
        assert_prewriting_editable(essay.status)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if essay.status not in OPEN_PREWRITING_STATUSES:
        raise HTTPException(status_code=404, detail="writing castle essay not found")


def _record_event(
    session: Session,
    event_type: str,
    *,
    essay: Essay,
    student: StudentProfile,
    payload: dict[str, Any] | None = None,
) -> None:
    safe_payload = {"essay_id": essay.id}
    if payload:
        safe_payload.update(payload)
    try:
        record_product_event(
            session,
            event_type,
            parent_id=student.parent_id,
            student_id=student.id,
            payload=safe_payload,
        )
    except Exception:
        pass


def _essay_payload(essay: Essay) -> dict[str, Any]:
    return {
        "id": essay.id,
        "student_id": essay.student_id,
        "title": essay.title,
        "status": essay.status,
        "material_card": essay.material_card,
        "outline": essay.outline,
        "created_at": essay.created_at,
    }


def _save_step_response(
    session: Session,
    essay: Essay,
    key: str,
    value: Any,
) -> dict[str, Any]:
    session.add(essay)
    session.commit()
    return {"essay": _essay_payload(essay), key: value}


def _material_answer_source_ids(material: dict[str, Any]) -> list[str]:
    source_ids: list[str] = []
    for answer in normalize_material_state(material)["answers"]:
        source_id = str(answer.get("id") or "").strip()
        if not source_id:
            continue
        if answer.get("skipped") or not str(answer.get("text") or "").strip():
            continue
        source_ids.append(source_id)
    return source_ids


def _normalize_child_edited_cards(
    material: dict[str, Any],
    cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fallback_source_ids = _material_answer_source_ids(material)
    normalized_cards = []
    for card in cards:
        normalized = deepcopy(card)
        if (
            normalized.get("child_edited")
            and str(normalized.get("text") or "").strip()
            and normalized.get("placeholder")
        ):
            normalized["placeholder"] = False
            if not normalized.get("source_answer_ids"):
                normalized["source_answer_ids"] = fallback_source_ids[:3]
        normalized_cards.append(normalized)
    return normalized_cards


def _normalize_child_edited_outline_sections(
    outline: dict[str, Any],
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    previous_sections = {
        str(section.get("id") or ""): section
        for section in normalize_outline_state(outline)["sections"]
        if str(section.get("id") or "").strip()
    }
    normalized_sections = []
    for section in sections:
        normalized = deepcopy(section)
        note = str(normalized.get("note") or "").strip()
        if normalized.get("child_edited") and note:
            normalized["placeholder"] = False
            raw_source_card_ids = normalized.get("source_card_ids", [])
            if isinstance(raw_source_card_ids, list):
                has_malformed_source_id = any(
                    not isinstance(source_id, str) or not source_id.strip()
                    for source_id in raw_source_card_ids
                )
                if has_malformed_source_id:
                    normalized_sections.append(normalized)
                    continue
                source_card_ids = [
                    str(source_id).strip()
                    for source_id in raw_source_card_ids
                ]
                if source_card_ids:
                    normalized["source_card_ids"] = source_card_ids
                else:
                    previous = previous_sections.get(str(normalized.get("id") or ""))
                    previous_note = str(previous.get("note") or "").strip() if previous else ""
                    previous_source_ids = (
                        deepcopy(previous.get("source_card_ids", [])) if previous else []
                    )
                    normalized["source_card_ids"] = (
                        previous_source_ids if previous_note != note else []
                    )
        normalized_sections.append(normalized)
    return normalized_sections


def _retained_material_card_count(cards: list[dict[str, Any]]) -> int:
    return sum(1 for card in cards if not card.get("deleted") and not card.get("placeholder"))


@router.post(
    "/api/students/{student_id}/writing-castle/classroom",
    status_code=201,
)
async def create_classroom_writing_castle_essay(
    student_id: str,
    request: ClassroomEssayCreate,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    student = require_student_for_auth_mode(session, settings, context, student_id)
    topic_text = request.topic_text.strip()
    if not topic_text:
        raise HTTPException(status_code=422, detail="topic_text is required")
    essay = Essay(
        student_id=student.id,
        title=topic_text,
        status=PREWRITING_STARTED_STATUS,
        material_card=init_material_card_state(),
        outline=init_outline_state(),
    )
    session.add(essay)
    session.flush()
    _record_event(
        session,
        "writing_castle_started",
        essay=essay,
        student=student,
        payload={"step": "classroom"},
    )
    session.commit()
    return {"essay": _essay_payload(essay)}


@router.get("/api/students/{student_id}/writing-castle/classroom/active")
async def get_active_classroom_writing_castle_essay(
    student_id: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    student = require_student_for_auth_mode(session, settings, context, student_id)
    essays = session.exec(
        select(Essay)
        .where(Essay.student_id == student.id)
        .where(Essay.status.in_(OPEN_PREWRITING_STATUSES))
        .order_by(Essay.created_at.desc())
    ).all()
    essay = next((candidate for candidate in essays if _is_writing_castle_essay(candidate)), None)
    return {"essay": _essay_payload(essay) if essay else None}


@router.post("/api/essays/{essay_id}/topic-analysis")
async def generate_topic_analysis(
    essay_id: str,
    request: EmptyGenerateRequest,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _prewriting_open(essay)
    student, _ability = _student_and_ability(session, essay.student_id)
    outline = normalize_outline_state(essay.outline)
    topic_analysis = outline["topic_analysis"]
    if topic_analysis.get("status") == "generated" and not request.regenerate:
        essay.outline = outline
        return _save_step_response(session, essay, "topic_analysis", topic_analysis)
    focus = outline["child_topic_focus"]
    if focus.get("skipped") or str(focus.get("text") or "").strip():
        raise HTTPException(status_code=409, detail="topic focus already saved")

    result = await writing_topic_analysis(
        runner,
        essay.title,
        session=session,
        student_id=essay.student_id,
    )
    topic_analysis = result.output.model_dump()
    essay.outline = merge_topic_analysis(outline, topic_analysis["cards"])
    essay.outline["topic_analysis"]["suggested_focus"] = topic_analysis["suggested_focus"]
    essay.status = next_status_after_topic(essay.status)
    _record_event(
        session,
        "topic_analysis_completed",
        essay=essay,
        student=student,
        payload={"step": "topic_analysis"},
    )
    return _save_step_response(session, essay, "topic_analysis", essay.outline["topic_analysis"])


@router.patch("/api/essays/{essay_id}/topic-focus")
async def save_topic_focus(
    essay_id: str,
    request: TopicFocusSave,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _prewriting_open(essay)
    student, _ability = _student_and_ability(session, essay.student_id)
    essay.outline = merge_topic_focus(
        essay.outline,
        text=request.text,
        adopted_from_ai=request.adopted_from_ai,
        skipped=request.skipped,
    )
    essay.status = next_status_after_topic(essay.status)
    _record_event(
        session,
        "topic_focus_skipped" if request.skipped else "topic_focus_confirmed",
        essay=essay,
        student=student,
        payload={"step": "topic_focus", "skipped": request.skipped},
    )
    return _save_step_response(
        session,
        essay,
        "child_topic_focus",
        essay.outline["child_topic_focus"],
    )


@router.post("/api/essays/{essay_id}/material-questions")
async def generate_material_questions(
    essay_id: str,
    request: EmptyGenerateRequest,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _prewriting_open(essay)
    student, _ability = _student_and_ability(session, essay.student_id)
    material = normalize_material_state(essay.material_card)
    questions_status = material["step_state"].get("questions_status")
    if questions_status == "generated" and not request.regenerate:
        essay.material_card = material
        return _save_step_response(session, essay, "material_card", essay.material_card)
    if questions_status in {"skipped", "edited", "confirmed"}:
        raise HTTPException(status_code=409, detail="material questions already saved")
    if material.get("answers"):
        raise HTTPException(status_code=409, detail="material answers already saved")

    outline = normalize_outline_state(essay.outline)
    result = await material_questions(
        runner,
        essay.title,
        outline["child_topic_focus"].get("text", ""),
        session=session,
        student_id=essay.student_id,
    )
    essay.material_card = merge_material_questions(
        material,
        [question.model_dump() for question in result.output.questions],
    )
    essay.status = next_status_after_materials(essay.status)
    _record_event(
        session,
        "material_questions_completed",
        essay=essay,
        student=student,
        payload={"step": "material_questions"},
    )
    return _save_step_response(session, essay, "material_card", essay.material_card)


@router.patch("/api/essays/{essay_id}/material-answers")
async def save_material_answers(
    essay_id: str,
    request: MaterialAnswerSave,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _prewriting_open(essay)
    student, _ability = _student_and_ability(session, essay.student_id)
    essay.material_card = merge_material_answers(essay.material_card, answers=request.answers)
    essay.status = next_status_after_materials(essay.status)
    answered_count = sum(
        1
        for answer in request.answers
        if not answer.get("skipped") and str(answer.get("text") or "").strip()
    )
    if answered_count == 0:
        essay.material_card["step_state"]["questions_status"] = "skipped"
    _record_event(
        session,
        "material_questions_skipped" if answered_count == 0 else "material_question_answered",
        essay=essay,
        student=student,
        payload={
            "step": "material_answers",
            "answered_count": answered_count,
            "skipped": answered_count == 0,
        },
    )
    return _save_step_response(session, essay, "material_card", essay.material_card)


@router.post("/api/essays/{essay_id}/material-cards")
async def generate_material_cards(
    essay_id: str,
    request: EmptyGenerateRequest,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _prewriting_open(essay)
    student, _ability = _student_and_ability(session, essay.student_id)
    material = normalize_material_state(essay.material_card)
    cards_status = material["step_state"].get("cards_status")
    if cards_status == "generated" and not request.regenerate:
        essay.material_card = material
        return _save_step_response(session, essay, "material_card", essay.material_card)
    if cards_status in {"edited", "confirmed"}:
        raise HTTPException(status_code=409, detail="material cards already saved")

    result = await material_card_generation(
        runner,
        material["answers"],
        session=session,
        student_id=essay.student_id,
    )
    cards = []
    for order, card in enumerate(result.output.cards, start=1):
        cards.append(
            {
                **card.model_dump(),
                "order": order,
                "deleted": False,
                "child_edited": False,
            }
        )
    try:
        essay.material_card = merge_material_cards(material, cards, status="generated")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    essay.status = next_status_after_materials(essay.status)
    _record_event(
        session,
        "material_cards_generated",
        essay=essay,
        student=student,
        payload={
            "step": "material_cards",
            "card_count": len(cards),
        },
    )
    return _save_step_response(session, essay, "material_card", essay.material_card)


@router.patch("/api/essays/{essay_id}/material-cards")
async def save_material_cards(
    essay_id: str,
    request: MaterialCardsSave,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _prewriting_open(essay)
    student, _ability = _student_and_ability(session, essay.student_id)
    cards = _normalize_child_edited_cards(essay.material_card, request.cards)
    try:
        essay.material_card = confirm_material_cards(essay.material_card, cards)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    essay.status = next_status_after_materials(essay.status)
    _record_event(
        session,
        "material_cards_confirmed",
        essay=essay,
        student=student,
        payload={
            "step": "material_cards",
            "card_count": _retained_material_card_count(cards),
        },
    )
    return _save_step_response(session, essay, "material_card", essay.material_card)


@router.post("/api/essays/{essay_id}/outline")
async def generate_outline(
    essay_id: str,
    request: EmptyGenerateRequest,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _prewriting_open(essay)
    student, _ability = _student_and_ability(session, essay.student_id)
    outline = normalize_outline_state(essay.outline)
    outline_status = outline["step_state"].get("outline_status")
    if outline_status == "generated" and not request.regenerate:
        essay.outline = outline
        return _save_step_response(session, essay, "outline", essay.outline)
    if outline_status in {"skipped", "edited", "confirmed"}:
        raise HTTPException(status_code=409, detail="outline already saved")

    material = normalize_material_state(essay.material_card)
    result = await outline_generation(
        runner,
        material["cards"],
        session=session,
        student_id=essay.student_id,
    )
    sections = [
        {**section.model_dump(), "child_edited": False}
        for section in result.output.sections
    ]
    try:
        essay.outline = merge_outline_sections(
            outline,
            material,
            sections,
            status="generated",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    essay.status = next_status_after_outline(essay.status)
    _record_event(
        session,
        "outline_generated",
        essay=essay,
        student=student,
        payload={
            "step": "outline",
            "outline_section_count": len(sections),
        },
    )
    return _save_step_response(session, essay, "outline", essay.outline)


@router.patch("/api/essays/{essay_id}/outline")
async def save_outline(
    essay_id: str,
    request: OutlineSave,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _prewriting_open(essay)
    student, _ability = _student_and_ability(session, essay.student_id)
    if request.skipped:
        outline = normalize_outline_state(essay.outline)
        outline["sections"] = []
        outline["step_state"]["outline_status"] = "skipped"
        essay.outline = outline
    else:
        try:
            sections = _normalize_child_edited_outline_sections(essay.outline, request.sections)
            essay.outline = merge_outline_sections(
                essay.outline,
                essay.material_card,
                sections,
                status="confirmed",
                allow_child_edited_without_sources=True,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    essay.status = next_status_after_outline(essay.status)
    _record_event(
        session,
        "outline_skipped" if request.skipped else "outline_confirmed",
        essay=essay,
        student=student,
        payload={
            "step": "outline",
            "outline_section_count": len(essay.outline["sections"]),
            "skipped": request.skipped,
        },
    )
    return _save_step_response(session, essay, "outline", essay.outline)


@router.post(
    "/api/essays/{essay_id}/first-draft",
    status_code=201,
)
async def submit_first_draft(
    essay_id: str,
    request: FirstDraftSubmit,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _prewriting_open(essay)
    existing_first_draft = session.exec(
        select(EssayVersion).where(
            EssayVersion.essay_id == essay_id,
            EssayVersion.version_label == "first_draft",
        )
    ).first()
    if existing_first_draft:
        raise HTTPException(status_code=409, detail="first draft already submitted")

    student, ability = _student_and_ability(session, essay.student_id)
    try:
        feedback_result = await essay_feedback(
            runner,
            essay.title,
            request.draft,
            session=session,
            prompt_version=settings.llm_prompt_version,
            student_id=essay.student_id,
        )
        feedback = feedback_result.output
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        try:
            record_product_event(
                session,
                "ai_feedback_failed",
                parent_id=student.parent_id,
                student_id=student.id,
                payload={"task_type": "essay", "error_category": "exception"},
            )
            session.commit()
        except Exception:
            session.rollback()
        raise
    if _is_ai_feedback_failure(feedback_result.log):
        try:
            record_product_event(
                session,
                "ai_feedback_failed",
                parent_id=student.parent_id,
                student_id=student.id,
                payload={"task_type": "essay", "error_category": "exception"},
            )
        except Exception:
            pass

    essay.status = REVISION_REQUESTED_STATUS
    version = EssayVersion(
        essay_id=essay.id,
        version_label="first_draft",
        content=request.draft,
        ai_feedback=feedback.model_dump(),
        llm_call_log_id=feedback_result.log.id if feedback_result.log else None,
    )
    session.add(essay)
    session.add(version)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="first draft already submitted") from exc
    _record_event(
        session,
        "prewriting_first_draft_submitted",
        essay=essay,
        student=student,
        payload={"step": "first_draft"},
    )
    apply_ability_delta(
        session,
        ability,
        draft_ability_deltas(len(feedback.improvements)),
        TaskType.essay,
        version.id,
    )
    session.add(ability)
    essay_payload = _essay_payload(essay)
    version_payload = version.model_dump()
    version_payload["reaction"] = feedback_reaction_value(
        session,
        student.id,
        "essay_draft",
        version.id,
    )
    session.commit()
    return {"essay": essay_payload, "first_draft": version_payload, "feedback": feedback}
