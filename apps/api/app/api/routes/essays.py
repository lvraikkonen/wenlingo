from datetime import timedelta, timezone
from hashlib import sha256
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
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
from app.domain.models import (
    AbilityProfile,
    Essay,
    EssayRevisionAttempt,
    EssayVersion,
    StudentProfile,
    utcnow,
)
from app.services.abilities import apply_ability_delta
from app.services.ai_tasks import essay_feedback, essay_revision_comparison
from app.services.essay_archive import (
    REVISION_ATTEMPT_TIMEOUT_SECONDS,
    get_round_index,
    get_version_label_for_round,
    latest_essay_version,
    mark_stale_pending_attempts_failed,
)
from app.services.essay_workflow import (
    ASSESSMENT_ESSAY_STATUS,
    REVISION_REQUESTED_STATUS,
    SETTLED_ESSAY_STATUS,
    draft_ability_deltas,
    revision_ability_deltas,
)
from app.services.gamification import settle_task

router = APIRouter(tags=["essays"])
DAILY_LIMIT_ERROR_MESSAGES = {"daily limit exceeded", "daily limit reached"}


class EssayCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    draft: str = Field(min_length=20, max_length=3000)
    entry: str


class EssayRevisionCreate(BaseModel):
    base_version_id: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=20)
    idempotency_key: str = Field(min_length=8, max_length=120)
    completed_tasks: list[str] = Field(default_factory=list)
    skipped_tasks: list[str] = Field(default_factory=list)
    duration_seconds: int | None = Field(default=None, ge=0)


def _is_ai_feedback_failure(log) -> bool:
    return bool(
        log
        and log.validation_ok is False
        and log.error_message
        and log.error_message not in DAILY_LIMIT_ERROR_MESSAGES
    )


def _content_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def _pending_revision_response(attempt: EssayRevisionAttempt) -> JSONResponse:
    return JSONResponse(
        status_code=202,
        content={
            "status": "pending_comparison",
            "attempt_id": attempt.id,
            "message": "这次修改正在保存，请不要重复提交。",
        },
    )


def _attempt_is_stale(attempt: EssayRevisionAttempt, now) -> bool:
    updated_at = attempt.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return updated_at < now - timedelta(seconds=REVISION_ATTEMPT_TIMEOUT_SECONDS)


def _failed_revision_response(attempt: EssayRevisionAttempt) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "status": "comparison_failed",
            "attempt_id": attempt.id,
            "error_code": attempt.error_code,
            "can_retry": True,
            "message": "上次 AI 对比没有完成，请重新提交这一稿。",
        },
    )


def _revision_payload(
    session: Session,
    student_id: str,
    revision: EssayVersion,
    comparison: Any,
    settlement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    revision_payload = revision.model_dump()
    revision_payload["reaction"] = feedback_reaction_value(
        session,
        student_id,
        "essay_revision",
        revision.id,
    )
    return {"revision": revision_payload, "comparison": comparison, "settlement": settlement}


def _completed_attempt_payload(session: Session, attempt: EssayRevisionAttempt) -> dict[str, Any]:
    revision = session.get(EssayVersion, attempt.new_version_id) if attempt.new_version_id else None
    if revision is None:
        raise HTTPException(status_code=409, detail="completed revision version not found")
    essay = session.get(Essay, attempt.essay_id)
    if essay is None:
        raise HTTPException(status_code=404, detail="essay not found")
    return _revision_payload(session, essay.student_id, revision, revision.ai_feedback, None)


def _same_key_attempt(
    session: Session,
    *,
    essay_id: str,
    base_version_id: str,
    idempotency_key: str,
) -> EssayRevisionAttempt | None:
    return session.exec(
        select(EssayRevisionAttempt).where(
            EssayRevisionAttempt.essay_id == essay_id,
            EssayRevisionAttempt.base_version_id == base_version_id,
            EssayRevisionAttempt.idempotency_key == idempotency_key,
        )
    ).first()


def _active_attempt_for_target(
    session: Session,
    *,
    essay_id: str,
    base_version_id: str,
    target_round_index: int,
) -> EssayRevisionAttempt | None:
    return session.exec(
        select(EssayRevisionAttempt).where(
            EssayRevisionAttempt.essay_id == essay_id,
            EssayRevisionAttempt.base_version_id == base_version_id,
            EssayRevisionAttempt.target_round_index == target_round_index,
            EssayRevisionAttempt.status.in_(["pending_comparison", "completed"]),
        )
    ).first()


@router.post(
    "/api/students/{student_id}/essays",
    status_code=201,
)
async def create_essay(
    student_id: str,
    request: EssayCreate,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    student = require_student_for_auth_mode(session, settings, context, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not ability:
        raise HTTPException(status_code=404, detail="student not found")
    try:
        feedback_result = await essay_feedback(
            runner,
            request.title,
            request.draft,
            session=session,
            prompt_version=settings.llm_prompt_version,
            student_id=student_id,
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
    essay = Essay(student_id=student_id, title=request.title, status=REVISION_REQUESTED_STATUS)
    session.add(essay)
    session.flush()
    version = EssayVersion(
        essay_id=essay.id,
        version_label="first_draft",
        content=request.draft,
        ai_feedback=feedback.model_dump(),
        llm_call_log_id=feedback_result.log.id if feedback_result.log else None,
    )
    session.add(version)
    session.flush()
    try:
        record_product_event(
            session,
            "essay_draft_feedback_completed",
            parent_id=student.parent_id,
            student_id=student.id,
            payload={
                "target_type": "essay_draft",
                "target_id": version.id,
                "task_type": "essay",
                "status": "completed",
            },
        )
    except Exception:
        pass
    ability_deltas = draft_ability_deltas(len(feedback.improvements))
    apply_ability_delta(session, ability, ability_deltas, TaskType.essay, version.id)
    session.add(ability)
    essay_payload = essay.model_dump()
    version_payload = version.model_dump()
    version_payload["reaction"] = feedback_reaction_value(
        session,
        student.id,
        "essay_draft",
        version.id,
    )
    session.commit()
    return {"essay": essay_payload, "first_draft": version_payload, "feedback": feedback}


@router.post(
    "/api/essays/{essay_id}/revision",
    status_code=201,
    response_model=None,
)
async def submit_revision(
    essay_id: str,
    request: EssayRevisionCreate,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
) -> JSONResponse | dict[str, Any]:
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    if essay.status == ASSESSMENT_ESSAY_STATUS:
        raise HTTPException(status_code=404, detail="essay not found")

    now = utcnow()
    attempt = _same_key_attempt(
        session,
        essay_id=essay_id,
        base_version_id=request.base_version_id,
        idempotency_key=request.idempotency_key,
    )
    if attempt is not None:
        if attempt.status == "completed":
            return _completed_attempt_payload(session, attempt)
        if attempt.status == "comparison_failed":
            return _failed_revision_response(attempt)
        if attempt.status == "pending_comparison":
            if not _attempt_is_stale(attempt, now):
                return _pending_revision_response(attempt)
            attempt.status = "comparison_failed"
            attempt.error_code = "attempt_timeout"
            attempt.updated_at = now
            session.add(attempt)
            session.commit()
            return _failed_revision_response(attempt)
    session.commit()

    mark_stale_pending_attempts_failed(session, now=utcnow())
    session.commit()
    latest = latest_essay_version(session, essay_id)
    if latest is None:
        raise HTTPException(status_code=409, detail="first draft not found")
    versions = session.exec(select(EssayVersion).where(EssayVersion.essay_id == essay_id)).all()
    if not any(get_round_index(version) == 1 for version in versions):
        raise HTTPException(status_code=409, detail="first draft not found")
    if latest.id != request.base_version_id:
        raise HTTPException(status_code=409, detail="base version is stale")

    target_round_index = get_round_index(latest) + 1
    active_attempt = _active_attempt_for_target(
        session,
        essay_id=essay_id,
        base_version_id=request.base_version_id,
        target_round_index=target_round_index,
    )
    if active_attempt is not None:
        if active_attempt.status == "pending_comparison":
            return _pending_revision_response(active_attempt)
        return _completed_attempt_payload(session, active_attempt)

    student = session.get(StudentProfile, essay.student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == essay.student_id)).first()
    if not student or not ability:
        raise HTTPException(status_code=404, detail="student not found")

    attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=request.base_version_id,
        target_round_index=target_round_index,
        submitted_content=request.content,
        submitted_content_hash=_content_hash(request.content),
        idempotency_key=request.idempotency_key,
        status="pending_comparison",
    )
    session.add(attempt)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        active_attempt = _active_attempt_for_target(
            session,
            essay_id=essay_id,
            base_version_id=request.base_version_id,
            target_round_index=target_round_index,
        )
        if active_attempt is not None and active_attempt.status == "pending_comparison":
            return _pending_revision_response(active_attempt)
        if active_attempt is not None and active_attempt.status == "completed":
            return _completed_attempt_payload(session, active_attempt)
        raise HTTPException(status_code=409, detail="revision attempt conflict")

    base_content = latest.content
    try:
        comparison_result = await essay_revision_comparison(
            runner,
            base_content,
            request.content,
            session=session,
            prompt_version=settings.llm_prompt_version,
            student_id=essay.student_id,
        )
    except Exception:
        session.rollback()
        failed_attempt = session.get(EssayRevisionAttempt, attempt.id)
        if failed_attempt is not None:
            failed_attempt.status = "comparison_failed"
            failed_attempt.error_code = "comparison_failed"
            failed_attempt.updated_at = utcnow()
            session.add(failed_attempt)
            session.commit()
        raise HTTPException(
            status_code=502,
            detail="这次 AI 对比没有完成，请稍后重试。",
        )
    comparison = comparison_result.output
    if _is_ai_feedback_failure(comparison_result.log):
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
    attempt = session.get(EssayRevisionAttempt, attempt.id)
    essay = session.get(Essay, essay_id)
    if attempt is None or essay is None:
        raise HTTPException(status_code=409, detail="revision attempt not found")
    revision = EssayVersion(
        essay_id=essay_id,
        version_label=get_version_label_for_round(target_round_index),
        round_index=target_round_index,
        content=request.content,
        ai_feedback=comparison.model_dump(),
        completed_tasks=request.completed_tasks,
        skipped_tasks=request.skipped_tasks,
        duration_seconds=request.duration_seconds,
        llm_call_log_id=comparison_result.log.id if comparison_result.log else None,
    )
    session.add(revision)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="essay version already exists") from exc
    try:
        record_product_event(
            session,
            "essay_revision_feedback_completed",
            parent_id=student.parent_id,
            student_id=student.id,
            payload={
                "target_type": "essay_revision",
                "target_id": revision.id,
                "task_type": "essay",
                "status": "completed",
            },
        )
    except Exception:
        pass
    settlement_payload = None
    if target_round_index == 2:
        ability_deltas = revision_ability_deltas(len(comparison.evidence))
        apply_ability_delta(session, ability, ability_deltas, TaskType.essay, revision.id)
        event = settle_task(
            student,
            TaskType.essay,
            ["细节缺口"],
            {
                "essay_id": essay_id,
                "completed_task_count": len(request.completed_tasks),
                "completed_tasks": request.completed_tasks,
                "ability_deltas": ability_deltas,
            },
        )
        essay.status = SETTLED_ESSAY_STATUS
        session.add(student)
        session.add(event)
        settlement_payload = event.model_dump()
    attempt.status = "completed"
    attempt.new_version_id = revision.id
    attempt.submitted_content = None
    attempt.error_code = None
    attempt.updated_at = utcnow()
    session.add(essay)
    session.add(ability)
    session.add(attempt)
    payload = _revision_payload(session, student.id, revision, comparison, settlement_payload)
    session.commit()
    return payload


@router.post(
    "/api/essays/{essay_id}/revision-attempts/{attempt_id}/retry-comparison",
    status_code=201,
    response_model=None,
)
async def retry_revision_attempt(
    essay_id: str,
    attempt_id: str,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
) -> JSONResponse | dict[str, Any]:
    """Retry a comparison_failed attempt using the preserved submitted content."""
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    if essay.status == ASSESSMENT_ESSAY_STATUS:
        raise HTTPException(status_code=404, detail="essay not found")
    attempt = session.get(EssayRevisionAttempt, attempt_id)
    if attempt is None or attempt.essay_id != essay_id:
        raise HTTPException(status_code=404, detail="revision attempt not found")
    if attempt.status != "comparison_failed":
        raise HTTPException(status_code=409, detail="revision attempt is not retryable")
    if not attempt.submitted_content:
        raise HTTPException(status_code=409, detail="revision attempt content not found")

    latest = latest_essay_version(session, essay_id)
    if latest is None:
        raise HTTPException(status_code=409, detail="first draft not found")
    if latest.id != attempt.base_version_id:
        raise HTTPException(status_code=409, detail="base version is stale")
    student = session.get(StudentProfile, essay.student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == essay.student_id)).first()
    if not student or not ability:
        raise HTTPException(status_code=404, detail="student not found")

    revision_content = attempt.submitted_content
    target_round_index = attempt.target_round_index
    base_content = latest.content
    attempt.status = "pending_comparison"
    attempt.error_code = None
    attempt.updated_at = utcnow()
    session.add(attempt)
    session.commit()

    try:
        comparison_result = await essay_revision_comparison(
            runner,
            base_content,
            revision_content,
            session=session,
            prompt_version=settings.llm_prompt_version,
            student_id=essay.student_id,
        )
    except Exception:
        session.rollback()
        failed_attempt = session.get(EssayRevisionAttempt, attempt_id)
        if failed_attempt is not None:
            failed_attempt.status = "comparison_failed"
            failed_attempt.error_code = "comparison_failed"
            failed_attempt.updated_at = utcnow()
            session.add(failed_attempt)
            session.commit()
        raise HTTPException(
            status_code=502,
            detail="这次 AI 对比没有完成，请稍后重试。",
        )

    comparison = comparison_result.output
    attempt = session.get(EssayRevisionAttempt, attempt_id)
    essay = session.get(Essay, essay_id)
    if attempt is None or essay is None:
        raise HTTPException(status_code=409, detail="revision attempt not found")
    revision = EssayVersion(
        essay_id=essay_id,
        version_label=get_version_label_for_round(target_round_index),
        round_index=target_round_index,
        content=revision_content,
        ai_feedback=comparison.model_dump(),
        llm_call_log_id=comparison_result.log.id if comparison_result.log else None,
    )
    session.add(revision)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="essay version already exists") from exc

    settlement_payload = None
    if target_round_index == 2:
        ability_deltas = revision_ability_deltas(len(comparison.evidence))
        apply_ability_delta(session, ability, ability_deltas, TaskType.essay, revision.id)
        event = settle_task(
            student,
            TaskType.essay,
            ["细节缺口"],
            {
                "essay_id": essay_id,
                "completed_task_count": 0,
                "completed_tasks": [],
                "ability_deltas": ability_deltas,
            },
        )
        essay.status = SETTLED_ESSAY_STATUS
        session.add(student)
        session.add(event)
        settlement_payload = event.model_dump()

    attempt.status = "completed"
    attempt.new_version_id = revision.id
    attempt.submitted_content = None
    attempt.error_code = None
    attempt.updated_at = utcnow()
    session.add(essay)
    session.add(ability)
    session.add(attempt)
    payload = _revision_payload(session, student.id, revision, comparison, settlement_payload)
    session.commit()
    return payload
