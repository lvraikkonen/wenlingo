from collections import Counter
from datetime import datetime, timezone
import secrets
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.auth_deps import require_allowed_origin, require_json_state_change
from app.api.deps import get_db_session
from app.api.routes.alpha import hash_invite_code, sanitize_event_payload
from app.core.config import Settings, get_settings
from app.domain.models import (
    AlphaInviteCode,
    Assessment,
    FeedbackReaction,
    LLMCallLog,
    ParentAccount,
    ParentFeedback,
    ParentSession,
    ParentUser,
    ProductEvent,
    StudentProfile,
    utcnow,
)
from app.services.auth_security import mask_email
from app.services.admin_test_account_cleanup import delete_test_accounts

router = APIRouter(prefix="/api/admin/alpha", tags=["admin-alpha"])


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


def _generate_invite_code() -> str:
    return f"ALPHA-{secrets.token_urlsafe(9).upper().replace('-', '').replace('_', '')}"


def _generate_unique_invite_code(reserved_hashes: set[str]) -> tuple[str, str]:
    for _ in range(100):
        raw_code = _generate_invite_code()
        code_hash = hash_invite_code(raw_code)
        if code_hash not in reserved_hashes:
            reserved_hashes.add(code_hash)
            return raw_code, code_hash
    raise HTTPException(status_code=500, detail="could not generate unique invite code")


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


def _is_demo_or_system_account(session: Session, account: ParentAccount) -> bool:
    if account.email_normalized == "demo@wenlingo.local":
        return True
    parent = session.exec(select(ParentUser).where(ParentUser.account_id == account.id)).first()
    return bool(parent and parent.email.startswith("demo@wenlingo.local"))


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


@router.post(
    "/invites",
    status_code=201,
    dependencies=[Depends(require_alpha_admin_state_change)],
)
def create_admin_alpha_invites(
    request: AdminInviteCreate,
    session: Session = Depends(get_db_session),
):
    rows: list[dict[str, str]] = []
    reserved_hashes = set(session.exec(select(AlphaInviteCode.code_hash)).all())
    for index in range(1, request.count + 1):
        raw_code, code_hash = _generate_unique_invite_code(reserved_hashes)
        invite = AlphaInviteCode(
            code_hash=code_hash,
            label=f"{request.label_prefix} {index:02d}",
            status="issued",
            issued_to_note=request.issued_to_note,
        )
        session.add(invite)
        session.flush()
        rows.append(
            {
                "invite_id": invite.id,
                "label": invite.label,
                "status": invite.status,
                "raw_code": raw_code,
            }
        )
    session.commit()
    return {"invites": rows}


@router.post(
    "/invites/{invite_id}/revoke",
    dependencies=[Depends(require_alpha_admin_state_change)],
)
def revoke_admin_alpha_invite(
    invite_id: str,
    request: EmptyAdminAction,
    session: Session = Depends(get_db_session),
):
    invite = session.get(AlphaInviteCode, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="invite not found")
    if invite.status != "issued" or invite.consumed_by_parent_id or invite.consumed_at:
        raise HTTPException(status_code=409, detail="invite is not revocable")

    invite.status = "revoked"
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return {
        "invite": {
            "invite_id": invite.id,
            "label": invite.label,
            "status": invite.status,
        }
    }


@router.get("/accounts", dependencies=[Depends(require_alpha_admin_token)])
def list_admin_alpha_accounts(session: Session = Depends(get_db_session)):
    accounts = sorted(
        session.exec(select(ParentAccount)).all(),
        key=lambda account: (account.created_at, account.id),
    )
    rows: list[dict[str, Any]] = []
    for account in accounts:
        parent = session.exec(
            select(ParentUser).where(ParentUser.account_id == account.id)
        ).first()
        rows.append(
            {
                "account_id": account.id,
                "email_masked": mask_email(account.email_normalized),
                "status": account.status,
                "parent_id": parent.id if parent else None,
                "parent_display_name": parent.display_name if parent else None,
                "children_count": len(_children_for_parent(session, parent.id))
                if parent
                else 0,
                "active_session_count": _active_session_count(session, account.id),
                "created_at": _serialize_dt(account.created_at),
                "updated_at": _serialize_dt(account.updated_at),
                "last_login_at": _serialize_dt(account.last_login_at),
            }
        )
    return {"accounts": rows}


@router.post(
    "/accounts/{account_id}/disable",
    dependencies=[Depends(require_alpha_admin_state_change)],
)
def disable_admin_alpha_account(
    account_id: str,
    request: EmptyAdminAction,
    session: Session = Depends(get_db_session),
):
    account = session.get(ParentAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    if _is_demo_or_system_account(session, account):
        raise HTTPException(status_code=409, detail="demo/system account cannot be disabled")

    now = utcnow()
    account.status = "disabled"
    account.updated_at = now
    active_sessions = session.exec(
        select(ParentSession).where(
            ParentSession.account_id == account.id,
            ParentSession.revoked_at.is_(None),
            ParentSession.expires_at > now,
        )
    ).all()
    for parent_session in active_sessions:
        parent_session.revoked_at = now
        session.add(parent_session)
    session.add(account)
    session.commit()
    session.refresh(account)
    return {
        "account": {
            "account_id": account.id,
            "status": account.status,
            "revoked_session_count": len(active_sessions),
        }
    }


@router.post(
    "/accounts/{account_id}/enable",
    dependencies=[Depends(require_alpha_admin_state_change)],
)
def enable_admin_alpha_account(
    account_id: str,
    request: EmptyAdminAction,
    session: Session = Depends(get_db_session),
):
    account = session.get(ParentAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")

    account.status = "active"
    account.updated_at = utcnow()
    session.add(account)
    session.commit()
    session.refresh(account)
    return {
        "account": {
            "account_id": account.id,
            "status": account.status,
        }
    }


@router.post(
    "/accounts/delete-test",
    dependencies=[Depends(require_alpha_admin_state_change)],
)
def delete_admin_alpha_test_accounts(
    request: AdminAccountDeleteTestRequest,
    session: Session = Depends(get_db_session),
):
    result = delete_test_accounts(
        session,
        account_ids=request.account_ids,
        confirm=request.confirm,
    )
    return {
        "deleted_count": result.deleted_count,
        "accounts": [
            {
                "account_id": row.account_id,
                "email_masked": row.email_masked,
                "parent_ids": row.parent_ids,
                "child_count": row.child_count,
                "deleted_session_count": row.deleted_session_count,
                "deleted_invite_count": row.deleted_invite_count,
            }
            for row in result.deleted_accounts
        ],
    }


@router.get("/ai-usage", dependencies=[Depends(require_alpha_admin_token)])
def alpha_admin_ai_usage(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    pricing_configured = (
        settings.llm_input_cost_per_1k_tokens > 0
        or settings.llm_output_cost_per_1k_tokens > 0
    )
    aggregates: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for log in session.exec(select(LLMCallLog)).all():
        usage_date = _product_day(log.created_at, settings.llm_daily_limit_timezone)
        final_status = log.final_status or (
            "primary_success" if log.validation_ok else "failed"
        )
        key = (
            usage_date,
            log.task_name,
            log.resolved_provider or log.provider,
            log.resolved_model or log.model,
            final_status,
        )
        row = aggregates.setdefault(
            key,
            {
                "date": usage_date,
                "task_type": log.task_name,
                "provider": log.resolved_provider or log.provider,
                "model": log.resolved_model or log.model,
                "final_status": final_status,
                "call_count": 0,
                "success_count": 0,
                "fallback_success_count": 0,
                "deterministic_fallback_count": 0,
                "failure_count": 0,
                "daily_limit_hit_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost": 0.0,
                "pricing_status": log.pricing_status or "pricing_unconfigured",
                "latency_ms_total": 0,
                "avg_latency_ms": 0,
            },
        )
        row["call_count"] += 1
        status = row["final_status"]
        if status == "primary_success":
            row["success_count"] += 1
        elif status == "fallback_success":
            row["success_count"] += 1
            row["fallback_success_count"] += 1
        elif status == "deterministic_fallback_used":
            row["deterministic_fallback_count"] += 1
        elif status == "failed":
            row["failure_count"] += 1
        row["prompt_tokens"] += log.prompt_tokens
        row["completion_tokens"] += log.completion_tokens
        row["total_tokens"] += log.total_tokens
        row["estimated_cost"] += log.estimated_cost
        row["latency_ms_total"] += log.latency_ms

    limit_hits: Counter[tuple[str, str]] = Counter()
    events = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "ai_daily_limit_reached")
    ).all()
    for event in events:
        task_type = event.payload.get("task_type")
        if isinstance(task_type, str) and task_type:
            usage_date = _product_day(
                event.created_at,
                settings.llm_daily_limit_timezone,
            )
            limit_hits[(usage_date, task_type)] += 1

    rows = []
    for key in sorted(aggregates):
        row = aggregates[key]
        row["daily_limit_hit_count"] += limit_hits[(row["date"], row["task_type"])]
        row["estimated_cost"] = round(row["estimated_cost"], 6)
        row["avg_latency_ms"] = (
            int(row["latency_ms_total"] / row["call_count"])
            if row["call_count"]
            else 0
        )
        row.pop("latency_ms_total", None)
        rows.append(row)
    return {"pricing_configured": pricing_configured, "usage": rows}


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
