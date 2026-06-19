from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.auth_deps import require_allowed_origin, require_json_state_change
from app.core.config import Settings, get_settings
from app.domain.models import (
    FeedbackReaction,
    ParentFeedback,
    ParentSession,
    ParentUser,
    ProductEvent,
    StudentProfile,
    utcnow,
)


def require_alpha_admin_token(
    x_alpha_admin_token: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.alpha_admin_token or x_alpha_admin_token != settings.alpha_admin_token:
        raise HTTPException(status_code=403, detail="admin token required")


class AdminInviteCreate(BaseModel):
    count: int = Field(ge=1, le=20)
    label_prefix: str = Field(min_length=1, max_length=80)
    issued_to_note: str = Field(default="", max_length=240)


class EmptyAdminAction(BaseModel):
    pass


class AdminAccountDeleteTestRequest(BaseModel):
    account_ids: list[str] = Field(min_length=1, max_length=20)
    confirm: str


def require_alpha_admin_state_change(
    request: Request,
    x_alpha_admin_token: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    require_alpha_admin_token(
        x_alpha_admin_token=x_alpha_admin_token,
        settings=settings,
    )
    require_allowed_origin(request, settings)
    require_json_state_change(request)


def _serialize_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _product_day(value: datetime, timezone_name: str) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(timezone_name)).date().isoformat()


def _children_for_parent(session: Session, parent_id: str) -> list[StudentProfile]:
    children = session.exec(
        select(StudentProfile).where(StudentProfile.parent_id == parent_id)
    ).all()
    return sorted(children, key=lambda child: (child.created_at, child.id))


def _active_session_count(session: Session, account_id: str) -> int:
    now = utcnow()
    return len(
        session.exec(
            select(ParentSession).where(
                ParentSession.account_id == account_id,
                ParentSession.revoked_at.is_(None),
                ParentSession.expires_at > now,
            )
        ).all()
    )


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
