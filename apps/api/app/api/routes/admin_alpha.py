from collections import Counter
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.api.routes.alpha import sanitize_event_payload
from app.core.config import Settings, get_settings
from app.domain.models import (
    AlphaInviteCode,
    Assessment,
    FeedbackReaction,
    ParentAccount,
    ParentFeedback,
    ParentUser,
    ProductEvent,
    StudentProfile,
)
from app.services.auth_security import mask_email

router = APIRouter(prefix="/api/admin/alpha", tags=["admin-alpha"])


def require_alpha_admin_token(
    x_alpha_admin_token: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.alpha_admin_token or x_alpha_admin_token != settings.alpha_admin_token:
        raise HTTPException(status_code=403, detail="admin token required")


def _serialize_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _reaction_counts(reactions: list[FeedbackReaction]) -> dict[str, int]:
    return dict(sorted(Counter(reaction.reaction for reaction in reactions).items()))


def _latest_parent_feedback(feedback_rows: list[ParentFeedback]) -> str | None:
    if not feedback_rows:
        return None
    latest = max(feedback_rows, key=lambda row: (row.updated_at, row.id))
    return latest.usefulness


def _family_events(
    session: Session,
    parent_id: str | None,
    invite_id: str | None = None,
    invite_ids: set[str] | None = None,
    child_ids: set[str] | None = None,
) -> list[ProductEvent]:
    events = session.exec(select(ProductEvent)).all()
    family_invite_ids = set(invite_ids or set())
    if invite_id is not None:
        family_invite_ids.add(invite_id)
    family_child_ids = child_ids or set()
    return [
        event
        for event in events
        if (parent_id is not None and event.parent_id == parent_id)
        or (event.invite_code_id is not None and event.invite_code_id in family_invite_ids)
        or (event.student_id is not None and event.student_id in family_child_ids)
    ]


def _funnel_stage(
    parent: ParentUser | None,
    child_count: int,
    assessment_completed_count: int,
    summary_viewed: bool,
) -> str:
    if summary_viewed:
        return "summary_viewed"
    if assessment_completed_count > 0:
        return "assessment_completed"
    if child_count > 0:
        return "child_created"
    if parent is not None:
        return "parent_created"
    return "invite_issued"


def _children_for_parent(session: Session, parent_id: str) -> list[StudentProfile]:
    children = session.exec(
        select(StudentProfile).where(StudentProfile.parent_id == parent_id)
    ).all()
    return sorted(children, key=lambda child: (child.created_at, child.id))


@router.get("/overview", dependencies=[Depends(require_alpha_admin_token)])
def alpha_admin_overview(session: Session = Depends(get_db_session)):
    invites = session.exec(select(AlphaInviteCode)).all()
    rows: list[dict[str, Any]] = []

    for invite in sorted(invites, key=lambda row: (row.created_at, row.id)):
        parent = (
            session.get(ParentUser, invite.consumed_by_parent_id)
            if invite.consumed_by_parent_id
            else None
        )
        account = (
            session.get(ParentAccount, parent.account_id)
            if parent and parent.account_id
            else None
        )
        children = _children_for_parent(session, parent.id) if parent else []
        child_ids = {child.id for child in children}
        reactions = (
            session.exec(
                select(FeedbackReaction).where(FeedbackReaction.student_id.in_(child_ids))
            ).all()
            if child_ids
            else []
        )
        feedback_rows = (
            session.exec(
                select(ParentFeedback).where(ParentFeedback.student_id.in_(child_ids))
            ).all()
            if child_ids
            else []
        )
        assessment_completed_count = (
            len(
                session.exec(
                    select(Assessment).where(Assessment.student_id.in_(child_ids))
                ).all()
            )
            if child_ids
            else 0
        )
        events = _family_events(
            session,
            parent.id if parent else None,
            invite_id=invite.id,
            child_ids=child_ids,
        )
        summary_viewed = any(event.event_type == "summary_viewed" for event in events)
        last_event_at = max((event.created_at for event in events), default=None)

        rows.append(
            {
                "invite_id": invite.id,
                "invite_label": invite.label,
                "invite_status": invite.status,
                "parent_id": parent.id if parent else None,
                "parent_display_name": parent.display_name if parent else None,
                "child_count": len(children),
                "funnel_stage": _funnel_stage(
                    parent,
                    len(children),
                    assessment_completed_count,
                    summary_viewed,
                ),
                "assessment_completed_count": assessment_completed_count,
                "summary_viewed": summary_viewed,
                "reaction_counts": _reaction_counts(reactions),
                "latest_parent_feedback": _latest_parent_feedback(feedback_rows),
                "last_event_at": _serialize_dt(last_event_at),
                "account_linked": account is not None,
                "account_email_masked": mask_email(account.email_normalized)
                if account
                else None,
                "phone_bound": bool(account and account.phone_bound_at),
                "last_login_at": _serialize_dt(
                    account.last_login_at if account else None
                ),
            }
        )

    return {"families": rows}


@router.get(
    "/families/{parent_id}",
    dependencies=[Depends(require_alpha_admin_token)],
)
def alpha_admin_family_detail(
    parent_id: str,
    session: Session = Depends(get_db_session),
):
    parent = session.get(ParentUser, parent_id)
    if not parent:
        raise HTTPException(status_code=404, detail="family not found")

    children = _children_for_parent(session, parent.id)
    child_ids = {child.id for child in children}
    invites = session.exec(
        select(AlphaInviteCode).where(AlphaInviteCode.consumed_by_parent_id == parent.id)
    ).all()
    invite_ids = {invite.id for invite in invites}
    events = sorted(
        _family_events(session, parent.id, invite_ids=invite_ids, child_ids=child_ids),
        key=lambda event: (event.created_at, event.id),
    )
    reactions = (
        session.exec(
            select(FeedbackReaction).where(FeedbackReaction.student_id.in_(child_ids))
        ).all()
        if child_ids
        else []
    )
    feedback_rows = (
        session.exec(
            select(ParentFeedback).where(ParentFeedback.student_id.in_(child_ids))
        ).all()
        if child_ids
        else []
    )

    return {
        "parent": {
            "id": parent.id,
            "display_name": parent.display_name,
        },
        "children": [
            {
                "id": child.id,
                "grade_label": child.grade_label,
            }
            for child in children
        ],
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "created_at": _serialize_dt(event.created_at),
                "payload": sanitize_event_payload(event.payload),
            }
            for event in events
        ],
        "reaction_counts": _reaction_counts(reactions),
        "parent_feedback": [
            {
                "student_id": row.student_id,
                "usefulness": row.usefulness,
            }
            for row in sorted(feedback_rows, key=lambda row: (row.updated_at, row.id))
        ],
    }
