from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.deps import get_db_session, get_llm_provider
from app.core.config import Settings, get_settings
from app.domain.enums import TaskType
from app.domain.models import AbilityProfile, Essay, EssayVersion, StudentProfile
from app.services.abilities import apply_ability_delta
from app.services.ai_tasks import essay_feedback, essay_revision_comparison
from app.services.gamification import settle_task
from app.services.llm_provider import LLMProvider

router = APIRouter(tags=["essays"])


class EssayCreate(BaseModel):
    title: str = Field(min_length=1)
    draft: str = Field(min_length=20)
    entry: str


class EssayRevisionCreate(BaseModel):
    content: str = Field(min_length=20)
    completed_tasks: list[str] = Field(default_factory=list)
    skipped_tasks: list[str] = Field(default_factory=list)
    duration_seconds: int | None = Field(default=None, ge=0)


@router.post("/api/students/{student_id}/essays", status_code=201)
async def create_essay(
    student_id: str,
    request: EssayCreate,
    session: Session = Depends(get_db_session),
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
):
    student = session.get(StudentProfile, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="student not found")
    try:
        feedback_result = await essay_feedback(
            provider,
            request.title,
            request.draft,
            session=session,
            prompt_version=settings.llm_prompt_version,
            student_id=student_id,
            daily_limit_enabled=settings.llm_daily_limit_enabled,
            daily_limit_per_student_task=settings.llm_daily_limit_per_student_task,
        )
        feedback = feedback_result.output
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
        llm_call_log_id=feedback_result.log.id if feedback_result.log else None,
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
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
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
    comparison_result = await essay_revision_comparison(
        provider,
        first_draft.content,
        request.content,
        session=session,
        prompt_version=settings.llm_prompt_version,
        student_id=essay.student_id,
        daily_limit_enabled=settings.llm_daily_limit_enabled,
        daily_limit_per_student_task=settings.llm_daily_limit_per_student_task,
    )
    comparison = comparison_result.output
    revision = EssayVersion(
        essay_id=essay_id,
        version_label="revision",
        content=request.content,
        ai_feedback=comparison.model_dump(),
        completed_tasks=request.completed_tasks,
        skipped_tasks=request.skipped_tasks,
        duration_seconds=request.duration_seconds,
        llm_call_log_id=comparison_result.log.id if comparison_result.log else None,
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
