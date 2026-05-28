from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.api.routes.alpha import record_product_event
from app.domain.models import (
    Assessment,
    Essay,
    EssayVersion,
    FeedbackReaction,
    SentenceTraining,
    StudentProfile,
)

router = APIRouter(prefix="/api/students", tags=["reactions"])


class FeedbackReactionCreate(BaseModel):
    target_type: Literal[
        "assessment",
        "sentence_training",
        "essay_draft",
        "essay_revision",
    ]
    target_id: str = Field(min_length=1)
    reaction: Literal["positive", "neutral", "negative"]
    parent_id: str | None = None
    alpha_session_id: str = Field(default="", max_length=120)


def _target_belongs_to_student(
    session: Session,
    student_id: str,
    target_type: str,
    target_id: str,
) -> bool:
    if target_type == "assessment":
        return (
            session.exec(
                select(Assessment).where(
                    Assessment.id == target_id,
                    Assessment.student_id == student_id,
                )
            ).first()
            is not None
        )
    if target_type == "sentence_training":
        return (
            session.exec(
                select(SentenceTraining).where(
                    SentenceTraining.id == target_id,
                    SentenceTraining.student_id == student_id,
                )
            ).first()
            is not None
        )

    expected_version_label = {
        "essay_draft": "first_draft",
        "essay_revision": "revision",
    }[target_type]
    version = session.get(EssayVersion, target_id)
    if not version or version.version_label != expected_version_label:
        return False
    essay = session.get(Essay, version.essay_id)
    return bool(essay and essay.student_id == student_id)


@router.post("/{student_id}/feedback-reactions", status_code=201)
def create_feedback_reaction(
    student_id: str,
    request: FeedbackReactionCreate,
    session: Session = Depends(get_db_session),
):
    student = session.get(StudentProfile, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="student not found")
    if request.parent_id is not None and request.parent_id != student.parent_id:
        raise HTTPException(status_code=404, detail="student not found")
    if not _target_belongs_to_student(
        session,
        student_id,
        request.target_type,
        request.target_id,
    ):
        raise HTTPException(status_code=404, detail="feedback target not found")

    reaction = session.exec(
        select(FeedbackReaction).where(
            FeedbackReaction.student_id == student_id,
            FeedbackReaction.target_type == request.target_type,
            FeedbackReaction.target_id == request.target_id,
        )
    ).first()
    if reaction:
        reaction.reaction = request.reaction
        reaction.parent_id = request.parent_id
        reaction.alpha_session_id = request.alpha_session_id
        reaction.updated_at = datetime.now(timezone.utc)
    else:
        reaction = FeedbackReaction(
            parent_id=request.parent_id,
            student_id=student_id,
            target_type=request.target_type,
            target_id=request.target_id,
            reaction=request.reaction,
            alpha_session_id=request.alpha_session_id,
        )
    session.add(reaction)
    try:
        record_product_event(
            session,
            "child_feedback_reaction_submitted",
            parent_id=request.parent_id,
            student_id=student_id,
            alpha_session_id=request.alpha_session_id,
            payload={
                "target_type": request.target_type,
                "target_id": request.target_id,
                "reaction": request.reaction,
            },
        )
    except Exception:
        pass
    session.commit()
    session.refresh(reaction)
    return {
        "reaction": {
            "id": reaction.id,
            "student_id": reaction.student_id,
            "target_type": reaction.target_type,
            "target_id": reaction.target_id,
            "reaction": reaction.reaction,
        }
    }
