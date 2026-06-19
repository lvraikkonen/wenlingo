from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_db_session
from app.api.routes import admin_alpha as admin_alpha_routes
from app.domain.enums import StudentPersona
from app.domain.models import (
    AlphaInviteCode,
    ParentAccount,
    ParentSession,
    ParentUser,
    StudentProfile,
    utcnow,
)
from app.domain.seed import seed_demo_data
from app.main import create_app


def create_admin_client(session, monkeypatch, token: str = "secret"):
    monkeypatch.setenv("ALPHA_ADMIN_TOKEN", token)
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "https://wenlingo.example")
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    return app


def admin_headers(token="secret", origin="https://wenlingo.example"):
    return {
        "X-Alpha-Admin-Token": token,
        "Origin": origin,
        "Content-Type": "application/json",
    }


def test_admin_alpha_split_preserves_route_paths(session, monkeypatch):
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        overview = client.get(
            "/api/admin/alpha/overview",
            headers={"X-Alpha-Admin-Token": "secret"},
        )
        accounts = client.get(
            "/api/admin/alpha/accounts",
            headers={"X-Alpha-Admin-Token": "secret"},
        )

    assert overview.status_code == 200
    assert "families" in overview.json()
    assert accounts.status_code == 200
    assert "accounts" in accounts.json()


def test_admin_invite_generation_returns_raw_codes_once_and_stores_hashes(session, monkeypatch):
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/api/admin/alpha/invites",
            headers=admin_headers(),
            json={"count": 2, "label_prefix": "Alpha QA", "issued_to_note": "June QA"},
        )

    assert response.status_code == 201
    body = response.json()
    assert len(body["invites"]) == 2
    assert body["invites"][0]["raw_code"].startswith("ALPHA-")
    assert body["invites"][0]["label"] == "Alpha QA 01"
    assert body["invites"][1]["label"] == "Alpha QA 02"
    persisted = session.exec(select(AlphaInviteCode)).all()
    assert len(persisted) == 2
    assert all(invite.status == "issued" for invite in persisted)
    assert all(body["invites"][0]["raw_code"] != invite.code_hash for invite in persisted)
    assert all(invite.issued_to_note == "June QA" for invite in persisted)


def test_admin_invite_generation_retries_existing_and_batch_code_collisions(session, monkeypatch):
    duplicate_raw_code = "ALPHA-DUPLICATE"
    session.add(
        AlphaInviteCode(
            code_hash=admin_alpha_routes.hash_invite_code(duplicate_raw_code),
            label="Already Issued",
            status="issued",
        )
    )
    session.commit()
    generated_codes = iter(
        [
            duplicate_raw_code,
            "ALPHA-UNIQUE-ONE",
            "ALPHA-UNIQUE-ONE",
            "ALPHA-UNIQUE-TWO",
        ]
    )
    monkeypatch.setattr(
        admin_alpha_routes,
        "_generate_invite_code",
        lambda: next(generated_codes),
    )
    app = create_admin_client(session, monkeypatch)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/admin/alpha/invites",
            headers=admin_headers(),
            json={"count": 2, "label_prefix": "Alpha QA"},
        )

    assert response.status_code == 201
    raw_codes = [invite["raw_code"] for invite in response.json()["invites"]]
    assert raw_codes == ["ALPHA-UNIQUE-ONE", "ALPHA-UNIQUE-TWO"]
    persisted_hashes = [invite.code_hash for invite in session.exec(select(AlphaInviteCode)).all()]
    assert admin_alpha_routes.hash_invite_code(duplicate_raw_code) in persisted_hashes
    assert admin_alpha_routes.hash_invite_code("ALPHA-UNIQUE-ONE") in persisted_hashes
    assert admin_alpha_routes.hash_invite_code("ALPHA-UNIQUE-TWO") in persisted_hashes


def test_admin_invite_generation_enforces_count_bounds(session, monkeypatch):
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        low = client.post(
            "/api/admin/alpha/invites",
            headers=admin_headers(),
            json={"count": 0, "label_prefix": "Alpha QA"},
        )
        high = client.post(
            "/api/admin/alpha/invites",
            headers=admin_headers(),
            json={"count": 21, "label_prefix": "Alpha QA"},
        )

    assert low.status_code == 422
    assert high.status_code == 422


def test_admin_write_endpoints_require_json_and_allowed_origin(session, monkeypatch):
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        bad_content_type = client.post(
            "/api/admin/alpha/invites",
            headers={
                "X-Alpha-Admin-Token": "secret",
                "Origin": "https://wenlingo.example",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            content="count=1",
        )
        bad_origin = client.post(
            "/api/admin/alpha/invites",
            headers=admin_headers(origin="https://evil.example"),
            json={"count": 1, "label_prefix": "Alpha QA"},
        )

    assert bad_content_type.status_code == 415
    assert bad_origin.status_code == 403


def test_admin_can_revoke_only_unconsumed_issued_invite(session, monkeypatch):
    issued = AlphaInviteCode(code_hash="issued-hash", label="Issued", status="issued")
    consumed = AlphaInviteCode(
        code_hash="consumed-hash",
        label="Consumed",
        status="consumed",
        consumed_by_parent_id="parent-1",
        consumed_at=utcnow(),
    )
    revoked = AlphaInviteCode(code_hash="revoked-hash", label="Revoked", status="revoked")
    session.add(issued)
    session.add(consumed)
    session.add(revoked)
    session.commit()
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        issued_response = client.post(
            f"/api/admin/alpha/invites/{issued.id}/revoke",
            headers=admin_headers(),
            json={},
        )
        consumed_response = client.post(
            f"/api/admin/alpha/invites/{consumed.id}/revoke",
            headers=admin_headers(),
            json={},
        )
        revoked_response = client.post(
            f"/api/admin/alpha/invites/{revoked.id}/revoke",
            headers=admin_headers(),
            json={},
        )

    assert issued_response.status_code == 200
    assert issued_response.json()["invite"]["status"] == "revoked"
    assert consumed_response.status_code == 409
    assert revoked_response.status_code == 409


def test_admin_accounts_list_masks_email_and_counts_active_sessions(session, monkeypatch):
    login_at = utcnow()
    account = ParentAccount(
        email_normalized="parent@example.com",
        email_verified_at=utcnow(),
        last_login_at=login_at,
    )
    session.add(account)
    session.flush()
    parent = ParentUser(email="legacy@example.com", display_name="Alpha Parent", account_id=account.id)
    session.add(parent)
    session.add(
        StudentProfile(
            parent_id=parent.id,
            name="Alpha Child One",
            persona=StudentPersona.real_child,
        )
    )
    session.add(
        StudentProfile(
            parent_id=parent.id,
            name="Alpha Child Two",
            persona=StudentPersona.real_child,
        )
    )
    session.add(
        ParentSession(
            account_id=account.id,
            token_hash="active",
            expires_at=utcnow() + timedelta(days=1),
        )
    )
    session.add(
        ParentSession(
            account_id=account.id,
            token_hash="revoked",
            expires_at=utcnow() + timedelta(days=1),
            revoked_at=utcnow(),
        )
    )
    session.commit()
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.get("/api/admin/alpha/accounts", headers={"X-Alpha-Admin-Token": "secret"})

    assert response.status_code == 200
    row = response.json()["accounts"][0]
    assert row["account_id"] == account.id
    assert row["email_masked"] == "pa***@example.com"
    assert row["status"] == "active"
    assert row["parent_id"] == parent.id
    assert row["parent_display_name"] == "Alpha Parent"
    assert row["children_count"] == 2
    assert row["active_session_count"] == 1
    assert row["created_at"] == account.created_at.isoformat()
    assert row["last_login_at"] == account.last_login_at.isoformat()
    assert "parent@example.com" not in str(response.json())


def test_admin_lists_active_sessions_without_token_hash(session, monkeypatch):
    account = ParentAccount(email_normalized="parent@example.com", email_verified_at=utcnow())
    session.add(account)
    session.flush()
    active = ParentSession(
        account_id=account.id,
        token_hash="secret-token-hash",
        expires_at=utcnow() + timedelta(days=1),
    )
    revoked = ParentSession(
        account_id=account.id,
        token_hash="revoked-token-hash",
        expires_at=utcnow() + timedelta(days=1),
        revoked_at=utcnow(),
    )
    session.add(active)
    session.add(revoked)
    session.commit()
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.get(
            f"/api/admin/alpha/accounts/{account.id}/sessions",
            headers={"X-Alpha-Admin-Token": "secret"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["account"]["account_id"] == account.id
    assert body["sessions"][0]["session_id"] == active.id
    assert body["sessions"][0]["revoked_at"] is None
    assert "token_hash" not in body["sessions"][0]
    assert "secret-token-hash" not in response.text
    assert revoked.id not in response.text


def test_admin_revoke_one_session_is_idempotent(session, monkeypatch):
    account = ParentAccount(email_normalized="parent@example.com", email_verified_at=utcnow())
    session.add(account)
    session.flush()
    parent_session = ParentSession(
        account_id=account.id,
        token_hash="active-token-hash",
        expires_at=utcnow() + timedelta(days=1),
    )
    session.add(parent_session)
    session.commit()
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        first = client.post(
            f"/api/admin/alpha/accounts/{account.id}/sessions/{parent_session.id}/revoke",
            headers=admin_headers(),
            json={},
        )
        second = client.post(
            f"/api/admin/alpha/accounts/{account.id}/sessions/{parent_session.id}/revoke",
            headers=admin_headers(),
            json={},
        )

    assert first.status_code == 200
    assert first.json()["session"]["revoked"] is True
    assert second.status_code == 200
    assert second.json()["session"]["revoked"] is False


def test_admin_revoke_all_sessions_revokes_only_active_sessions(session, monkeypatch):
    account = ParentAccount(email_normalized="parent@example.com", email_verified_at=utcnow())
    session.add(account)
    session.flush()
    session.add(
        ParentSession(
            account_id=account.id,
            token_hash="active-one",
            expires_at=utcnow() + timedelta(days=1),
        )
    )
    session.add(
        ParentSession(
            account_id=account.id,
            token_hash="active-two",
            expires_at=utcnow() + timedelta(days=1),
        )
    )
    session.add(
        ParentSession(
            account_id=account.id,
            token_hash="expired",
            expires_at=utcnow() - timedelta(minutes=1),
        )
    )
    session.commit()
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            f"/api/admin/alpha/accounts/{account.id}/sessions/revoke-all",
            headers=admin_headers(),
            json={},
        )

    assert response.status_code == 200
    assert response.json()["account"]["revoked_session_count"] == 2


def test_admin_disable_revokes_sessions_and_enable_restores_status(session, monkeypatch):
    account = ParentAccount(email_normalized="parent@example.com", email_verified_at=utcnow())
    session.add(account)
    session.flush()
    active_session = ParentSession(
        account_id=account.id,
        token_hash="active",
        expires_at=utcnow() + timedelta(days=1),
    )
    session.add(active_session)
    session.commit()
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        disable = client.post(
            f"/api/admin/alpha/accounts/{account.id}/disable",
            headers=admin_headers(),
            json={},
        )
        enable = client.post(
            f"/api/admin/alpha/accounts/{account.id}/enable",
            headers=admin_headers(),
            json={},
        )

    assert disable.status_code == 200
    assert disable.json()["account"]["revoked_session_count"] == 1
    session.refresh(account)
    session.refresh(active_session)
    assert active_session.revoked_at is not None
    assert enable.status_code == 200
    assert session.get(ParentAccount, account.id).status == "active"


def test_admin_disable_refuses_demo_parent_account_shape(session, monkeypatch):
    demo_parent = seed_demo_data(session)
    account = ParentAccount(
        email_normalized="demo@wenlingo.local",
        email_verified_at=utcnow(),
    )
    session.add(account)
    session.flush()
    demo_parent.account_id = account.id
    session.add(demo_parent)
    session.commit()
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            f"/api/admin/alpha/accounts/{account.id}/disable",
            headers=admin_headers(),
            json={},
        )
        demo_login = client.post("/api/auth/demo-login")

    assert response.status_code == 409
    assert session.get(ParentAccount, account.id).status == "active"
    assert demo_login.status_code == 200


def test_admin_overview_hides_revoked_invites_by_default(session, monkeypatch):
    issued = AlphaInviteCode(code_hash="issued-overview-hash", label="Issued", status="issued")
    revoked = AlphaInviteCode(
        code_hash="revoked-overview-hash",
        label="Revoked",
        status="revoked",
    )
    session.add(issued)
    session.add(revoked)
    session.commit()
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.get(
            "/api/admin/alpha/overview",
            headers={"X-Alpha-Admin-Token": "secret"},
        )

    assert response.status_code == 200
    invite_ids = [row["invite_id"] for row in response.json()["families"]]
    assert invite_ids == [issued.id]


def test_admin_overview_can_include_revoked_invites(session, monkeypatch):
    issued = AlphaInviteCode(code_hash="issued-include-hash", label="Issued", status="issued")
    revoked = AlphaInviteCode(
        code_hash="revoked-include-hash",
        label="Revoked",
        status="revoked",
    )
    session.add(issued)
    session.add(revoked)
    session.commit()
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.get(
            "/api/admin/alpha/overview?include_revoked=true",
            headers={"X-Alpha-Admin-Token": "secret"},
        )

    assert response.status_code == 200
    statuses = [row["invite_status"] for row in response.json()["families"]]
    assert statuses == ["issued", "revoked"]
