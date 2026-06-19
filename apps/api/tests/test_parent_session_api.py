from datetime import timedelta

import pytest
from sqlmodel import select

from app.core.config import Settings
from app.domain.models import ParentAccount, ParentSession, ParentUser, utcnow
from app.services.auth_security import hash_secret
from app.services.parent_sessions import (
    active_parent_sessions_for_account,
    cleanup_parent_sessions,
    create_parent_session as issue_parent_session,
    revoke_active_parent_sessions_for_account,
    revoke_parent_session_for_account,
)


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    monkeypatch.setenv("AUTH_SESSION_COOKIE_NAME", "wenlingo_parent_session")
    monkeypatch.setenv("AUTH_SESSION_DAYS", "30")
    monkeypatch.setenv("AUTH_SESSION_LAST_SEEN_THROTTLE_MINUTES", "15")
    monkeypatch.setenv("AUTH_SESSION_COOKIE_SECURE", "false")


def create_account(session, email="parent@example.com"):
    account = ParentAccount(
        email_normalized=email,
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
    session_id=None,
    expires_delta=timedelta(days=30),
    revoked=False,
    last_seen_delta=None,
    created_at=None,
    last_seen_at=None,
):
    parent_session_kwargs = {}
    if session_id is not None:
        parent_session_kwargs["id"] = session_id
    parent_session = ParentSession(
        **parent_session_kwargs,
        account_id=account.id,
        token_hash=hash_secret(token, purpose="session-token", pepper="test-pepper"),
        expires_at=utcnow() + expires_delta,
        revoked_at=utcnow() if revoked else None,
    )
    if created_at is not None:
        parent_session.created_at = created_at
    if last_seen_delta is not None:
        parent_session.last_seen_at = utcnow() + last_seen_delta
    if last_seen_at is not None:
        parent_session.last_seen_at = last_seen_at
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


def test_get_session_fails_closed_for_duplicate_linked_parents(client, session):
    account = create_account(session)
    create_parent_session(session, account)
    session.add(
        ParentUser(
            email="parent-one@example.com",
            display_name="Parent One",
            account_id=account.id,
            account_linked_at=utcnow(),
        )
    )
    session.add(
        ParentUser(
            email="parent-two@example.com",
            display_name="Parent Two",
            account_id=account.id,
            account_linked_at=utcnow(),
        )
    )
    session.commit()
    client.cookies.set("wenlingo_parent_session", "session-token")

    response = client.get("/api/auth/session")

    assert response.status_code == 409


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


def test_create_parent_session_cookie_uses_configured_samesite(session):
    account = create_account(session)
    settings = Settings(
        auth_secret_pepper="test-pepper",
        auth_session_cookie_secure=True,
        auth_session_cookie_samesite="none",
    )

    from starlette.responses import Response

    response = Response()
    issue_parent_session(db=session, settings=settings, account=account, response=response)

    set_cookie = response.headers["set-cookie"]
    assert "SameSite=none" in set_cookie
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


def test_active_parent_sessions_for_account_filters_revoked_and_expired(session):
    account = create_account(session)
    active = create_parent_session(session, account, token="active")
    create_parent_session(session, account, token="revoked", revoked=True)
    create_parent_session(session, account, token="expired", expires_delta=timedelta(minutes=-1))

    rows = active_parent_sessions_for_account(session, account.id)

    assert [row.id for row in rows] == [active.id]


def test_active_parent_sessions_for_account_sorts_descending_and_excludes_other_accounts(session):
    account = create_account(session)
    other_account = create_account(session, email="other-parent@example.com")
    base = utcnow()
    last_seen_tie = base - timedelta(minutes=5)
    created_tie = base - timedelta(minutes=10)
    highest_last_seen = create_parent_session(
        session,
        account,
        token="highest-last-seen",
        session_id="session-a",
        created_at=base - timedelta(hours=1),
        last_seen_at=base - timedelta(minutes=1),
    )
    id_tie_winner = create_parent_session(
        session,
        account,
        token="id-tie-winner",
        session_id="session-c",
        created_at=created_tie,
        last_seen_at=last_seen_tie,
    )
    id_tie_loser = create_parent_session(
        session,
        account,
        token="id-tie-loser",
        session_id="session-b",
        created_at=created_tie,
        last_seen_at=last_seen_tie,
    )
    older_created = create_parent_session(
        session,
        account,
        token="older-created",
        session_id="session-z",
        created_at=base - timedelta(minutes=11),
        last_seen_at=last_seen_tie,
    )
    create_parent_session(
        session,
        other_account,
        token="other-account-active",
        session_id="session-other",
        created_at=base,
        last_seen_at=base,
    )

    rows = active_parent_sessions_for_account(session, account.id)

    assert [row.id for row in rows] == [
        highest_last_seen.id,
        id_tie_winner.id,
        id_tie_loser.id,
        older_created.id,
    ]


def test_revoke_parent_session_for_account_is_idempotent(session):
    account = create_account(session)
    parent_session = create_parent_session(session, account)

    first = revoke_parent_session_for_account(session, account.id, parent_session.id)
    second = revoke_parent_session_for_account(session, account.id, parent_session.id)

    assert first.revoked is True
    assert second.revoked is False
    session.refresh(parent_session)
    assert parent_session.revoked_at is not None


def test_revoke_parent_session_for_account_rejects_wrong_account_without_revoking(session):
    account = create_account(session)
    other_account = create_account(session, email="other-parent@example.com")
    parent_session = create_parent_session(session, account)

    with pytest.raises(LookupError):
        revoke_parent_session_for_account(session, other_account.id, parent_session.id)

    session.refresh(parent_session)
    assert parent_session.revoked_at is None


def test_revoke_active_parent_sessions_for_account_counts_only_active(session):
    account = create_account(session)
    create_parent_session(session, account, token="active-one")
    create_parent_session(session, account, token="active-two")
    create_parent_session(session, account, token="revoked", revoked=True)

    result = revoke_active_parent_sessions_for_account(session, account.id)

    assert result.revoked_session_count == 2
    assert active_parent_sessions_for_account(session, account.id) == []


def test_revoke_parent_session_helpers_do_not_commit_implicitly(session):
    account = create_account(session)
    single_session = create_parent_session(session, account, token="single")

    revoke_parent_session_for_account(session, account.id, single_session.id)
    session.refresh(single_session)
    assert single_session.revoked_at is not None

    session.rollback()
    session.refresh(single_session)
    assert single_session.revoked_at is None

    active_one = create_parent_session(session, account, token="active-one")
    active_two = create_parent_session(session, account, token="active-two")

    revoke_active_parent_sessions_for_account(session, account.id)
    session.refresh(active_one)
    session.refresh(active_two)
    assert active_one.revoked_at is not None
    assert active_two.revoked_at is not None

    session.rollback()
    session.refresh(active_one)
    session.refresh(active_two)
    assert active_one.revoked_at is None
    assert active_two.revoked_at is None


def test_cleanup_parent_sessions_dry_run_and_execute(session):
    account = create_account(session)
    active = create_parent_session(session, account, token="active")
    old_revoked = create_parent_session(session, account, token="old-revoked", revoked=True)
    old_revoked.revoked_at = utcnow() - timedelta(days=45)
    old_expired = create_parent_session(
        session,
        account,
        token="old-expired",
        expires_delta=timedelta(days=-45),
    )
    recent_expired = create_parent_session(
        session,
        account,
        token="recent-expired",
        expires_delta=timedelta(days=-5),
    )
    session.add(old_revoked)
    session.commit()

    dry_run = cleanup_parent_sessions(
        db=session,
        revoked_retention_days=30,
        expired_retention_days=30,
        execute=False,
    )
    assert dry_run.deleted_count == 0
    assert dry_run.eligible_count == 2
    assert session.get(ParentSession, old_revoked.id) is not None

    executed = cleanup_parent_sessions(
        db=session,
        revoked_retention_days=30,
        expired_retention_days=30,
        execute=True,
    )

    assert executed.deleted_count == 2
    assert executed.reason_counts == {"expired": 1, "revoked": 1}
    assert session.get(ParentSession, active.id) is not None
    assert session.get(ParentSession, recent_expired.id) is not None
    assert session.get(ParentSession, old_revoked.id) is None
    assert session.get(ParentSession, old_expired.id) is None


def test_cleanup_parent_sessions_counts_revoked_before_expired_when_both_apply(session):
    account = create_account(session)
    both_revoked_and_expired = create_parent_session(
        session,
        account,
        token="both-revoked-and-expired",
        revoked=True,
        expires_delta=timedelta(days=-45),
    )
    both_revoked_and_expired.revoked_at = utcnow() - timedelta(days=45)
    session.add(both_revoked_and_expired)
    session.commit()

    result = cleanup_parent_sessions(
        db=session,
        revoked_retention_days=30,
        expired_retention_days=30,
        execute=False,
    )

    assert result.eligible_count == 1
    assert result.reason_counts == {"revoked": 1}


@pytest.mark.parametrize(
    ("revoked_retention_days", "expired_retention_days"),
    [
        (-1, 30),
        (30, -1),
    ],
)
def test_cleanup_parent_sessions_rejects_negative_retention_days(
    session,
    revoked_retention_days,
    expired_retention_days,
):
    with pytest.raises(ValueError):
        cleanup_parent_sessions(
            db=session,
            revoked_retention_days=revoked_retention_days,
            expired_retention_days=expired_retention_days,
            execute=False,
        )
