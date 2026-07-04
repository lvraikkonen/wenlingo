import asyncio
from copy import deepcopy
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from app.api.auth_deps import (
    ParentContext,
    require_auth_mode_state_change,
    require_essay_for_auth_mode,
    require_student_for_auth_mode,
)
from app.api.deps import (
    AITaskRunner,
    SessionFactory,
    get_ai_task_runner,
    get_db_session,
    get_session_factory,
)
from app.api.routes.alpha import record_product_event
from app.core.config import Settings, get_settings
from app.domain.models import (
    AbilityProfile,
    Essay,
    EssayFeedbackSubmission,
    EssayVersion,
    PrewritingAIJob,
    StudentProfile,
    WritingTopicIdeaBatch,
    new_uuid,
    utcnow,
)
from app.services.ai_tasks import (
    essay_feedback,
    material_card_generation,
    material_questions,
    outline_generation,
    writing_topic_idea_generation,
    writing_topic_analysis,
)
from app.services.essay_feedback_persistence import save_prewriting_first_draft_feedback_result
from app.services.essay_feedback_streaming import (
    EssayFeedbackDailyLimitReached,
    active_submission_json_response,
    build_prewriting_first_draft_feedback_stream,
    reserve_submission_daily_limit_if_needed,
)
from app.services.essay_feedback_submission import (
    IdempotencyPayloadMismatch,
    SubmissionAlreadyTerminal,
    begin_submission_result_save,
    build_submission_payload_hash,
    create_or_get_submission,
    finalize_submission_with_reservation,
    idempotency_scope_for,
    mark_submission_status,
)
from app.services.prewriting_jobs import (
    PREWRITING_JOB_RESULT_REF_TYPE,
    acquire_job_lease,
    complete_job,
    create_or_get_prewriting_job,
    fail_job,
    heartbeat_job,
    next_progress_snapshot,
)
from app.services.streaming_events import format_sse_event
from app.services.writing_castle_state import (
    LEGACY_SCHEMA_VERSION,
    MATERIALS_READY_STATUS,
    OUTLINE_READY_STATUS,
    PREWRITING_STARTED_STATUS,
    REVISION_REQUESTED_STATUS,
    SCHEMA_VERSION,
    SETTLED_ESSAY_STATUS,
    TOPIC_READY_STATUS,
    assert_prewriting_editable,
    attach_scaffold_snapshot,
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
    resolve_essay_scaffold,
)
from app.services.writing_castle_scaffold import (
    FUTURE_TOPIC_TYPES,
    detect_unsupported_future_type,
    resolve_scaffold_snapshot,
    supported_topic_type_choices,
)
from app.services.writing_topic_ideas import (
    allowed_topic_variants,
    create_idea_batch,
    create_or_return_ai_topic_essay,
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


class AiTopicIdeasCreate(BaseModel):
    interest_text: str = Field(default="", max_length=120)


class AiTopicEssayCreate(BaseModel):
    idea_batch_id: str = Field(min_length=1, max_length=120)
    selected_idea_id: str = Field(min_length=1, max_length=40)


OverrideReason = Literal["manual_choice", "suggestion_accepted", "fallback_selected"]


class ScaffoldSelectionSave(BaseModel):
    topic_type: str = Field(min_length=1, max_length=80)
    topic_variant: str | None = Field(default=None, max_length=80)
    accepted_suggestion_id: str | None = Field(default=None, max_length=120)
    override_reason: OverrideReason | None = "manual_choice"
    unsupported_future_type: str | None = Field(default=None, max_length=80)

    @field_validator("unsupported_future_type")
    @classmethod
    def validate_unsupported_future_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in FUTURE_TOPIC_TYPES:
            raise ValueError("unsupported_future_type must be a known future topic type")
        return value


class EmptyGenerateRequest(BaseModel):
    regenerate: bool = False


class PrewritingJobCreate(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=120)


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
    client_submission_id: str = Field(min_length=1, max_length=120)


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
    supported_schema_versions = {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}
    material_schema_version = essay.material_card.get("schema_version")
    outline_schema_version = essay.outline.get("schema_version")
    return (
        material_schema_version == outline_schema_version
        and material_schema_version in supported_schema_versions
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


def _daily_limit_reached_http_exception(exc: EssayFeedbackDailyLimitReached) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={"code": "DAILY_LIMIT_REACHED", "message": str(exc)},
    )


def _release_submission_after_failed_json(
    *,
    session: Session,
    submission_id: str | None,
    error_code: str,
    error_message: str,
    llm_call_log_id: str | None = None,
) -> None:
    if submission_id is None:
        return
    try:
        finalize_submission_with_reservation(
            session=session,
            submission_id=submission_id,
            terminal_status="failed_released",
            saved_result=False,
            essay_version_id=None,
            result_fetch_url="",
            llm_call_log_id=llm_call_log_id,
            error_code=error_code,
            error_message=error_message,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise


def _existing_feedback_submission_for_payload(
    *,
    session: Session,
    essay: Essay,
    route_scope: str,
    client_submission_id: str,
    payload: dict[str, Any],
) -> EssayFeedbackSubmission | None:
    submission = session.exec(
        select(EssayFeedbackSubmission).where(
            EssayFeedbackSubmission.idempotency_scope
            == idempotency_scope_for(essay.student_id, essay.id),
            EssayFeedbackSubmission.task_name == "essay_feedback",
            EssayFeedbackSubmission.client_submission_id == client_submission_id,
        )
    ).first()
    if submission is None:
        return None
    payload_hash = build_submission_payload_hash(
        task_name="essay_feedback",
        route_scope=route_scope,
        payload_schema_version="v0.6e.1",
        payload=payload,
    )
    if submission.payload_hash != payload_hash:
        raise IdempotencyPayloadMismatch
    return submission


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
    safe_payload["server_completed_at"] = utcnow().isoformat()
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


def _record_writing_castle_product_event(
    session: Session,
    event_type: str,
    *,
    student: StudentProfile,
    essay_id: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    safe_payload = {"server_completed_at": utcnow().isoformat()}
    if essay_id:
        safe_payload["essay_id"] = essay_id
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


def _scaffold_event_payload(scaffold: dict[str, Any] | None) -> dict[str, Any]:
    if not scaffold:
        return {"scaffold_schema": "legacy_v0.6a"}
    return {
        "topic_type": scaffold["topic_type"],
        "topic_variant": scaffold["topic_variant"],
        "scaffold_template_version": scaffold["scaffold_template_version"],
        "selection_source": scaffold.get("selection_source", ""),
    }


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


def _essay_topic_text(essay: Essay) -> str:
    outline = normalize_outline_state(essay.outline)
    requirement = outline.get("topic_requirement") or {}
    return (
        str(requirement.get("topic_text") or "")
        or str(getattr(essay, "title", "") or "")
        or str(getattr(essay, "prompt", "") or "")
    )


def _resolved_scaffold_or_legacy(essay: Essay) -> dict[str, Any] | None:
    try:
        return resolve_essay_scaffold(essay)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _scaffold_selection_source(override_reason: OverrideReason | None) -> str:
    if override_reason == "suggestion_accepted":
        return "ai_suggested"
    if override_reason == "fallback_selected":
        return "fallback"
    return "manual"


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
    material_state = normalize_material_state(material)
    is_v06b = material_state.get("schema_version") == SCHEMA_VERSION
    previous_cards = {
        str(card.get("id") or ""): card
        for card in material_state["cards"]
        if str(card.get("id") or "").strip()
    }
    fallback_source_ids = _material_answer_source_ids(material)
    normalized_cards = []
    for card in cards:
        normalized = deepcopy(card)
        text = str(normalized.get("text") or "").strip()
        previous = previous_cards.get(str(normalized.get("id") or ""))
        previous_was_placeholder = bool(previous and previous.get("placeholder"))
        needs_child_source_ref = (
            normalized.get("placeholder")
            or previous_was_placeholder
            or not normalized.get("source_refs")
        )
        if normalized.get("child_edited") and text and needs_child_source_ref:
            normalized["placeholder"] = False
            if not normalized.get("source_answer_ids"):
                normalized["source_answer_ids"] = fallback_source_ids[:3]
            if not normalized.get("source_refs"):
                if is_v06b:
                    normalized["source_refs"] = [
                        {
                            "source_type": "child_confirmed",
                            "confirmation_id": str(normalized.get("id") or "child-edited-card"),
                            "confirmed_text": text,
                        }
                    ]
                else:
                    normalized["source_refs"] = [
                        {"source_type": "real_experience", "answer_id": source_id}
                        for source_id in normalized["source_answer_ids"]
                    ]
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


def _material_card_generation_result_cards(result) -> list[dict[str, Any]]:
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
    return cards


def _outline_generation_result_sections(result) -> list[dict[str, Any]]:
    return [
        {**section.model_dump(), "child_edited": False}
        for section in result.output.sections
    ]


def _prepare_material_card_generation_inputs(
    *,
    essay: Essay,
    regenerate: bool = False,
) -> dict[str, Any]:
    _prewriting_open(essay)
    scaffold = _resolved_scaffold_or_legacy(essay)
    material = normalize_material_state(essay.material_card)
    cards_status = material["step_state"].get("cards_status")
    if cards_status == "generated" and not regenerate:
        return {
            "already_done": True,
            "student_id": essay.student_id,
            "material": material,
            "scaffold": deepcopy(scaffold),
        }
    if cards_status in {"edited", "confirmed"}:
        raise HTTPException(status_code=409, detail="material cards already saved")
    return {
        "already_done": False,
        "student_id": essay.student_id,
        "answers": deepcopy(material["answers"]),
        "scaffold": deepcopy(scaffold),
    }


def _prepare_outline_generation_inputs(
    *,
    essay: Essay,
    regenerate: bool = False,
) -> dict[str, Any]:
    _prewriting_open(essay)
    scaffold = _resolved_scaffold_or_legacy(essay)
    outline = normalize_outline_state(essay.outline)
    outline_status = outline["step_state"].get("outline_status")
    if outline_status == "generated" and not regenerate:
        return {
            "already_done": True,
            "student_id": essay.student_id,
            "outline": outline,
            "scaffold": deepcopy(scaffold),
        }
    if outline_status in {"skipped", "edited", "confirmed"}:
        raise HTTPException(status_code=409, detail="outline already saved")
    material = normalize_material_state(essay.material_card)
    return {
        "already_done": False,
        "student_id": essay.student_id,
        "cards": deepcopy(material["cards"]),
        "scaffold": deepcopy(scaffold),
    }


def _save_material_card_generation_result(
    *,
    session: Session,
    essay: Essay,
    cards: list[dict[str, Any]],
    scaffold: dict[str, Any] | None,
    regenerate: bool = False,
) -> str:
    student, _ability = _student_and_ability(session, essay.student_id)
    material = normalize_material_state(essay.material_card)
    cards_status = material["step_state"].get("cards_status")
    if cards_status == "generated" and not regenerate:
        essay.material_card = material
        session.add(essay)
        session.flush()
        return essay.id
    if cards_status in {"edited", "confirmed"}:
        raise HTTPException(status_code=409, detail="material cards already saved")
    try:
        essay.material_card = merge_material_cards(
            material,
            cards,
            status="generated",
            scaffold=scaffold,
        )
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
            **_scaffold_event_payload(scaffold),
            "card_count": len(cards),
        },
    )
    session.add(essay)
    session.flush()
    return essay.id


def _save_outline_generation_result(
    *,
    session: Session,
    essay: Essay,
    sections: list[dict[str, Any]],
    scaffold: dict[str, Any] | None,
    regenerate: bool = False,
) -> str:
    student, _ability = _student_and_ability(session, essay.student_id)
    outline = normalize_outline_state(essay.outline)
    outline_status = outline["step_state"].get("outline_status")
    if outline_status == "generated" and not regenerate:
        essay.outline = outline
        session.add(essay)
        session.flush()
        return essay.id
    if outline_status in {"skipped", "edited", "confirmed"}:
        raise HTTPException(status_code=409, detail="outline already saved")
    material = normalize_material_state(essay.material_card)
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
            **_scaffold_event_payload(scaffold),
            "outline_section_count": len(sections),
        },
    )
    session.add(essay)
    session.flush()
    return essay.id


async def execute_material_card_generation(
    *,
    session: Session,
    essay: Essay,
    runner: AITaskRunner,
    settings: Settings,
    regenerate: bool = False,
) -> str:
    """Save complete validated material cards and return result_ref_id."""
    _ = settings
    inputs = _prepare_material_card_generation_inputs(essay=essay, regenerate=regenerate)
    if inputs["already_done"]:
        essay.material_card = inputs["material"]
        session.add(essay)
        session.flush()
        return essay.id

    result = await material_card_generation(
        runner,
        inputs["answers"],
        session=session,
        student_id=inputs["student_id"],
        scaffold=inputs["scaffold"],
    )
    return _save_material_card_generation_result(
        session=session,
        essay=essay,
        cards=_material_card_generation_result_cards(result),
        scaffold=inputs["scaffold"],
        regenerate=regenerate,
    )


async def execute_outline_generation(
    *,
    session: Session,
    essay: Essay,
    runner: AITaskRunner,
    settings: Settings,
    regenerate: bool = False,
) -> str:
    """Save complete validated outline and return result_ref_id."""
    _ = settings
    inputs = _prepare_outline_generation_inputs(essay=essay, regenerate=regenerate)
    if inputs["already_done"]:
        essay.outline = inputs["outline"]
        session.add(essay)
        session.flush()
        return essay.id

    result = await outline_generation(
        runner,
        inputs["cards"],
        session=session,
        student_id=inputs["student_id"],
        scaffold=inputs["scaffold"],
    )
    return _save_outline_generation_result(
        session=session,
        essay=essay,
        sections=_outline_generation_result_sections(result),
        scaffold=inputs["scaffold"],
        regenerate=regenerate,
    )


def _prewriting_job_response(job: PrewritingAIJob) -> dict[str, Any]:
    return {
        "schema_version": job.schema_version,
        "job_id": job.id,
        "task_name": job.task_name,
        "status": job.status,
        "stage": job.stage,
        "seq": job.progress_event_seq,
        "result_ref_type": job.result_ref_type,
        "result_ref_id": job.result_ref_id,
        "error_code": job.error_code,
        "error_message": job.error_message,
    }


def _prewriting_job_event_snapshot(job: PrewritingAIJob) -> dict[str, Any]:
    return {
        "schema_version": job.schema_version,
        "event_id": f"evt_{new_uuid()}",
        "seq": job.progress_event_seq,
        "job_id": job.id,
        "task_name": job.task_name,
        "stage": job.stage,
        "status": job.status,
        "result_ref_type": job.result_ref_type,
        "result_ref_id": job.result_ref_id,
    }


def _prewriting_job_event_name(job: PrewritingAIJob) -> str:
    if job.status in {"completed", "failed"}:
        return job.status
    return "progress"


def _require_prewriting_job_for_auth(
    *,
    session: Session,
    settings: Settings,
    context: ParentContext | None,
    job_id: str,
) -> PrewritingAIJob:
    job = session.get(PrewritingAIJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="prewriting job not found")
    require_essay_for_auth_mode(session, settings, context, job.essay_id)
    return job


async def _mark_prewriting_job_failed(
    *,
    session_factory: SessionFactory,
    job_id: str,
    error_code: str,
    error_message: str,
    llm_call_log_id: str | None = None,
) -> None:
    with session_factory() as session:
        fail_job(
            session=session,
            job_id=job_id,
            error_code=error_code,
            error_message=error_message,
            llm_call_log_id=llm_call_log_id,
        )


async def _run_prewriting_job(
    *,
    session_factory: SessionFactory,
    job_id: str,
    essay_id: str,
    task_name: str,
    worker_id: str,
    runner: AITaskRunner,
    settings: Settings,
) -> None:
    llm_call_log_id: str | None = None
    result_ref_id: str | None = None
    try:
        with session_factory() as session:
            heartbeat = heartbeat_job(session=session, job_id=job_id, worker_id=worker_id)
            if heartbeat is None:
                return
        with session_factory() as session:
            next_progress_snapshot(
                session=session,
                job_id=job_id,
                stage="primary_started",
                status="running",
            )
        with session_factory() as session:
            job = session.get(PrewritingAIJob, job_id)
            if job is None or job.status != "running" or job.locked_by != worker_id:
                return
            essay = session.get(Essay, essay_id)
            if essay is None:
                raise ValueError("writing castle essay not found")
            if task_name == "material_card_generation":
                inputs = _prepare_material_card_generation_inputs(essay=essay)
            elif task_name == "outline_generation":
                inputs = _prepare_outline_generation_inputs(essay=essay)
            else:
                raise ValueError("unsupported prewriting job task")
            if inputs["already_done"]:
                result_ref_id = essay.id

        if result_ref_id is None:
            with session_factory() as session:
                if task_name == "material_card_generation":
                    result = await material_card_generation(
                        runner,
                        inputs["answers"],
                        session=session,
                        student_id=inputs["student_id"],
                        scaffold=inputs["scaffold"],
                    )
                    complete_result = _material_card_generation_result_cards(result)
                else:
                    result = await outline_generation(
                        runner,
                        inputs["cards"],
                        session=session,
                        student_id=inputs["student_id"],
                        scaffold=inputs["scaffold"],
                    )
                    complete_result = _outline_generation_result_sections(result)
                log = getattr(result, "log", None)
                llm_call_log_id = log.id if log is not None else None
                session.commit()
            with session_factory() as session:
                job = session.get(PrewritingAIJob, job_id)
                if job is None or job.status != "running" or job.locked_by != worker_id:
                    return
                essay = session.get(Essay, essay_id)
                if essay is None:
                    raise ValueError("writing castle essay not found")
                _prewriting_open(essay)
                if task_name == "material_card_generation":
                    result_ref_id = _save_material_card_generation_result(
                        session=session,
                        essay=essay,
                        cards=complete_result,
                        scaffold=inputs["scaffold"],
                    )
                else:
                    result_ref_id = _save_outline_generation_result(
                        session=session,
                        essay=essay,
                        sections=complete_result,
                        scaffold=inputs["scaffold"],
                    )
                session.commit()

        with session_factory() as session:
            complete_job(
                session=session,
                job_id=job_id,
                result_ref_type=PREWRITING_JOB_RESULT_REF_TYPE,
                result_ref_id=result_ref_id,
                llm_call_log_id=llm_call_log_id,
            )
    except HTTPException as exc:
        await _mark_prewriting_job_failed(
            session_factory=session_factory,
            job_id=job_id,
            error_code=f"HTTP_{exc.status_code}",
            error_message=str(exc.detail),
            llm_call_log_id=llm_call_log_id,
        )
    except Exception as exc:
        await _mark_prewriting_job_failed(
            session_factory=session_factory,
            job_id=job_id,
            error_code="PREWRITING_JOB_FAILED",
            error_message=str(exc),
            llm_call_log_id=llm_call_log_id,
        )


def _schedule_prewriting_job(
    *,
    job: PrewritingAIJob,
    worker_id: str,
    session_factory: SessionFactory,
    runner: AITaskRunner,
    settings: Settings,
) -> None:
    asyncio.create_task(
        _run_prewriting_job(
            session_factory=session_factory,
            job_id=job.id,
            essay_id=job.essay_id,
            task_name=job.task_name,
            worker_id=worker_id,
            runner=runner,
            settings=settings,
        )
    )


async def _create_prewriting_job(
    *,
    essay_id: str,
    task_name: str,
    payload: PrewritingJobCreate,
    session: Session,
    session_factory: SessionFactory,
    runner: AITaskRunner,
    settings: Settings,
    context: ParentContext | None,
) -> JSONResponse:
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _prewriting_open(essay)
    job = create_or_get_prewriting_job(
        session=session,
        student_id=essay.student_id,
        essay_id=essay.id,
        task_name=task_name,
        idempotency_key=payload.idempotency_key,
    )
    worker_id = f"worker_{new_uuid()}"
    leased_job = acquire_job_lease(session=session, job_id=job.id, worker_id=worker_id)
    if leased_job is not None:
        job = leased_job
        _schedule_prewriting_job(
            job=job,
            worker_id=worker_id,
            session_factory=session_factory,
            runner=runner,
            settings=settings,
        )
    return JSONResponse(status_code=202, content=_prewriting_job_response(job))


@router.post("/api/essays/{essay_id}/material-cards/jobs", status_code=202)
async def create_material_card_generation_job(
    essay_id: str,
    payload: PrewritingJobCreate,
    session: Session = Depends(get_db_session),
    session_factory: SessionFactory = Depends(get_session_factory),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    return await _create_prewriting_job(
        essay_id=essay_id,
        task_name="material_card_generation",
        payload=payload,
        session=session,
        session_factory=session_factory,
        runner=runner,
        settings=settings,
        context=context,
    )


@router.post("/api/essays/{essay_id}/outline/jobs", status_code=202)
async def create_outline_generation_job(
    essay_id: str,
    payload: PrewritingJobCreate,
    session: Session = Depends(get_db_session),
    session_factory: SessionFactory = Depends(get_session_factory),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    return await _create_prewriting_job(
        essay_id=essay_id,
        task_name="outline_generation",
        payload=payload,
        session=session,
        session_factory=session_factory,
        runner=runner,
        settings=settings,
        context=context,
    )


@router.get("/api/prewriting/jobs/{job_id}")
async def get_prewriting_job(
    job_id: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    job = _require_prewriting_job_for_auth(
        session=session,
        settings=settings,
        context=context,
        job_id=job_id,
    )
    return _prewriting_job_response(job)


@router.get("/api/prewriting/jobs/{job_id}/events")
async def stream_prewriting_job_events(
    job_id: str,
    request: Request,
    session_factory: SessionFactory = Depends(get_session_factory),
    settings: Settings = Depends(get_settings),
):
    with session_factory() as session:
        context = require_auth_mode_state_change(request, db=session, settings=settings)
        _require_prewriting_job_for_auth(
            session=session,
            settings=settings,
            context=context,
            job_id=job_id,
        )

    async def event_stream():
        last_seq: int | None = None
        last_status = ""
        last_stage = ""
        while True:
            if await request.is_disconnected():
                break
            with session_factory() as session:
                job = session.get(PrewritingAIJob, job_id)
                if job is None:
                    break
                snapshot = _prewriting_job_event_snapshot(job)
                should_emit = (
                    last_seq is None
                    or snapshot["seq"] != last_seq
                    or snapshot["status"] != last_status
                    or snapshot["stage"] != last_stage
                )
                if should_emit:
                    yield format_sse_event(_prewriting_job_event_name(job), snapshot)
                    last_seq = snapshot["seq"]
                    last_status = snapshot["status"]
                    last_stage = snapshot["stage"]
                if job.status in {"completed", "failed"}:
                    break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    unsupported_future_type = detect_unsupported_future_type(topic_text)
    return {
        "essay": _essay_payload(essay),
        "supported_topic_types": supported_topic_type_choices(),
        "unsupported_future_type": unsupported_future_type,
    }


@router.post("/api/students/{student_id}/writing-castle/ai-topic-ideas", status_code=201)
async def generate_ai_topic_ideas(
    student_id: str,
    request: AiTopicIdeasCreate,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    student = require_student_for_auth_mode(session, settings, context, student_id)
    supported_choices = supported_topic_type_choices()
    variants = allowed_topic_variants()
    _record_writing_castle_product_event(
        session,
        "ai_topic_ideas_requested",
        student=student,
        payload={
            "interest_input_present": bool(request.interest_text.strip()),
            "grade_label": student.grade_label,
        },
    )
    session.commit()
    try:
        result = await writing_topic_idea_generation(
            runner,
            grade_label=student.grade_label,
            interest_text=request.interest_text,
            supported_choices=supported_choices,
            allowed_variants=variants,
            session=session,
            student_id=student.id,
        )
    except RuntimeError as exc:
        session.commit()
        raise HTTPException(status_code=503, detail="ai topic ideas unavailable") from exc
    batch = create_idea_batch(
        session,
        student=student,
        ideas=result.output,
        interest_text=request.interest_text,
    )
    _record_writing_castle_product_event(
        session,
        "ai_topic_ideas_generated",
        student=student,
        payload={
            "idea_batch_id": batch.id,
            "interest_input_present": batch.interest_input_present,
            "grade_label": student.grade_label,
            "idea_count": len(batch.ideas),
        },
    )
    session.commit()
    return {
        "idea_batch_id": batch.id,
        "ideas": batch.ideas,
        "expires_at": batch.expires_at,
    }


@router.post("/api/students/{student_id}/writing-castle/ai-topic-essay")
async def create_ai_topic_essay(
    student_id: str,
    request: AiTopicEssayCreate,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    student = require_student_for_auth_mode(session, settings, context, student_id)
    batch = session.get(WritingTopicIdeaBatch, request.idea_batch_id)
    if batch is None or batch.student_id != student.id:
        raise HTTPException(status_code=404, detail="idea batch not found")
    essay, selected_idea, created = create_or_return_ai_topic_essay(
        session,
        student=student,
        batch=batch,
        selected_idea_id=request.selected_idea_id,
    )
    _record_event(
        session,
        "ai_topic_idea_selected",
        essay=essay,
        student=student,
        payload={
            **_scaffold_event_payload(essay.outline["scaffold"]),
            "idea_batch_id": batch.id,
            "selected_idea_id": request.selected_idea_id,
            "topic_type": selected_idea["topic_type"],
            "topic_variant": selected_idea.get("topic_variant") or "default",
            "topic_origin": "ai_topic_idea",
        },
    )
    session.commit()
    return JSONResponse(
        status_code=201 if created else 200,
        content=jsonable_encoder({"essay": _essay_payload(essay)}),
    )


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
    if (
        essay
        and essay.material_card.get("schema_version") == SCHEMA_VERSION
        and essay.outline.get("schema_version") == SCHEMA_VERSION
        and (
            essay.material_card.get("scaffold_ref") is not None
            or essay.outline.get("scaffold") is not None
        )
    ):
        _resolved_scaffold_or_legacy(essay)
    return {"essay": _essay_payload(essay) if essay else None}


@router.patch("/api/essays/{essay_id}/scaffold-selection")
async def save_scaffold_selection(
    essay_id: str,
    request: ScaffoldSelectionSave,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _prewriting_open(essay)
    student, _ability = _student_and_ability(session, essay.student_id)
    outline = normalize_outline_state(essay.outline)
    material = normalize_material_state(essay.material_card)
    if (
        outline["topic_analysis"].get("status") == "generated"
        or material.get("answers")
        or material.get("cards")
        or outline.get("sections")
    ):
        raise HTTPException(
            status_code=409,
            detail="scaffold cannot change after prewriting content exists",
        )
    try:
        snapshot = resolve_scaffold_snapshot(
            request.topic_type,
            request.topic_variant,
            _scaffold_selection_source(request.override_reason),
        )
        detected_future_type = detect_unsupported_future_type(_essay_topic_text(essay))
        unsupported_future_type = detected_future_type or request.unsupported_future_type
        if unsupported_future_type:
            snapshot["unsupported_future_type"] = unsupported_future_type
            snapshot["unsupported_override"] = True
        essay.material_card, essay.outline = attach_scaffold_snapshot(material, outline, snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _record_event(
        session,
        "scaffold_selected",
        essay=essay,
        student=student,
        payload={
            "step": "scaffold_selection",
            **_scaffold_event_payload(snapshot),
            "override_reason": request.override_reason or "manual_choice",
            "accepted_suggestion_id": request.accepted_suggestion_id or "",
            "unsupported_future_type": snapshot.get("unsupported_future_type", ""),
            "unsupported_override": bool(snapshot.get("unsupported_override")),
        },
    )
    return _save_step_response(session, essay, "scaffold", snapshot)


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
    scaffold = _resolved_scaffold_or_legacy(essay)
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
        scaffold=scaffold,
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
        payload={"step": "topic_analysis", **_scaffold_event_payload(scaffold)},
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
    scaffold = _resolved_scaffold_or_legacy(essay)
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
        scaffold=scaffold,
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
        payload={"step": "material_questions", **_scaffold_event_payload(scaffold)},
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
    scaffold = _resolved_scaffold_or_legacy(essay)
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
            **_scaffold_event_payload(scaffold),
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
    await execute_material_card_generation(
        session=session,
        essay=essay,
        runner=runner,
        settings=settings,
        regenerate=request.regenerate,
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
    scaffold = _resolved_scaffold_or_legacy(essay)
    student, _ability = _student_and_ability(session, essay.student_id)
    cards = _normalize_child_edited_cards(essay.material_card, request.cards)
    try:
        essay.material_card = confirm_material_cards(essay.material_card, cards, scaffold=scaffold)
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
            **_scaffold_event_payload(scaffold),
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
    await execute_outline_generation(
        session=session,
        essay=essay,
        runner=runner,
        settings=settings,
        regenerate=request.regenerate,
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
    scaffold = _resolved_scaffold_or_legacy(essay)
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
            **_scaffold_event_payload(scaffold),
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
    student, _ability = _student_and_ability(session, essay.student_id)
    try:
        submission = _existing_feedback_submission_for_payload(
            session=session,
            essay=essay,
            route_scope="prewriting_first_draft",
            client_submission_id=request.client_submission_id,
            payload=request.model_dump(),
        )
    except IdempotencyPayloadMismatch as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_PAYLOAD_MISMATCH"},
        ) from exc
    if submission is not None:
        try:
            active_response = active_submission_json_response(submission)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if active_response is not None and active_response["status"] == "IN_PROGRESS":
            return JSONResponse(status_code=202, content=active_response)
        if active_response is not None:
            return JSONResponse(status_code=200, content=active_response)

    _prewriting_open(essay)
    existing_first_draft = session.exec(
        select(EssayVersion).where(
            EssayVersion.essay_id == essay_id,
            EssayVersion.version_label == "first_draft",
        )
    ).first()
    if existing_first_draft:
        raise HTTPException(status_code=409, detail="first draft already submitted")

    if submission is None:
        try:
            submission = create_or_get_submission(
                session=session,
                student_id=essay.student_id,
                essay_id=essay.id,
                task_name="essay_feedback",
                route_scope="prewriting_first_draft",
                client_submission_id=request.client_submission_id,
                payload=request.model_dump(),
            )
        except IdempotencyPayloadMismatch as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_PAYLOAD_MISMATCH"},
            ) from exc
    try:
        reserve_submission_daily_limit_if_needed(
            session=session,
            settings=settings,
            student_id=essay.student_id,
            submission=submission,
        )
    except EssayFeedbackDailyLimitReached as exc:
        session.rollback()
        raise _daily_limit_reached_http_exception(exc) from exc
    if submission.status == "created":
        submission = mark_submission_status(
            session=session,
            submission_id=submission.id,
            status="reserved",
        )
    if submission.status == "reserved":
        submission = mark_submission_status(
            session=session,
            submission_id=submission.id,
            status="streaming_started",
        )
    session.commit()
    try:
        feedback_result = await essay_feedback(
            runner,
            essay.title,
            request.draft,
            session=session,
            prompt_version=settings.llm_prompt_version,
            student_id=essay.student_id,
            daily_limit_reservation_owner="submission_ledger",
        )
        feedback = feedback_result.output
    except IdempotencyPayloadMismatch as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_PAYLOAD_MISMATCH"},
        ) from exc
    except ValueError as exc:
        session.rollback()
        _release_submission_after_failed_json(
            session=session,
            submission_id=submission.id if submission is not None else None,
            error_code="ESSAY_FEEDBACK_VALUE_ERROR",
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        _release_submission_after_failed_json(
            session=session,
            submission_id=submission.id if submission is not None else None,
            error_code="ESSAY_FEEDBACK_PROVIDER_ERROR",
            error_message="essay feedback provider failed",
        )
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

    try:
        if submission is not None:
            begin_submission_result_save(
                session=session,
                submission_id=submission.id,
            )
        response_payload = save_prewriting_first_draft_feedback_result(
            session=session,
            essay=essay,
            draft=request.draft,
            feedback=feedback,
            llm_log=feedback_result.log,
        )
    except SubmissionAlreadyTerminal as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "SUBMISSION_ALREADY_TERMINAL"},
        ) from exc
    except Exception:
        session.rollback()
        _release_submission_after_failed_json(
            session=session,
            submission_id=submission.id if submission is not None else None,
            error_code="ESSAY_FEEDBACK_SAVE_FAILED",
            error_message="essay feedback save failed",
            llm_call_log_id=None,
        )
        raise
    if submission is not None:
        first_draft_id = str(response_payload["first_draft"]["id"])
        finalize_submission_with_reservation(
            session=session,
            submission_id=submission.id,
            terminal_status="completed",
            saved_result=True,
            essay_version_id=first_draft_id,
            result_fetch_url=f"/api/essays/{essay.id}",
            llm_call_log_id=feedback_result.log.id if feedback_result.log else None,
        )
    session.commit()
    return response_payload


@router.post("/api/essays/{essay_id}/first-draft/stream-feedback")
async def stream_submit_first_draft_feedback(
    essay_id: str,
    payload: FirstDraftSubmit,
    request: Request,
    session_factory: SessionFactory = Depends(get_session_factory),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
):
    with session_factory() as session:
        context = require_auth_mode_state_change(request, db=session, settings=settings)
        essay = require_essay_for_auth_mode(session, settings, context, essay_id)
        try:
            existing_submission = _existing_feedback_submission_for_payload(
                session=session,
                essay=essay,
                route_scope="prewriting_first_draft",
                client_submission_id=payload.client_submission_id,
                payload=payload.model_dump(),
            )
        except IdempotencyPayloadMismatch as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_PAYLOAD_MISMATCH"},
            ) from exc
        if existing_submission is not None:
            try:
                existing_response = active_submission_json_response(existing_submission)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            if existing_response is not None:
                stream = build_prewriting_first_draft_feedback_stream(
                    request_session=session,
                    session_factory=session_factory,
                    runner=runner,
                    settings=settings,
                    essay=essay,
                    payload=payload,
                )
                return StreamingResponse(
                    stream,
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache, no-transform",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )
        _prewriting_open(essay)
        existing_first_draft = session.exec(
            select(EssayVersion).where(
                EssayVersion.essay_id == essay_id,
                EssayVersion.version_label == "first_draft",
            )
        ).first()
        if existing_first_draft:
            raise HTTPException(status_code=409, detail="first draft already submitted")
        stream = build_prewriting_first_draft_feedback_stream(
            request_session=session,
            session_factory=session_factory,
            runner=runner,
            settings=settings,
            essay=essay,
            payload=payload,
        )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
