from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.domain.enums import TaskType
from app.domain.models import AbilityProfile, ReadingSession, StudentProfile
from app.services.abilities import apply_ability_delta
from app.services.gamification import settle_task

router = APIRouter(prefix="/api/students", tags=["readings"])

ARTICLES = {
    "spring-sounds": {
        "title": "鏄ュぉ鐨勫０闊?",
        "transfer_tip": "鍐欐櫙鏃跺彲浠ュ姞鍏ュ０闊炽€?",
    }
}


class ReadingCreate(BaseModel):
    article_id: str
    answers: dict[str, str]


@router.post("/{student_id}/readings", status_code=201)
def create_reading(
    student_id: str,
    request: ReadingCreate,
    session: Session = Depends(get_db_session),
):
    student = session.get(StudentProfile, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    article = ARTICLES.get(request.article_id)
    if not student or not ability or not article:
        raise HTTPException(status_code=404, detail="reading context not found")
    reading = ReadingSession(
        student_id=student_id,
        article_title=article["title"],
        answers=request.answers,
        ai_feedback={"encouragement": "浣犳姄浣忎簡鏂囩珷閲岀殑澹伴煶缁嗚妭銆?"},
        transfer_tip=article["transfer_tip"],
    )
    apply_ability_delta(ability, TaskType.reading, "reading_transfer", 0.75)
    event = settle_task(student, TaskType.reading, ["姒傛嫭涓嶆竻"], {"transfer_tip": article["transfer_tip"]})
    session.add(reading)
    session.add(ability)
    session.add(student)
    session.add(event)
    reading_payload = reading.model_dump()
    session.commit()
    return reading_payload
