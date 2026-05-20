from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps import get_db_session, get_llm_provider
from app.core.config import Settings, get_settings
from app.domain.enums import TaskType
from app.domain.models import AbilityProfile, SentenceTraining, StudentProfile
from app.services.abilities import apply_ability_delta
from app.services.ai_tasks import sentence_upgrade_feedback
from app.services.gamification import settle_task
from app.services.llm_provider import LLMProvider
from app.services.recommendations import choose_today_tasks

router = APIRouter(prefix="/api/students", tags=["sentences"])

SENTENCE_ABILITY_DELTA_FALLBACK = {"expression": 2, "observation": 2}


class SentenceTrainingCreate(BaseModel):
    source_sentence: str = Field(min_length=1)
    upgraded_sentence: str = Field(min_length=1)
    focus: str


@router.post("/{student_id}/sentences", status_code=201)
async def create_sentence_training(
    student_id: str,
    request: SentenceTrainingCreate,
    session: Session = Depends(get_db_session),
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
):
    student = session.get(StudentProfile, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not student or not ability:
        raise HTTPException(status_code=404, detail="student not found")
    feedback_result = await sentence_upgrade_feedback(
        provider=provider,
        source_sentence=request.source_sentence,
        upgraded_sentence=request.upgraded_sentence,
        focus=request.focus,
        session=session,
        prompt_version=settings.llm_prompt_version,
        student_id=student_id,
        daily_limit_enabled=settings.llm_daily_limit_enabled,
        daily_limit_per_student_task=settings.llm_daily_limit_per_student_task,
    )
    feedback = feedback_result.output
    training = SentenceTraining(
        student_id=student_id,
        source_sentence=request.source_sentence,
        upgraded_sentence=request.upgraded_sentence,
        focus=request.focus,
        ai_feedback=feedback.model_dump(),
    )
    session.add(training)
    session.flush()
    ability_deltas = feedback.ability_delta or SENTENCE_ABILITY_DELTA_FALLBACK
    apply_ability_delta(session, ability, ability_deltas, TaskType.sentence, training.id)
    event = settle_task(student, TaskType.sentence, feedback.problem_monsters, {"focus": request.focus})
    session.add(ability)
    session.add(student)
    session.add(event)
    training_payload = training.model_dump()
    settlement_payload = event.model_dump()
    session.commit()
    return {
        "training": training_payload,
        "feedback": feedback,
        "settlement": settlement_payload,
        "next_task": choose_today_tasks(ability).main.model_dump(),
    }
