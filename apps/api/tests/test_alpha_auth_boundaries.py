from datetime import timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select
from starlette.requests import Request

from app.core.config import Settings
from app.domain.enums import StudentPersona
from app.domain.models import (
    Essay,
    ParentAccount,
    ParentSession,
    ParentUser,
    StudentProfile,
    utcnow,
)
from app.services.auth_security import hash_secret


def as_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def make_request(method: str, headers: dict[str, str] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/",
            "headers": [
                (name.lower().encode("latin-1"), value.encode("latin-1"))
                for name, value in (headers or {}).items()
            ],
        }
    )


def create_session_family(session, email="parent@example.com", token="token-value"):
    account = ParentAccount(
        email_normalized=email,
        email_verified_at=utcnow(),
        last_login_at=utcnow(),
    )
    session.add(account)
    session.flush()
    parent = ParentUser(
        email=f"alpha-{account.id}@wenlingo.local",
        display_name="Alpha Parent",
        account_id=account.id,
        account_linked_at=utcnow(),
    )
    session.add(parent)
    session.flush()
    child = StudentProfile(
        parent_id=parent.id,
        name="Xiao Wen",
        grade_label="Grade 4",
        persona=StudentPersona.real_child,
        is_real_child=True,
    )
    session.add(child)
    session.add(
        ParentSession(
            account_id=account.id,
            token_hash=hash_secret(
                token,
                purpose="session-token",
                pepper="test-pepper",
            ),
            expires_at=utcnow() + timedelta(days=30),
        )
    )
    session.commit()
    return account, parent, child, token


def test_optional_parent_context_resolves_session_cookie_and_linked_parent(session):
    from app.api.auth_deps import optional_parent_context

    account, parent, _, token = create_session_family(session)

    context = optional_parent_context(
        request=make_request("GET", {"Cookie": f"wenlingo_parent_session={token}"}),
        db=session,
        settings=Settings(auth_secret_pepper="test-pepper"),
    )

    assert context is not None
    assert context.account.id == account.id
    assert context.parent is not None
    assert context.parent.id == parent.id
    assert context.session.account_id == account.id


def test_optional_parent_context_uses_configured_session_cookie_name(session):
    from app.api.auth_deps import optional_parent_context

    account, parent, _, token = create_session_family(
        session,
        email="custom-cookie@example.com",
    )

    context = optional_parent_context(
        request=make_request("GET", {"Cookie": f"custom_parent_session={token}"}),
        db=session,
        settings=Settings(
            auth_secret_pepper="test-pepper",
            auth_session_cookie_name="custom_parent_session",
        ),
    )

    assert context is not None
    assert context.account.id == account.id
    assert context.parent is not None
    assert context.parent.id == parent.id


def test_optional_parent_context_persists_stale_last_seen_touch(session):
    from app.api.auth_deps import optional_parent_context

    _, _, _, token = create_session_family(
        session,
        email="stale-session@example.com",
    )
    token_hash = hash_secret(token, purpose="session-token", pepper="test-pepper")
    parent_session = session.exec(
        select(ParentSession).where(ParentSession.token_hash == token_hash)
    ).one()
    stale_last_seen_at = utcnow() - timedelta(hours=1)
    parent_session.last_seen_at = stale_last_seen_at
    session.add(parent_session)
    session.commit()
    parent_session_id = parent_session.id
    bind = session.get_bind()
    session.close()

    with Session(bind) as auth_session:
        context = optional_parent_context(
            request=make_request("GET", {"Cookie": f"wenlingo_parent_session={token}"}),
            db=auth_session,
            settings=Settings(
                auth_secret_pepper="test-pepper",
                auth_session_last_seen_throttle_minutes=15,
            ),
        )
        assert context is not None

    with Session(bind) as verify_session:
        reloaded = verify_session.get(ParentSession, parent_session_id)

    assert reloaded is not None
    assert as_utc(reloaded.last_seen_at) > as_utc(stale_last_seen_at)


def test_optional_parent_context_does_not_commit_recent_last_seen_touch(
    session,
    monkeypatch,
):
    from app.api.auth_deps import optional_parent_context

    _, _, _, token = create_session_family(
        session,
        email="recent-session@example.com",
    )

    def unexpected_commit():
        raise AssertionError("fresh parent session should not be committed")

    monkeypatch.setattr(session, "commit", unexpected_commit)

    context = optional_parent_context(
        request=make_request("GET", {"Cookie": f"wenlingo_parent_session={token}"}),
        db=session,
        settings=Settings(
            auth_secret_pepper="test-pepper",
            auth_session_last_seen_throttle_minutes=15,
        ),
    )

    assert context is not None


def test_optional_parent_context_fails_closed_for_duplicate_linked_parents(session):
    from app.api.auth_deps import optional_parent_context

    account, _, _, token = create_session_family(
        session,
        email="duplicate-parent@example.com",
    )
    session.add(
        ParentUser(
            email=f"duplicate-{account.id}@wenlingo.local",
            display_name="Duplicate Parent",
            account_id=account.id,
            account_linked_at=utcnow(),
        )
    )
    session.commit()

    with pytest.raises(HTTPException) as exc_info:
        optional_parent_context(
            request=make_request("GET", {"Cookie": f"wenlingo_parent_session={token}"}),
            db=session,
            settings=Settings(auth_secret_pepper="test-pepper"),
        )

    assert exc_info.value.status_code == 409


def test_optional_parent_context_keeps_unlinked_account_parent_none(session):
    from app.api.auth_deps import optional_parent_context

    account = ParentAccount(
        email_normalized="unlinked@example.com",
        email_verified_at=utcnow(),
        last_login_at=utcnow(),
    )
    token = "unlinked-token"
    session.add(account)
    session.flush()
    session.add(
        ParentSession(
            account_id=account.id,
            token_hash=hash_secret(
                token,
                purpose="session-token",
                pepper="test-pepper",
            ),
            expires_at=utcnow() + timedelta(days=30),
        )
    )
    session.commit()

    context = optional_parent_context(
        request=make_request("GET", {"Cookie": f"wenlingo_parent_session={token}"}),
        db=session,
        settings=Settings(auth_secret_pepper="test-pepper"),
    )

    assert context is not None
    assert context.account.id == account.id
    assert context.parent is None


def test_require_parent_context_rejects_missing_session():
    from app.api.auth_deps import require_parent_context

    with pytest.raises(HTTPException) as exc_info:
        require_parent_context(None)

    assert exc_info.value.status_code == 401


def test_require_linked_parent_rejects_unlinked_account(session):
    from app.api.auth_deps import ParentContext, require_linked_parent

    account, _, _, token = create_session_family(session)
    token_hash = hash_secret(token, purpose="session-token", pepper="test-pepper")
    parent_session = session.exec(
        select(ParentSession).where(ParentSession.token_hash == token_hash)
    ).one()

    with pytest.raises(HTTPException) as exc_info:
        require_linked_parent(
            ParentContext(account=account, parent=None, session=parent_session)
        )

    assert exc_info.value.status_code == 404


def test_require_json_state_change_rejects_non_json_body():
    from app.api.auth_deps import require_json_state_change

    request = make_request(
        "POST",
        {"Content-Type": "application/x-www-form-urlencoded"},
    )

    with pytest.raises(HTTPException) as exc_info:
        require_json_state_change(request)

    assert exc_info.value.status_code == 415


def test_require_allowed_origin_rejects_untrusted_origin():
    from app.api.auth_deps import require_allowed_origin

    request = make_request("POST", {"Origin": "https://evil.example"})

    with pytest.raises(HTTPException) as exc_info:
        require_allowed_origin(
            request,
            Settings(auth_allowed_origins="https://wenlingo.example"),
        )

    assert exc_info.value.status_code == 403


def test_parent_authorization_helpers_scope_students_and_essays(session):
    from app.api.auth_deps import require_essay_for_parent, require_student_for_parent

    _, owner, child, _ = create_session_family(
        session,
        email="owner@example.com",
        token="owner-token",
    )
    _, other_parent, other_child, _ = create_session_family(
        session,
        email="other@example.com",
        token="other-token",
    )
    essay = Essay(student_id=child.id, title="My Essay")
    session.add(essay)
    session.commit()

    assert require_student_for_parent(session, owner, child.id).id == child.id
    assert require_essay_for_parent(session, owner, essay.id).id == essay.id
    with pytest.raises(HTTPException) as exc_info:
        require_student_for_parent(session, other_parent, child.id)

    assert exc_info.value.status_code == 404
    with pytest.raises(HTTPException) as essay_exc_info:
        require_essay_for_parent(session, other_parent, essay.id)

    assert essay_exc_info.value.status_code == 404
    assert other_child.parent_id == other_parent.id


def test_legacy_parent_path_ignores_problematic_session_when_auth_disabled(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "false")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    account, parent, child, token = create_session_family(session)
    session.add(
        ParentUser(
            email="duplicate-linked-parent@example.com",
            display_name="Duplicate Parent",
            account_id=account.id,
            account_linked_at=utcnow(),
        )
    )
    session.commit()

    response = client.get(
        f"/api/alpha/parents/{parent.id}/children",
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 200
    assert response.json()["parent"]["id"] == parent.id
    assert [row["id"] for row in response.json()["children"]] == [child.id]


def test_parents_me_children_returns_session_parent_children(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, parent, child, token = create_session_family(session)

    response = client.get(
        "/api/alpha/parents/me/children",
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 200
    assert response.json()["parent"]["id"] == parent.id
    assert [row["id"] for row in response.json()["children"]] == [child.id]


def test_legacy_parent_path_requires_session_when_auth_required(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, parent, _, _ = create_session_family(session)

    response = client.get(f"/api/alpha/parents/{parent.id}/children")

    assert response.status_code == 401
    assert response.json()["detail"] == "parent session required"


def test_legacy_parent_path_rejects_invalid_session_when_auth_required(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, parent, _, _ = create_session_family(session)

    response = client.get(
        f"/api/alpha/parents/{parent.id}/children",
        cookies={"wenlingo_parent_session": "invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "parent session required"


def test_legacy_parent_path_requires_matching_session_parent(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, parent, _, token = create_session_family(session)
    _, other_parent, _, _ = create_session_family(
        session, email="other@example.com", token="other-token"
    )

    response = client.get(
        f"/api/alpha/parents/{other_parent.id}/children",
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 404
