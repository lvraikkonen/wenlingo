from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.auth_deps import (
    ParentContext,
    optional_parent_context,
    require_allowed_origin,
    require_json_state_change,
)
from app.api.deps import get_db_session, get_llm_provider
from app.api.feedback_state import feedback_reaction_value
from app.api.routes.alpha import record_product_event
from app.core.config import Settings, get_settings
from app.domain.enums import SentenceFocus, TaskType
from app.domain.models import AbilityProfile, SentenceTraining, StudentProfile
from app.services.abilities import VALID_ABILITY_NAMES, apply_ability_delta
from app.services.ai_tasks import sentence_upgrade_feedback
from app.services.gamification import settle_task
from app.services.llm_provider import LLMProvider
from app.services.recommendations import choose_today_tasks

router = APIRouter(prefix="/api/students", tags=["sentences"])

SENTENCE_ABILITY_DELTA_FALLBACK = {"expression": 2, "observation": 2}
DAILY_LIMIT_ERROR_MESSAGE = "daily limit exceeded"


class SentenceTrainingCreate(BaseModel):
    source_sentence: str = Field(min_length=1, max_length=500)
    upgraded_sentence: str = Field(min_length=1, max_length=500)
    focus: SentenceFocus


def _is_ai_feedback_failure(log) -> bool:
    return bool(
        log
        and log.validation_ok is False
        and log.error_message
        and log.error_message != DAILY_LIMIT_ERROR_MESSAGE
    )


def _student_or_404_for_auth_mode(
    session: Session,
    settings: Settings,
    context: ParentContext | None,
    student_id: str,
) -> StudentProfile:
    student = session.get(StudentProfile, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="student not found")
    if settings.auth_required_for_alpha:
        if context is None or context.parent is None:
            raise HTTPException(status_code=401, detail="parent session required")
        if student.parent_id != context.parent.id:
            raise HTTPException(status_code=404, detail="student not found")
    return student


@router.post(
    "/{student_id}/sentences",
    status_code=201,
    dependencies=[Depends(require_allowed_origin), Depends(require_json_state_change)],
)
async def create_sentence_training(
    student_id: str,
    request: SentenceTrainingCreate,
    session: Session = Depends(get_db_session),
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(optional_parent_context),
):
    student = _student_or_404_for_auth_mode(session, settings, context, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not ability:
        raise HTTPException(status_code=404, detail="student not found")
    focus = request.focus.value
    try:
        feedback_result = await sentence_upgrade_feedback(
            provider=provider,
            source_sentence=request.source_sentence,
            upgraded_sentence=request.upgraded_sentence,
            focus=focus,
            session=session,
            prompt_version=settings.llm_prompt_version,
            student_id=student_id,
            daily_limit_enabled=settings.llm_daily_limit_enabled,
            daily_limit_per_student_task=settings.llm_daily_limit_per_student_task,
        )
    except Exception:
        session.rollback()
        try:
            record_product_event(
                session,
                "ai_feedback_failed",
                parent_id=student.parent_id,
                student_id=student.id,
                payload={"task_type": "sentence", "error_category": "exception"},
            )
            session.commit()
        except Exception:
            session.rollback()
        raise
    feedback = feedback_result.output
    if _is_ai_feedback_failure(feedback_result.log):
        try:
            record_product_event(
                session,
                "ai_feedback_failed",
                parent_id=student.parent_id,
                student_id=student.id,
                payload={"task_type": "sentence", "error_category": "exception"},
            )
        except Exception:
            pass
    training = SentenceTraining(
        student_id=student_id,
        source_sentence=request.source_sentence,
        upgraded_sentence=request.upgraded_sentence,
        focus=focus,
        ai_feedback=feedback.model_dump(),
    )
    session.add(training)
    session.flush()
    try:
        record_product_event(
            session,
            "sentence_training_completed",
            parent_id=student.parent_id,
            student_id=student.id,
            payload={
                "target_type": "sentence_training",
                "target_id": training.id,
                "task_type": "sentence",
                "status": "completed",
            },
        )
    except Exception:
        pass
    ability_deltas = feedback.ability_delta
    if not any(
        ability_name in VALID_ABILITY_NAMES and raw_delta > 0
        for ability_name, raw_delta in ability_deltas.items()
    ):
        ability_deltas = SENTENCE_ABILITY_DELTA_FALLBACK
    apply_ability_delta(session, ability, ability_deltas, TaskType.sentence, training.id)
    event = settle_task(student, TaskType.sentence, feedback.problem_monsters, {"focus": focus})
    session.add(ability)
    session.add(student)
    session.add(event)
    training_payload = training.model_dump()
    training_payload["reaction"] = feedback_reaction_value(
        session,
        student.id,
        "sentence_training",
        training.id,
    )
    settlement_payload = event.model_dump()
    session.commit()
    return {
        "training": training_payload,
        "feedback": feedback,
        "settlement": settlement_payload,
        "next_task": choose_today_tasks(ability).main.model_dump(),
    }
