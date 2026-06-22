from datetime import timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select
from starlette.requests import Request

from app.api.routes import alpha as alpha_routes
from app.api.routes.alpha import hash_invite_code
from app.core.config import Settings
from app.domain.enums import StudentPersona
from app.domain.models import (
    AbilityProfile,
    AlphaInviteCode,
    Essay,
    ParentAccount,
    ParentSession,
    ParentUser,
    StudentProfile,
    utcnow,
)
from app.services.auth_security import hash_secret
from tests.conftest import (
    create_authenticated_family,
    create_second_authenticated_family,
)


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
    session.add(AbilityProfile(student_id=child.id))
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


def create_verified_session(session, email="verified@example.com", token="verified-token"):
    account = ParentAccount(
        email_normalized=email,
        email_verified_at=utcnow(),
        last_login_at=utcnow(),
    )
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
    return account, token


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


def test_session_parent_children_includes_bound_phone_account_payload(session):
    account, parent, _, _ = create_session_family(session)
    account.phone_e164 = "+8613800001234"
    account.phone_bound_at = utcnow()
    session.add(account)
    session.commit()

    payload = alpha_routes._children_payload(parent, session)

    assert payload["account"] == {
        "email_masked": "pa***@example.com",
        "phone_bound": True,
        "phone_masked": "138****1234",
    }


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


def test_prewriting_routes_reject_cross_family_access(session, client, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    first = create_authenticated_family(session)
    second = create_second_authenticated_family(session)

    start = client.post(
        f"/api/students/{second['student'].id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
        cookies=first["cookie"],
        headers={"origin": "http://testserver"},
    )
    assert start.status_code == 404

    own_start = client.post(
        f"/api/students/{second['student'].id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
        cookies=second["cookie"],
        headers={"origin": "http://testserver"},
    )
    assert own_start.status_code == 201
    essay_id = own_start.json()["essay"]["id"]

    blocked = client.post(
        f"/api/essays/{essay_id}/topic-analysis",
        json={},
        cookies=first["cookie"],
        headers={"origin": "http://testserver"},
    )
    assert blocked.status_code == 404


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


def test_parents_me_children_post_creates_session_parent_child(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, parent, _, token = create_session_family(session)

    response = client.post(
        "/api/alpha/parents/me/children",
        json={"nickname": "Session Child", "grade": 4},
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 201
    child_id = response.json()["child"]["id"]
    child = session.get(StudentProfile, child_id)
    assert child is not None
    assert child.parent_id == parent.id


def test_parents_me_child_summary_returns_session_parent_summary(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, parent, child, token = create_session_family(session)

    response = client.get(
        f"/api/alpha/parents/me/children/{child.id}/summary",
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 200
    assert response.json()["parent_id"] == parent.id
    assert response.json()["child"]["id"] == child.id


def test_parents_me_child_summary_feedback_uses_session_parent(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, parent, child, token = create_session_family(session)

    response = client.post(
        f"/api/alpha/parents/me/children/{child.id}/summary-feedback",
        json={"usefulness": "helpful"},
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 201
    assert response.json()["feedback"]["parent_id"] == parent.id
    assert response.json()["feedback"]["student_id"] == child.id
    assert response.json()["feedback"]["usefulness"] == "helpful"


def test_legacy_parent_path_requires_session_when_auth_required(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, parent, _, _ = create_session_family(session)

    response = client.get(f"/api/alpha/parents/{parent.id}/children")

    assert response.status_code == 401
    assert response.json()["detail"] == "parent session required"


def test_legacy_parent_summary_requires_session_when_auth_required(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, parent, child, _ = create_session_family(session)

    response = client.get(
        f"/api/alpha/parents/{parent.id}/children/{child.id}/summary",
    )

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


def test_legacy_parent_summary_feedback_rejects_cross_family_session(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, _, _, token = create_session_family(session)
    _, other_parent, other_child, _ = create_session_family(
        session, email="feedback-other@example.com", token="feedback-other-token"
    )

    response = client.post(
        f"/api/alpha/parents/{other_parent.id}/children/{other_child.id}/summary-feedback",
        json={"usefulness": "helpful"},
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 404


def test_student_dashboard_requires_session_in_auth_mode(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    _, _, child, _ = create_session_family(session)

    response = client.get(f"/api/students/{child.id}/dashboard")

    assert response.status_code == 401


@pytest.mark.parametrize(
    "cookies",
    [
        None,
        {"wenlingo_parent_session": "invalid-token"},
    ],
)
def test_student_dashboard_requires_session_before_student_lookup(
    client, monkeypatch, cookies
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")

    response = client.get(
        "/api/students/nonexistent-student/dashboard",
        cookies=cookies,
    )

    assert response.status_code == 401


def test_student_dashboard_hides_cross_family_child(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, _, _, token = create_session_family(session)
    _, _, other_child, _ = create_session_family(
        session, email="other@example.com", token="other-token"
    )

    response = client.get(
        f"/api/students/{other_child.id}/dashboard",
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 404


def test_essay_revision_requires_session_before_essay_lookup(client, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")

    response = client.post(
        "/api/essays/nonexistent-essay/revision",
        json={
            "content": "我学会了骑车。刚开始我紧紧抓车把，后来能自己骑过花坛。",
            "completed_tasks": [],
        },
    )

    assert response.status_code == 401


def test_essay_revision_hides_cross_family_essay(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, _, _, token = create_session_family(session)
    _, _, other_child, _ = create_session_family(
        session, email="other@example.com", token="other-token"
    )
    essay_response = client.post(
        f"/api/students/{other_child.id}/essays",
        json={
            "title": "我学会了骑车",
            "draft": "我学会了骑车。刚开始我很害怕。后来爸爸扶着我练，我终于能骑一小段了。",
            "entry": "existing_draft",
        },
        cookies={"wenlingo_parent_session": "other-token"},
    )
    essay_id = essay_response.json()["essay"]["id"]

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json={
            "content": "我学会了骑车。刚开始我紧紧抓车把，后来能自己骑过花坛。",
            "completed_tasks": [],
        },
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 404


def test_student_route_ignores_problematic_session_when_auth_disabled(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "false")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    account, _, child, token = create_session_family(session)
    session.add(
        ParentUser(
            email=f"duplicate-{account.id}@wenlingo.local",
            display_name="Duplicate Parent",
            account_id=account.id,
            account_linked_at=utcnow(),
        )
    )
    session.commit()

    response = client.get(
        f"/api/students/{child.id}/dashboard",
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 200


def test_legacy_state_change_does_not_enforce_auth_json_guard(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "false")
    _, _, child, _ = create_session_family(session)

    response = client.post(
        f"/api/students/{child.id}/readings",
        data="article_id=spring-sounds",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 422


def test_auth_state_change_requires_session_before_json_guard(client, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")

    response = client.post(
        "/api/students/nonexistent-student/readings",
        data="article_id=spring-sounds",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 401


def test_authenticated_alpha_parent_creation_links_current_account_and_consumes_invite(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    account, token = create_verified_session(session)
    invite = AlphaInviteCode(
        code_hash=hash_invite_code("ALPHA-NEW"), label="New", status="issued"
    )
    session.add(invite)
    session.commit()

    response = client.post(
        "/api/alpha/parents",
        json={
            "display_name": "新家长",
            "invite_code": "ALPHA-NEW",
            "alpha_session_id": "session-1",
        },
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 201
    parent = session.get(ParentUser, response.json()["parent"]["id"])
    assert parent.account_id == account.id
    session.refresh(invite)
    assert invite.status == "consumed"
    assert invite.consumed_by_parent_id == parent.id


def test_authenticated_alpha_parent_creation_rejects_account_that_already_has_parent(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    _, _, _, token = create_session_family(session)

    response = client.post(
        "/api/alpha/parents",
        json={"display_name": "重复家长", "invite_code": "ALPHA-ANY"},
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 409


def test_authenticated_alpha_parent_creation_rejects_account_linked_after_context(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    account, token = create_verified_session(
        session, email="race@example.com", token="race-token"
    )
    invite = AlphaInviteCode(
        code_hash=hash_invite_code("ALPHA-RACE"), label="Race", status="issued"
    )
    session.add(invite)
    session.commit()
    original_get_available_invite = alpha_routes._get_available_invite

    def link_account_then_lookup(db, code):
        db.add(
            ParentUser(
                email=f"race-linked-{account.id}@wenlingo.local",
                display_name="Race Linked Parent",
                account_id=account.id,
                account_linked_at=utcnow(),
            )
        )
        db.commit()
        return original_get_available_invite(db, code)

    monkeypatch.setattr(
        alpha_routes, "_get_available_invite", link_account_then_lookup
    )

    response = client.post(
        "/api/alpha/parents",
        json={"display_name": "竞态家长", "invite_code": "ALPHA-RACE"},
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 409
    session.refresh(invite)
    assert invite.status == "issued"
    assert invite.consumed_by_parent_id is None
    linked_parents = session.exec(
        select(ParentUser).where(ParentUser.account_id == account.id)
    ).all()
    assert len(linked_parents) == 1
    assert linked_parents[0].display_name == "Race Linked Parent"


def test_authenticated_alpha_parent_creation_rechecks_linked_parent_before_invite_lookup(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    account, token = create_verified_session(
        session, email="recheck@example.com", token="recheck-token"
    )
    invite = AlphaInviteCode(
        code_hash=hash_invite_code("ALPHA-RECHECK"), label="Recheck", status="issued"
    )
    session.add(invite)
    session.commit()
    original_optional_parent_context = alpha_routes.optional_parent_context
    original_get_available_invite = alpha_routes._get_available_invite
    invite_lookup_called = False

    def resolve_context_then_link_account(request, db, settings):
        context = original_optional_parent_context(
            request=request, db=db, settings=settings
        )
        db.add(
            ParentUser(
                email=f"recheck-linked-{account.id}@wenlingo.local",
                display_name="Recheck Linked Parent",
                account_id=account.id,
                account_linked_at=utcnow(),
            )
        )
        db.commit()
        return context

    def track_invite_lookup(db, code):
        nonlocal invite_lookup_called
        invite_lookup_called = True
        return original_get_available_invite(db, code)

    monkeypatch.setattr(
        alpha_routes, "optional_parent_context", resolve_context_then_link_account
    )
    monkeypatch.setattr(alpha_routes, "_get_available_invite", track_invite_lookup)

    response = client.post(
        "/api/alpha/parents",
        json={"display_name": "复查家长", "invite_code": "ALPHA-RECHECK"},
        cookies={"wenlingo_parent_session": token},
    )

    assert response.status_code == 409
    assert not invite_lookup_called
    session.refresh(invite)
    assert invite.status == "issued"
    assert invite.consumed_by_parent_id is None
