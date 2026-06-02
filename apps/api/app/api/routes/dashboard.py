from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.auth_deps import ParentContext, optional_parent_context
from app.api.deps import get_db_session
from app.core.config import Settings, get_settings
from app.domain.models import AbilityProfile, Assessment, StudentProfile
from app.services.abilities import to_child_abilities
from app.services.recommendations import choose_today_tasks

router = APIRouter(prefix="/api/students", tags=["dashboard"])


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


@router.get("/{student_id}/dashboard")
def student_dashboard(
    student_id: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(optional_parent_context),
):
    student = _student_or_404_for_auth_mode(session, settings, context, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not ability:
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
