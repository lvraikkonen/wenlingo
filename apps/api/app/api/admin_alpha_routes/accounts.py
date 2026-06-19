from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.admin_alpha_routes.common import (
    AdminAccountDeleteTestRequest,
    EmptyAdminAction,
    _active_session_count,
    _children_for_parent,
    _serialize_dt,
    require_alpha_admin_state_change,
    require_alpha_admin_token,
)
from app.api.deps import get_db_session
from app.domain.models import ParentAccount, ParentSession, ParentUser, utcnow
from app.services.admin_test_account_cleanup import delete_test_accounts
from app.services.auth_security import mask_email

router = APIRouter()


def _is_demo_or_system_account(session: Session, account: ParentAccount) -> bool:
    if account.email_normalized == "demo@wenlingo.local":
        return True
    parent = session.exec(select(ParentUser).where(ParentUser.account_id == account.id)).first()
    return bool(parent and parent.email.startswith("demo@wenlingo.local"))


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
