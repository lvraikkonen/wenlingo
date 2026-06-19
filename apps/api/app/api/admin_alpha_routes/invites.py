import secrets
import sys

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.admin_alpha_routes.common import (
    AdminInviteCreate,
    EmptyAdminAction,
    require_alpha_admin_state_change,
)
from app.api.deps import get_db_session
from app.api.routes.alpha import hash_invite_code
from app.domain.models import AlphaInviteCode

router = APIRouter()


def _generate_invite_code() -> str:
    return f"ALPHA-{secrets.token_urlsafe(9).upper().replace('-', '').replace('_', '')}"


_ORIGINAL_INVITE_CODE_GENERATOR = _generate_invite_code


def _generate_invite_code_for_compat() -> str:
    wrapper = sys.modules.get("app.api.routes.admin_alpha")
    wrapper_generator = (
        getattr(wrapper, "_generate_invite_code", None) if wrapper is not None else None
    )
    if (
        wrapper_generator is not None
        and wrapper_generator is not _generate_invite_code
        and wrapper_generator is not _ORIGINAL_INVITE_CODE_GENERATOR
    ):
        return wrapper_generator()
    return _generate_invite_code()


def _generate_unique_invite_code(reserved_hashes: set[str]) -> tuple[str, str]:
    for _ in range(100):
        raw_code = _generate_invite_code_for_compat()
        code_hash = hash_invite_code(raw_code)
        if code_hash not in reserved_hashes:
            reserved_hashes.add(code_hash)
            return raw_code, code_hash
    raise HTTPException(status_code=500, detail="could not generate unique invite code")


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
