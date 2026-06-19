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
from app.services.parent_sessions import (
    active_parent_sessions_for_account,
    revoke_active_parent_sessions_for_account,
    revoke_parent_session_for_account,
)

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


def _session_payload(parent_session: ParentSession) -> dict[str, Any]:
    return {
        "session_id": parent_session.id,
        "created_at": _serialize_dt(parent_session.created_at),
        "last_seen_at": _serialize_dt(parent_session.last_seen_at),
        "expires_at": _serialize_dt(parent_session.expires_at),
        "revoked_at": _serialize_dt(parent_session.revoked_at),
    }


@router.get("/accounts/{account_id}/sessions", dependencies=[Depends(require_alpha_admin_token)])
def list_admin_alpha_account_sessions(
    account_id: str,
    session: Session = Depends(get_db_session),
):
    account = session.get(ParentAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    return {
        "account": {
            "account_id": account.id,
            "email_masked": mask_email(account.email_normalized),
            "status": account.status,
        },
        "sessions": [
            _session_payload(parent_session)
            for parent_session in active_parent_sessions_for_account(session, account.id)
        ],
    }


@router.post(
    "/accounts/{account_id}/sessions/{session_id}/revoke",
    dependencies=[Depends(require_alpha_admin_state_change)],
)
def revoke_admin_alpha_account_session(
    account_id: str,
    session_id: str,
    request: EmptyAdminAction,
    session: Session = Depends(get_db_session),
):
    account = session.get(ParentAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        result = revoke_parent_session_for_account(session, account.id, session_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="session not found") from None
    session.commit()
    return {
        "session": {
            "session_id": result.session_id,
            "revoked": result.revoked,
        }
    }


@router.post(
    "/accounts/{account_id}/sessions/revoke-all",
    dependencies=[Depends(require_alpha_admin_state_change)],
)
def revoke_all_admin_alpha_account_sessions(
    account_id: str,
    request: EmptyAdminAction,
    session: Session = Depends(get_db_session),
):
    account = session.get(ParentAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    result = revoke_active_parent_sessions_for_account(session, account.id)
    session.commit()
    return {
        "account": {
            "account_id": account.id,
            "revoked_session_count": result.revoked_session_count,
        }
    }


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
    result = revoke_active_parent_sessions_for_account(session, account.id)
    session.add(account)
    session.commit()
    session.refresh(account)
    return {
        "account": {
            "account_id": account.id,
            "status": account.status,
            "revoked_session_count": result.revoked_session_count,
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
