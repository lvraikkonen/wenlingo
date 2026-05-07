from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.domain.enums import TaskType
from app.domain.models import AbilityProfile, Essay, EssayVersion, StudentProfile
from app.services.abilities import apply_ability_delta
from app.services.ai_tasks import essay_feedback, essay_revision_comparison
from app.services.gamification import settle_task
from app.services.llm_provider import MockLLMProvider

router = APIRouter(tags=["essays"])


class EssayCreate(BaseModel):
    title: str = Field(min_length=1)
    draft: str = Field(min_length=20)
    entry: str


class EssayRevisionCreate(BaseModel):
    content: str = Field(min_length=20)


@router.post("/api/students/{student_id}/essays", status_code=201)
async def create_essay(
    student_id: str,
    request: EssayCreate,
    session: Session = Depends(get_db_session),
):
    student = session.get(StudentProfile, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="student not found")
    try:
        feedback = await essay_feedback(MockLLMProvider(), request.title, request.draft)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    essay = Essay(student_id=student_id, title=request.title, status="revision_requested")
    session.add(essay)
    session.flush()
    version = EssayVersion(
        essay_id=essay.id,
        version_label="first_draft",
        content=request.draft,
        ai_feedback=feedback.model_dump(),
    )
    session.add(version)
    essay_payload = essay.model_dump()
    version_payload = version.model_dump()
    session.commit()
    return {"essay": essay_payload, "first_draft": version_payload, "feedback": feedback}


@router.post("/api/essays/{essay_id}/revision", status_code=201)
async def submit_revision(
    essay_id: str,
    request: EssayRevisionCreate,
    session: Session = Depends(get_db_session),
):
    essay = session.get(Essay, essay_id)
    if not essay:
        raise HTTPException(status_code=404, detail="essay not found")
    if essay.status == "settled":
        raise HTTPException(status_code=409, detail="essay already settled")
    first_draft = session.exec(
        select(EssayVersion).where(
            EssayVersion.essay_id == essay_id,
            EssayVersion.version_label == "first_draft",
        )
    ).first()
    if not first_draft:
        raise HTTPException(status_code=409, detail="first draft not found")
    existing_revision = session.exec(
        select(EssayVersion).where(
            EssayVersion.essay_id == essay_id,
            EssayVersion.version_label == "revision",
        )
    ).first()
    if existing_revision:
        raise HTTPException(status_code=409, detail="essay already settled")
    student = session.get(StudentProfile, essay.student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == essay.student_id)).first()
    if not student or not ability:
        raise HTTPException(status_code=404, detail="student not found")
    comparison = await essay_revision_comparison(
        MockLLMProvider(),
        first_draft.content,
        request.content,
    )
    revision = EssayVersion(
        essay_id=essay_id,
        version_label="revision",
        content=request.content,
        ai_feedback=comparison.model_dump(),
    )
    session.add(revision)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="essay already settled") from exc
    apply_ability_delta(ability, TaskType.essay, "essay_revision", 0.85, completed_revision=True)
    event = settle_task(student, TaskType.essay, ["细节缺口"], {"essay_id": essay_id})
    essay.status = "settled"
    session.add(essay)
    session.add(ability)
    session.add(student)
    session.add(event)
    revision_payload = revision.model_dump()
    settlement_payload = event.model_dump()
    session.commit()
    return {"revision": revision_payload, "comparison": comparison, "settlement": settlement_payload}
