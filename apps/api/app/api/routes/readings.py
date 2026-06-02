from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.auth_deps import (
    ParentContext,
    optional_parent_context,
    require_allowed_origin,
    require_json_state_change,
)
from app.api.deps import get_db_session
from app.core.config import Settings, get_settings
from app.domain.enums import TaskType
from app.domain.models import AbilityProfile, ReadingSession, StudentProfile
from app.services.abilities import apply_ability_delta
from app.services.gamification import settle_task

router = APIRouter(prefix="/api/students", tags=["readings"])

READING_ABILITY_DELTAS = {"comprehension": 4, "summarization": 4}

ARTICLES = {
    "spring-sounds": {
        "title": "春天的声音",
        "transfer_tip": "写景时可以加入声音。",
    }
}


class ReadingCreate(BaseModel):
    article_id: str
    answers: dict[str, str]


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
    "/{student_id}/readings",
    status_code=201,
    dependencies=[Depends(require_allowed_origin), Depends(require_json_state_change)],
)
def create_reading(
    student_id: str,
    request: ReadingCreate,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(optional_parent_context),
):
    student = _student_or_404_for_auth_mode(session, settings, context, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    article = ARTICLES.get(request.article_id)
    if not ability or not article:
        raise HTTPException(status_code=404, detail="reading context not found")
    reading = ReadingSession(
        student_id=student_id,
        article_title=article["title"],
        answers=request.answers,
        ai_feedback={"encouragement": "你抓住了文章里的声音细节。"},
        transfer_tip=article["transfer_tip"],
    )
    session.add(reading)
    session.flush()
    apply_ability_delta(session, ability, READING_ABILITY_DELTAS, TaskType.reading, reading.id)
    event = settle_task(student, TaskType.reading, ["概括不清"], {"transfer_tip": article["transfer_tip"]})
    session.add(ability)
    session.add(student)
    session.add(event)
    reading_payload = reading.model_dump()
    session.commit()
    return reading_payload
