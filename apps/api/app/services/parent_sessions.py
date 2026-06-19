from dataclasses import dataclass
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
        samesite=settings.auth_session_cookie_samesite,
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


@dataclass(frozen=True)
class RevokeParentSessionResult:
    revoked: bool
    session_id: str


@dataclass(frozen=True)
class RevokeAllParentSessionsResult:
    revoked_session_count: int


@dataclass(frozen=True)
class ParentSessionCleanupResult:
    scanned_count: int
    eligible_count: int
    deleted_count: int
    reason_counts: dict[str, int]
    revoked_cutoff: datetime
    expired_cutoff: datetime


def active_parent_session_statement(account_id: str):
    return select(ParentSession).where(
        ParentSession.account_id == account_id,
        ParentSession.revoked_at.is_(None),
        ParentSession.expires_at > utcnow(),
    )


def active_parent_sessions_for_account(db: Session, account_id: str) -> list[ParentSession]:
    sessions = db.exec(active_parent_session_statement(account_id)).all()
    return sorted(
        sessions,
        key=lambda parent_session: (
            _as_utc(parent_session.last_seen_at),
            _as_utc(parent_session.created_at),
            parent_session.id,
        ),
        reverse=True,
    )


def revoke_parent_session_for_account(
    db: Session,
    account_id: str,
    session_id: str,
) -> RevokeParentSessionResult:
    parent_session = db.get(ParentSession, session_id)
    if parent_session is None or parent_session.account_id != account_id:
        raise LookupError("parent session not found")

    if parent_session.revoked_at is not None or _as_utc(parent_session.expires_at) <= utcnow():
        return RevokeParentSessionResult(revoked=False, session_id=session_id)

    parent_session.revoked_at = utcnow()
    db.add(parent_session)
    db.flush()
    return RevokeParentSessionResult(revoked=True, session_id=session_id)


def revoke_active_parent_sessions_for_account(
    db: Session,
    account_id: str,
) -> RevokeAllParentSessionsResult:
    sessions = active_parent_sessions_for_account(db, account_id)
    now = utcnow()
    for parent_session in sessions:
        parent_session.revoked_at = now
        db.add(parent_session)
    db.flush()
    return RevokeAllParentSessionsResult(revoked_session_count=len(sessions))


def cleanup_parent_sessions(
    *,
    db: Session,
    revoked_retention_days: int,
    expired_retention_days: int,
    execute: bool,
) -> ParentSessionCleanupResult:
    if revoked_retention_days < 0 or expired_retention_days < 0:
        raise ValueError("retention days must be zero or positive")

    now = utcnow()
    revoked_cutoff = now - timedelta(days=revoked_retention_days)
    expired_cutoff = now - timedelta(days=expired_retention_days)
    sessions = db.exec(select(ParentSession)).all()
    eligible: list[ParentSession] = []
    reason_counts: dict[str, int] = {}

    for parent_session in sessions:
        reason = None
        if (
            parent_session.revoked_at is not None
            and _as_utc(parent_session.revoked_at) <= revoked_cutoff
        ):
            reason = "revoked"
        elif _as_utc(parent_session.expires_at) <= expired_cutoff:
            reason = "expired"

        if reason is None:
            continue
        eligible.append(parent_session)
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    if execute:
        for parent_session in eligible:
            db.delete(parent_session)
        db.commit()

    return ParentSessionCleanupResult(
        scanned_count=len(sessions),
        eligible_count=len(eligible),
        deleted_count=len(eligible) if execute else 0,
        reason_counts=reason_counts,
        revoked_cutoff=revoked_cutoff,
        expired_cutoff=expired_cutoff,
    )
