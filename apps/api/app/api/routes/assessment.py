from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.auth_deps import (
    ParentContext,
    require_auth_mode_state_change,
    require_student_for_auth_mode,
)
from app.api.deps import AITaskRunner, get_ai_task_runner, get_db_session
from app.api.feedback_state import feedback_reaction_value
from app.api.routes.alpha import record_product_event
from app.core.config import Settings, get_settings
from app.domain.models import AbilityProfile
from app.services.assessment import complete_entry_assessment

router = APIRouter(prefix="/api/students", tags=["assessment"])


class AssessmentCreate(BaseModel):
    sentence_before: str = Field(min_length=1, max_length=500)
    sentence_after: str = Field(min_length=1, max_length=500)
    short_writing: str = Field(min_length=20, max_length=500)


@router.post(
    "/{student_id}/assessment",
    status_code=201,
)
async def create_assessment(
    student_id: str,
    request: AssessmentCreate,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    student = require_student_for_auth_mode(session, settings, context, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not ability:
        session.rollback()
        raise HTTPException(status_code=404, detail="student not found")

    try:
        result = await complete_entry_assessment(
            session=session,
            student=student,
            ability=ability,
            runner=runner,
            settings=settings,
            sentence_before=request.sentence_before,
            sentence_after=request.sentence_after,
            short_writing=request.short_writing,
        )
        assessment_payload = {
            "id": result.assessment.id,
            "summary": result.assessment.summary,
            "sentence_training_id": result.assessment.sentence_training_id,
            "essay_id": result.assessment.essay_id,
            "reaction": feedback_reaction_value(
                session,
                student.id,
                "assessment",
                result.assessment.id,
            ),
        }
        settlement_payload = result.settlement.model_dump()
        response_payload = {
            "assessment": assessment_payload,
            "ability_sketch": result.ability_sketch,
            "settlement": settlement_payload,
            "game_event": settlement_payload,
        }
        try:
            record_product_event(
                session,
                "assessment_completed",
                parent_id=student.parent_id,
                student_id=student.id,
                payload={
                    "target_type": "assessment",
                    "target_id": result.assessment.id,
                    "task_type": "assessment",
                    "status": "completed",
                },
            )
        except Exception:
            pass
        session.commit()
        return response_payload
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        try:
            record_product_event(
                session,
                "ai_feedback_failed",
                parent_id=student.parent_id if student else None,
                student_id=student_id,
                payload={"task_type": "assessment", "error_category": "exception"},
            )
            session.commit()
        except Exception:
            session.rollback()
        raise
