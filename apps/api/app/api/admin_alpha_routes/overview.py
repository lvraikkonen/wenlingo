from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api.admin_alpha_routes.common import (
    _children_for_parent,
    _family_events,
    _funnel_stage,
    _latest_parent_feedback,
    _reaction_counts,
    _serialize_dt,
    require_alpha_admin_token,
)
from app.api.deps import get_db_session
from app.api.routes.alpha import sanitize_event_payload
from app.domain.models import (
    AlphaInviteCode,
    Assessment,
    FeedbackReaction,
    ParentAccount,
    ParentFeedback,
    ParentUser,
)
from app.services.auth_security import mask_email

router = APIRouter()


@router.get("/overview", dependencies=[Depends(require_alpha_admin_token)])
def alpha_admin_overview(
    include_revoked: bool = Query(default=False),
    session: Session = Depends(get_db_session),
):
    statement = select(AlphaInviteCode)
    if not include_revoked:
        statement = statement.where(AlphaInviteCode.status != "revoked")
    invites = session.exec(statement).all()
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
