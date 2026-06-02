from datetime import timedelta
import json

from sqlmodel import select

from app.api.routes.alpha import hash_invite_code
from app.domain.models import (
    AlphaInviteCode,
    ParentAccount,
    ParentSession,
    ParentUser,
    ProductEvent,
    utcnow,
)
from app.services.auth_security import hash_secret


def create_verified_session(session, token="token-value"):
    account = ParentAccount(email_normalized="parent@example.com", email_verified_at=utcnow())
    session.add(account)
    session.flush()
    session.add(
        ParentSession(
            account_id=account.id,
            token_hash=hash_secret(token, purpose="session-token", pepper="test-pepper"),
            expires_at=utcnow() + timedelta(days=30),
        )
    )
    session.commit()
    return account, token


def create_unverified_session(session, token="token-value"):
    account = ParentAccount(
        email_normalized="parent@example.com",
        email_verified_at=None,
    )
    session.add(account)
    session.flush()
    session.add(
        ParentSession(
            account_id=account.id,
            token_hash=hash_secret(token, purpose="session-token", pepper="test-pepper"),
            expires_at=utcnow() + timedelta(days=30),
        )
    )
    session.commit()
    return account, token


def create_alpha_parent_without_account(
    session,
    email="alpha-legacy@wenlingo.local",
    code="ALPHA-LEGACY",
):
    parent = ParentUser(email=email, display_name="Legacy 家长")
    session.add(parent)
    session.flush()
    invite = AlphaInviteCode(
        code_hash=hash_invite_code(code),
        label="Legacy",
        status="consumed",
        consumed_by_parent_id=parent.id,
        consumed_at=utcnow(),
    )
    session.add(invite)
    session.commit()
    return parent


def test_legacy_bind_links_unlinked_alpha_parent(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    account, token = create_verified_session(session)
    parent = create_alpha_parent_without_account(session)

    response = client.post(
        "/api/alpha/legacy-parent-bind",
        json={"legacy_parent_id": parent.id},
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 200
    session.refresh(parent)
    assert parent.account_id == account.id
    assert parent.account_linked_at is not None
    event = session.exec(
        select(ProductEvent).where(
            ProductEvent.event_type == "legacy_parent_account_bound"
        )
    ).one()
    assert event.parent_id == parent.id


def test_legacy_bind_rejects_non_alpha_parent(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, token = create_verified_session(session)
    parent = ParentUser(email="plain@example.com", display_name="Plain")
    session.add(parent)
    session.commit()

    response = client.post(
        "/api/alpha/legacy-parent-bind",
        json={"legacy_parent_id": parent.id},
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 404


def test_legacy_bind_conflict_does_not_reveal_other_email(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, token = create_verified_session(session)
    other = ParentAccount(email_normalized="other@example.com", email_verified_at=utcnow())
    session.add(other)
    session.flush()
    parent = create_alpha_parent_without_account(session)
    parent.account_id = other.id
    parent.account_linked_at = utcnow()
    session.add(parent)
    session.commit()

    response = client.post(
        "/api/alpha/legacy-parent-bind",
        json={"legacy_parent_id": parent.id},
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "这个家庭已经绑定过账号，请联系邀请人处理。"
    assert "other@example.com" not in response.text
    assert session.exec(
        select(ProductEvent).where(
            ProductEvent.event_type == "legacy_parent_account_bound"
        )
    ).all() == []


def test_legacy_bind_rejects_account_already_linked_to_another_parent(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    account, token = create_verified_session(session)
    first_parent = create_alpha_parent_without_account(session)
    second_parent = create_alpha_parent_without_account(
        session,
        email="alpha-legacy-second@wenlingo.local",
        code="ALPHA-LEGACY-SECOND",
    )

    first_response = client.post(
        "/api/alpha/legacy-parent-bind",
        json={"legacy_parent_id": first_parent.id},
        cookies={"wenlingo_parent_session": token},
    )
    second_response = client.post(
        "/api/alpha/legacy-parent-bind",
        json={"legacy_parent_id": second_parent.id},
        cookies={"wenlingo_parent_session": token},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "这个家庭已经绑定过账号，请联系邀请人处理。"
    session.refresh(first_parent)
    session.refresh(second_parent)
    assert first_parent.account_id == account.id
    assert second_parent.account_id is None
    events = session.exec(
        select(ProductEvent).where(
            ProductEvent.event_type == "legacy_parent_account_bound"
        )
    ).all()
    assert [event.parent_id for event in events] == [first_parent.id]


def test_legacy_bind_is_unavailable_when_alpha_auth_disabled(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "false")
    parent = create_alpha_parent_without_account(session)

    response = client.post(
        "/api/alpha/legacy-parent-bind",
        json={"legacy_parent_id": parent.id},
    )

    assert response.status_code == 404


def test_legacy_bind_requires_session_when_alpha_auth_enabled(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    parent = create_alpha_parent_without_account(session)

    response = client.post(
        "/api/alpha/legacy-parent-bind",
        json={"legacy_parent_id": parent.id},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "parent session required"


def test_legacy_bind_requires_verified_email_session(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, token = create_unverified_session(session)
    parent = create_alpha_parent_without_account(session)

    response = client.post(
        "/api/alpha/legacy-parent-bind",
        json={"legacy_parent_id": parent.id},
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "verified parent session required"


def test_legacy_bind_requires_json_body(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, token = create_verified_session(session)
    parent = create_alpha_parent_without_account(session)

    response = client.post(
        "/api/alpha/legacy-parent-bind",
        content=json.dumps({"legacy_parent_id": parent.id}),
        headers={"Content-Type": "text/plain"},
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "JSON body required"


def test_legacy_bind_rejects_bad_origin(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "https://wenlingo.example")
    _, token = create_verified_session(session)
    parent = create_alpha_parent_without_account(session)

    response = client.post(
        "/api/alpha/legacy-parent-bind",
        json={"legacy_parent_id": parent.id},
        headers={"Origin": "https://evil.example"},
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "origin not allowed"
