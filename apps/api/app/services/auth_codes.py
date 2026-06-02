import hmac
from datetime import timedelta

from fastapi import HTTPException
from sqlmodel import Session, select

from app.domain.models import AuthMagicCode, ParentAccount, utcnow
from app.services.auth_security import generate_magic_code, hash_secret, normalize_email
from app.services.email_sender import EmailSender

GENERIC_REQUEST_MESSAGE = "如果邮箱可用，我们已经发送验证码。"
GENERIC_VERIFY_ERROR = "验证码无效或已过期。"
RATE_LIMIT_ERROR = "验证码请求过于频繁，请稍后再试。"
_CODE_PURPOSE = "magic-code"
_LOGIN_PURPOSE = "parent_login"
_REQUEST_IP_PURPOSE = "request-ip"


def _require_pepper(settings) -> str:
    pepper = settings.auth_secret_pepper
    if not pepper:
        raise ValueError("auth_secret_pepper is required")
    return pepper


def _ensure_aware_compatible(dt):
    now = utcnow()
    if dt.tzinfo is None:
        return now.replace(tzinfo=None)
    return now


def _is_expired(code: AuthMagicCode) -> bool:
    return code.expires_at <= _ensure_aware_compatible(code.expires_at)


def _rate_limit_count(session: Session, *, field, value: str, since) -> int:
    return len(session.exec(select(AuthMagicCode).where(field == value, AuthMagicCode.created_at >= since)).all())


def _check_rate_limits(
    session: Session,
    *,
    settings,
    email_normalized: str,
    alpha_session_id: str,
    request_ip_hash: str,
):
    now = utcnow()
    ten_minutes_ago = now - timedelta(minutes=10)
    one_hour_ago = now - timedelta(hours=1)

    if _rate_limit_count(
        session,
        field=AuthMagicCode.email_normalized,
        value=email_normalized,
        since=ten_minutes_ago,
    ) >= settings.magic_code_email_rate_limit:
        raise HTTPException(status_code=429, detail=RATE_LIMIT_ERROR)

    if request_ip_hash and _rate_limit_count(
        session,
        field=AuthMagicCode.request_ip_hash,
        value=request_ip_hash,
        since=one_hour_ago,
    ) >= settings.magic_code_ip_rate_limit:
        raise HTTPException(status_code=429, detail=RATE_LIMIT_ERROR)

    if alpha_session_id and _rate_limit_count(
        session,
        field=AuthMagicCode.alpha_session_id,
        value=alpha_session_id,
        since=one_hour_ago,
    ) >= settings.magic_code_alpha_session_rate_limit:
        raise HTTPException(status_code=429, detail=RATE_LIMIT_ERROR)


def request_magic_code(
    session: Session,
    settings,
    email: str,
    alpha_session_id: str,
    request_ip: str | None,
    sender: EmailSender,
) -> dict[str, str]:
    email_normalized = normalize_email(email)
    pepper = _require_pepper(settings)
    alpha_session_id = alpha_session_id or ""
    request_ip_hash = hash_secret(request_ip, purpose=_REQUEST_IP_PURPOSE, pepper=pepper) if request_ip else ""

    _check_rate_limits(
        session,
        settings=settings,
        email_normalized=email_normalized,
        alpha_session_id=alpha_session_id,
        request_ip_hash=request_ip_hash,
    )

    now = utcnow()
    previous_codes = session.exec(
        select(AuthMagicCode).where(
            AuthMagicCode.email_normalized == email_normalized,
            AuthMagicCode.purpose == _LOGIN_PURPOSE,
            AuthMagicCode.consumed_at.is_(None),
        )
    ).all()
    for previous_code in previous_codes:
        previous_code.consumed_at = now
        session.add(previous_code)

    code = "123456" if settings.magic_code_dev_echo else generate_magic_code()
    magic_code = AuthMagicCode(
        email_normalized=email_normalized,
        code_hash=hash_secret(code, purpose=_CODE_PURPOSE, pepper=pepper),
        purpose=_LOGIN_PURPOSE,
        expires_at=now + timedelta(minutes=settings.magic_code_ttl_minutes),
        alpha_session_id=alpha_session_id,
        request_ip_hash=request_ip_hash,
    )
    session.add(magic_code)
    sender.send_magic_code(
        to_email=email_normalized,
        code=code,
        ttl_minutes=settings.magic_code_ttl_minutes,
    )
    session.commit()
    return {"message": GENERIC_REQUEST_MESSAGE}


def _latest_unconsumed_code(session: Session, email_normalized: str) -> AuthMagicCode | None:
    return session.exec(
        select(AuthMagicCode)
        .where(
            AuthMagicCode.email_normalized == email_normalized,
            AuthMagicCode.purpose == _LOGIN_PURPOSE,
            AuthMagicCode.consumed_at.is_(None),
        )
        .order_by(AuthMagicCode.created_at.desc())
    ).first()


def _reject_code(session: Session, magic_code: AuthMagicCode | None, settings):
    if magic_code is not None:
        now = utcnow()
        magic_code.attempt_count += 1
        magic_code.last_attempt_at = now
        if magic_code.attempt_count >= settings.magic_code_max_attempts:
            magic_code.consumed_at = now
        session.add(magic_code)
        session.commit()
    raise HTTPException(status_code=400, detail=GENERIC_VERIFY_ERROR)


def verify_magic_code(session: Session, settings, email: str, code: str) -> ParentAccount:
    email_normalized = normalize_email(email)
    pepper = _require_pepper(settings)
    magic_code = _latest_unconsumed_code(session, email_normalized)

    if magic_code is None:
        _reject_code(session, None, settings)
    if magic_code.attempt_count >= settings.magic_code_max_attempts or _is_expired(magic_code):
        _reject_code(session, magic_code, settings)

    submitted_hash = hash_secret(code, purpose=_CODE_PURPOSE, pepper=pepper)
    if not hmac.compare_digest(submitted_hash, magic_code.code_hash):
        _reject_code(session, magic_code, settings)

    now = utcnow()
    account = session.exec(
        select(ParentAccount).where(ParentAccount.email_normalized == email_normalized)
    ).first()
    if account is None:
        account = ParentAccount(email_normalized=email_normalized, email_verified_at=now)
    elif account.email_verified_at is None:
        account.email_verified_at = now
    account.last_login_at = now
    account.updated_at = now
    magic_code.consumed_at = now
    session.add(account)
    session.add(magic_code)
    return account

