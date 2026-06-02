from datetime import timedelta

import pytest
from sqlmodel import select

from app.core.config import Settings
from app.domain.models import ParentAccount, ParentSession, utcnow
from app.services.auth_security import hash_secret
from app.services.parent_sessions import create_parent_session as issue_parent_session


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    monkeypatch.setenv("AUTH_SESSION_COOKIE_NAME", "wenlingo_parent_session")
    monkeypatch.setenv("AUTH_SESSION_DAYS", "30")
    monkeypatch.setenv("AUTH_SESSION_LAST_SEEN_THROTTLE_MINUTES", "15")
    monkeypatch.setenv("AUTH_SESSION_COOKIE_SECURE", "false")


def create_account(session):
    account = ParentAccount(
        email_normalized="parent@example.com",
        email_verified_at=utcnow(),
        last_login_at=utcnow(),
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def create_parent_session(
    session,
    account,
    token="session-token",
    expires_delta=timedelta(days=30),
    revoked=False,
    last_seen_delta=None,
):
    parent_session = ParentSession(
        account_id=account.id,
        token_hash=hash_secret(token, purpose="session-token", pepper="test-pepper"),
        expires_at=utcnow() + expires_delta,
        revoked_at=utcnow() if revoked else None,
    )
    if last_seen_delta is not None:
        parent_session.last_seen_at = utcnow() + last_seen_delta
    session.add(parent_session)
    session.commit()
    session.refresh(parent_session)
    return parent_session


def test_get_session_returns_unauthenticated_without_cookie(client):
    response = client.get("/api/auth/session")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_get_session_with_valid_cookie_returns_masked_account(client, session):
    account = create_account(session)
    create_parent_session(session, account)
    client.cookies.set("wenlingo_parent_session", "session-token")

    response = client.get("/api/auth/session")

    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert response.json()["account"]["email_masked"] == "pa***@example.com"


def test_get_session_with_expired_cookie_returns_unauthenticated(client, session):
    account = create_account(session)
    create_parent_session(session, account, expires_delta=timedelta(minutes=-1))
    client.cookies.set("wenlingo_parent_session", "session-token")

    response = client.get("/api/auth/session")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_get_session_with_revoked_cookie_returns_unauthenticated(client, session):
    account = create_account(session)
    create_parent_session(session, account, revoked=True)
    client.cookies.set("wenlingo_parent_session", "session-token")

    response = client.get("/api/auth/session")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_get_session_does_not_touch_recent_last_seen_at(client, session):
    account = create_account(session)
    parent_session = create_parent_session(
        session,
        account,
        last_seen_delta=timedelta(minutes=-1),
    )
    original_last_seen_at = parent_session.last_seen_at
    client.cookies.set("wenlingo_parent_session", "session-token")

    response = client.get("/api/auth/session")

    assert response.status_code == 200
    session.refresh(parent_session)
    assert parent_session.last_seen_at == original_last_seen_at


def test_logout_with_valid_cookie_revokes_session_and_clears_cookie(client, session):
    account = create_account(session)
    parent_session = create_parent_session(session, account)
    client.cookies.set("wenlingo_parent_session", "session-token")

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    session.refresh(parent_session)
    assert parent_session.revoked_at is not None
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_create_parent_session_cookie_uses_configured_security_attributes(session):
    account = create_account(session)
    settings = Settings(auth_secret_pepper="test-pepper", auth_session_cookie_secure=True)

    from starlette.responses import Response

    response = Response()
    issue_parent_session(db=session, settings=settings, account=account, response=response)

    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Secure" in set_cookie


def test_patch_account_phone_with_valid_cookie_binds_normalized_phone(client, session):
    account = create_account(session)
    create_parent_session(session, account)
    client.cookies.set("wenlingo_parent_session", "session-token")

    response = client.patch("/api/auth/account/phone", json={"phone": "138 0000 1234"})

    assert response.status_code == 200
    assert response.json() == {"phone_masked": "138****1234", "phone_bound": True}
    stored_account = session.exec(select(ParentAccount).where(ParentAccount.id == account.id)).one()
    assert stored_account.phone_e164 == "+8613800001234"
    assert stored_account.phone_bound_at is not None
    assert stored_account.phone_verified_at is None


def test_patch_account_phone_without_cookie_returns_401(client):
    response = client.patch("/api/auth/account/phone", json={"phone": "138 0000 1234"})

    assert response.status_code == 401
