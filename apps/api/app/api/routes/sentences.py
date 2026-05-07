from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.domain.enums import TaskType
from app.domain.models import AbilityProfile, SentenceTraining, StudentProfile
from app.services.abilities import apply_ability_delta
from app.services.ai_tasks import sentence_upgrade_feedback
from app.services.gamification import settle_task
from app.services.llm_provider import MockLLMProvider
from app.services.recommendations import choose_today_tasks

router = APIRouter(prefix="/api/students", tags=["sentences"])


class SentenceTrainingCreate(BaseModel):
    source_sentence: str = Field(min_length=1)
    upgraded_sentence: str = Field(min_length=1)
    focus: str


@router.post("/{student_id}/sentences", status_code=201)
async def create_sentence_training(
    student_id: str,
    request: SentenceTrainingCreate,
    session: Session = Depends(get_db_session),
):
    student = session.get(StudentProfile, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not student or not ability:
        raise HTTPException(status_code=404, detail="student not found")
    feedback = await sentence_upgrade_feedback(
        provider=MockLLMProvider(),
        source_sentence=request.source_sentence,
        upgraded_sentence=request.upgraded_sentence,
        focus=request.focus,
    )
    training = SentenceTraining(
        student_id=student_id,
        source_sentence=request.source_sentence,
        upgraded_sentence=request.upgraded_sentence,
        focus=request.focus,
        ai_feedback=feedback.model_dump(),
    )
    apply_ability_delta(ability, TaskType.sentence, "sentence_upgrade", 0.8)
    event = settle_task(student, TaskType.sentence, feedback.problem_monsters, {"focus": request.focus})
    session.add(training)
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
        "next_task": choose_today_tasks(ability, has_completed_assessment=True).main.model_dump(),
    }
