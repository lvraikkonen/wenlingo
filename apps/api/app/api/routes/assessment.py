from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.domain.enums import TaskType
from app.domain.models import AbilityProfile, Assessment, StudentProfile
from app.services.abilities import apply_ability_delta
from app.services.gamification import settle_task

router = APIRouter(prefix="/api/students", tags=["assessment"])


class AssessmentCreate(BaseModel):
    sentence_before: str = Field(min_length=1)
    sentence_after: str = Field(min_length=1)
    short_writing: str = Field(min_length=20, max_length=200)


@router.post("/{student_id}/assessment", status_code=201)
def create_assessment(
    student_id: str,
    request: AssessmentCreate,
    session: Session = Depends(get_db_session),
):
    student = session.get(StudentProfile, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not student or not ability:
        raise HTTPException(status_code=404, detail="student not found")
    assessment = Assessment(
        student_id=student_id,
        sentence_before=request.sentence_before,
        sentence_after=request.sentence_after,
        short_writing=request.short_writing,
        summary="完成入门小试炼，生成第一张能力草图。",
    )
    apply_ability_delta(ability, TaskType.assessment, "entry_assessment", 0.6)
    event = settle_task(student, TaskType.assessment, [], {"summary": assessment.summary})
    session.add(assessment)
    session.add(event)
    session.add(ability)
    session.add(student)
    session.commit()
    return {
        "assessment": {
            "id": assessment.id,
            "summary": assessment.summary,
        },
        "game_event": {
            "xp_delta": event.xp_delta,
            "level_after": event.level_after,
            "badge_code": event.badge_code,
        },
    }
