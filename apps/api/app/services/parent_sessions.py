from datetime import datetime, timedelta, timezone

from fastapi import Response
from sqlmodel import Session, select

from app.core.config import Settings
from app.domain.models import ParentAccount, ParentSession, utcnow
from app.services.auth_security import generate_session_token, hash_secret, mask_email, mask_phone


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def create_parent_session(
    *,
    db: Session,
    settings: Settings,
    account: ParentAccount,
    response: Response,
) -> str:
    token = generate_session_token()
    token_hash = hash_secret(
        token,
        purpose="session-token",
        pepper=settings.auth_secret_pepper,
    )
    parent_session = ParentSession(
        account_id=account.id,
        token_hash=token_hash,
        expires_at=utcnow() + timedelta(days=settings.auth_session_days),
    )
    db.add(parent_session)
    response.set_cookie(
        settings.auth_session_cookie_name,
        token,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return token


def get_session_account(
    *,
    db: Session,
    settings: Settings,
    token: str | None,
) -> tuple[ParentAccount, ParentSession] | None:
    if not token:
        return None

    token_hash = hash_secret(
        token,
        purpose="session-token",
        pepper=settings.auth_secret_pepper,
    )
    parent_session = db.exec(
        select(ParentSession).where(ParentSession.token_hash == token_hash)
    ).first()
    if parent_session is None or parent_session.revoked_at is not None:
        return None
    if _as_utc(parent_session.expires_at) <= utcnow():
        return None

    account = db.get(ParentAccount, parent_session.account_id)
    if account is None or account.status != "active":
        return None
    return account, parent_session


def clear_parent_session(*, response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.auth_session_cookie_name, path="/")


def touch_parent_session(*, db: Session, settings: Settings, parent_session: ParentSession) -> bool:
    threshold = utcnow() - timedelta(minutes=settings.auth_session_last_seen_throttle_minutes)
    if _as_utc(parent_session.last_seen_at) > threshold:
        return False
    parent_session.last_seen_at = utcnow()
    db.add(parent_session)
    return True


def auth_session_payload(*, account: ParentAccount, parent_id: str | None = None) -> dict:
    account_payload = {
        "id": account.id,
        "email_masked": mask_email(account.email_normalized),
        "phone_bound": bool(account.phone_bound_at),
    }
    if account.phone_e164:
        account_payload["phone_masked"] = mask_phone(account.phone_e164)

    payload = {"authenticated": True, "account": account_payload}
    if parent_id:
        payload["parent_id"] = parent_id
    return payload
