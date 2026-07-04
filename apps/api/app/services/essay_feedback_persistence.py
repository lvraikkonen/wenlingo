from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.feedback_state import feedback_reaction_value
from app.api.routes.alpha import record_product_event
from app.domain.enums import TaskType
from app.domain.models import (
    AbilityProfile,
    Essay,
    EssayVersion,
    LLMCallLog,
    StudentProfile,
    utcnow,
)
from app.services.abilities import apply_ability_delta
from app.services.essay_archive import get_version_label_for_round
from app.services.essay_workflow import REVISION_REQUESTED_STATUS, draft_ability_deltas
from app.services.llm_contracts import EssayFeedback
from app.services.writing_castle_state import resolve_essay_scaffold


def _feedback_log_id(llm_log: LLMCallLog | None) -> str | None:
    return llm_log.id if llm_log is not None else None


def _student_and_ability(session: Session, student_id: str) -> tuple[StudentProfile, AbilityProfile]:
    student = session.get(StudentProfile, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not student or not ability:
        raise HTTPException(status_code=404, detail="student not found")
    return student, ability


def _record_feedback_event(
    session: Session,
    *,
    student: StudentProfile,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    try:
        record_product_event(
            session,
            event_type,
            parent_id=student.parent_id,
            student_id=student.id,
            payload=payload,
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


def save_direct_draft_feedback_result(
    *,
    session: Session,
    student_id: str,
    title: str,
    draft: str,
    feedback: EssayFeedback,
    llm_log: LLMCallLog | None,
) -> dict[str, Any]:
    student, ability = _student_and_ability(session, student_id)
    submitted_at = utcnow()
    essay = Essay(
        student_id=student_id,
        title=title,
        status=REVISION_REQUESTED_STATUS,
        updated_at=submitted_at,
        last_version_submitted_at=submitted_at,
    )
    session.add(essay)
    session.flush()
    version = EssayVersion(
        essay_id=essay.id,
        version_label=get_version_label_for_round(1),
        round_index=1,
        content=draft,
        ai_feedback=feedback.model_dump(),
        llm_call_log_id=_feedback_log_id(llm_log),
        created_at=submitted_at,
    )
    session.add(version)
    session.flush()
    _record_feedback_event(
        session,
        student=student,
        event_type="essay_draft_feedback_completed",
        payload={
            "target_type": "essay_draft",
            "target_id": version.id,
            "task_type": "essay",
            "status": "completed",
        },
    )
    apply_ability_delta(
        session,
        ability,
        draft_ability_deltas(len(feedback.improvements)),
        TaskType.essay,
        version.id,
    )
    session.add(ability)
    essay_payload = essay.model_dump()
    version_payload = version.model_dump()
    version_payload["reaction"] = feedback_reaction_value(
        session,
        student.id,
        "essay_draft",
        version.id,
    )
    return {"essay": essay_payload, "first_draft": version_payload, "feedback": feedback}


def save_prewriting_first_draft_feedback_result(
    *,
    session: Session,
    essay: Essay,
    draft: str,
    feedback: EssayFeedback,
    llm_log: LLMCallLog | None,
) -> dict[str, Any]:
    student, ability = _student_and_ability(session, essay.student_id)
    submitted_at = utcnow()
    essay.status = REVISION_REQUESTED_STATUS
    essay.updated_at = submitted_at
    essay.last_version_submitted_at = submitted_at
    version = EssayVersion(
        essay_id=essay.id,
        version_label=get_version_label_for_round(1),
        round_index=1,
        content=draft,
        ai_feedback=feedback.model_dump(),
        llm_call_log_id=_feedback_log_id(llm_log),
        created_at=submitted_at,
    )
    session.add(essay)
    session.add(version)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="first draft already submitted") from exc
    try:
        scaffold = resolve_essay_scaffold(essay)
    except (KeyError, TypeError, ValueError):
        scaffold = None
    _record_feedback_event(
        session,
        student=student,
        event_type="prewriting_first_draft_submitted",
        payload={
            "essay_id": essay.id,
            "server_completed_at": utcnow().isoformat(),
            "step": "first_draft",
            **_scaffold_event_payload(scaffold),
        },
    )
    apply_ability_delta(
        session,
        ability,
        draft_ability_deltas(len(feedback.improvements)),
        TaskType.essay,
        version.id,
    )
    session.add(ability)
    version_payload = version.model_dump()
    version_payload["reaction"] = feedback_reaction_value(
        session,
        student.id,
        "essay_draft",
        version.id,
    )
    return {"essay": _essay_payload(essay), "first_draft": version_payload, "feedback": feedback}
