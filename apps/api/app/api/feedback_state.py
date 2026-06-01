from sqlmodel import Session, select

from app.domain.models import FeedbackReaction, ParentFeedback


def feedback_reaction_value(
    session: Session,
    student_id: str,
    target_type: str,
    target_id: str,
) -> str | None:
    reaction = session.exec(
        select(FeedbackReaction).where(
            FeedbackReaction.student_id == student_id,
            FeedbackReaction.target_type == target_type,
            FeedbackReaction.target_id == target_id,
        )
    ).first()
    return reaction.reaction if reaction else None


def parent_summary_usefulness(
    session: Session,
    parent_id: str,
    student_id: str,
) -> str | None:
    feedback = session.exec(
        select(ParentFeedback).where(
            ParentFeedback.parent_id == parent_id,
            ParentFeedback.student_id == student_id,
            ParentFeedback.target_type == "alpha_summary",
        )
    ).first()
    return feedback.usefulness if feedback else None
