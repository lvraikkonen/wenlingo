from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.domain.models import AbilityProfile, Assessment, StudentProfile
from app.services.abilities import to_child_abilities
from app.services.recommendations import choose_today_tasks

router = APIRouter(prefix="/api/students", tags=["dashboard"])


@router.get("/{student_id}/dashboard")
def student_dashboard(student_id: str, session: Session = Depends(get_db_session)):
    student = session.get(StudentProfile, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not student or not ability:
        raise HTTPException(status_code=404, detail="student not found")
    has_assessment = session.exec(select(Assessment).where(Assessment.student_id == student_id)).first() is not None
    return {
        "student": student,
        "ability_note": "第一张能力草图" if has_assessment else "等待入门小试点",
        "child_abilities": to_child_abilities(ability),
        "today_tasks": choose_today_tasks(ability).model_dump(),
        "map": ["句子工坊", "作文城堡", "阅读峡谷"],
        "coach_message": "今天先完成推荐任务，再看看哪里变强了。",
    }
