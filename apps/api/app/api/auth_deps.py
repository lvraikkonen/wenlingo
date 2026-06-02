from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.core.config import Settings, get_settings
from app.domain.models import Essay, ParentAccount, ParentSession, ParentUser, StudentProfile
from app.services.parent_sessions import get_session_account, touch_parent_session


@dataclass
class ParentContext:
    account: ParentAccount
    parent: ParentUser | None
    session: ParentSession


def require_json_state_change(request: Request) -> None:
    if request.method not in {"POST", "PATCH", "PUT", "DELETE"}:
        return
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        raise HTTPException(status_code=415, detail="JSON body required")


def require_allowed_origin(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    if request.method not in {"POST", "PATCH", "PUT", "DELETE"}:
        return
    allowed = {
        origin.strip()
        for origin in settings.auth_allowed_origins.split(",")
        if origin.strip()
    }
    if not allowed:
        return

    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    referer_origin = ""
    if referer:
        referer_origin = "/".join(referer.split("/", 3)[:3])
    candidate = origin or referer_origin
    if candidate not in allowed:
        raise HTTPException(status_code=403, detail="origin not allowed")


def optional_parent_context(
    request: Request,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ParentContext | None:
    token = request.cookies.get(settings.auth_session_cookie_name)
    session_pair = get_session_account(db=db, settings=settings, token=token)
    if not session_pair:
        return None

    account, parent_session = session_pair
    parent = db.exec(select(ParentUser).where(ParentUser.account_id == account.id)).first()
    touch_parent_session(db=db, settings=settings, parent_session=parent_session)
    return ParentContext(account=account, parent=parent, session=parent_session)


def require_parent_context(
    context: ParentContext | None = Depends(optional_parent_context),
) -> ParentContext:
    if context is None:
        raise HTTPException(status_code=401, detail="parent session required")
    return context


def require_linked_parent(
    context: ParentContext = Depends(require_parent_context),
) -> ParentUser:
    if context.parent is None:
        raise HTTPException(status_code=404, detail="alpha parent not found")
    return context.parent


def require_student_for_parent(
    db: Session,
    parent: ParentUser,
    student_id: str,
) -> StudentProfile:
    student = db.get(StudentProfile, student_id)
    if not student or student.parent_id != parent.id:
        raise HTTPException(status_code=404, detail="student not found")
    return student


def require_essay_for_parent(db: Session, parent: ParentUser, essay_id: str) -> Essay:
    essay = db.get(Essay, essay_id)
    if not essay:
        raise HTTPException(status_code=404, detail="essay not found")
    require_student_for_parent(db, parent, essay.student_id)
    return essay
