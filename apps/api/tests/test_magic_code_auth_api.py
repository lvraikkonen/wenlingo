from datetime import timedelta

import pytest
from sqlmodel import select

from app.domain.models import AuthMagicCode, ParentAccount, ProductEvent, utcnow
from app.services.auth_security import hash_secret

GENERIC_REQUEST_MESSAGE = "如果邮箱可用，我们已经发送验证码。"
GENERIC_VERIFY_ERROR = "验证码无效或已过期。"
RATE_LIMIT_ERROR = "验证码请求过于频繁，请稍后再试。"


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    monkeypatch.setenv("MAGIC_CODE_DEV_ECHO", "true")
    monkeypatch.setenv("MAGIC_CODE_TTL_MINUTES", "10")


def _request_code(client, email=" Parent@Example.COM ", alpha_session_id="alpha-1"):
    return client.post(
        "/api/auth/magic-codes/request",
        json={"email": email, "alpha_session_id": alpha_session_id},
    )


def _stored_codes(session):
    return session.exec(select(AuthMagicCode)).all()


def _insert_code(
    session,
    *,
    email="parent@example.com",
    code="123456",
    expires_delta=timedelta(minutes=10),
    consumed=False,
    attempt_count=0,
):
    magic_code = AuthMagicCode(
        email_normalized=email,
        code_hash=hash_secret(code, purpose="magic-code", pepper="test-pepper"),
        purpose="parent_login",
        expires_at=utcnow() + expires_delta,
        consumed_at=utcnow() if consumed else None,
        attempt_count=attempt_count,
    )
    session.add(magic_code)
    session.commit()
    session.refresh(magic_code)
    return magic_code


def test_request_magic_code_returns_generic_message_and_stores_hashed_normalized_code(client, session):
    response = _request_code(client)

    assert response.status_code == 200
    assert response.json() == {"message": GENERIC_REQUEST_MESSAGE}
    codes = _stored_codes(session)
    assert len(codes) == 1
    assert codes[0].email_normalized == "parent@example.com"
    assert codes[0].code_hash != "123456"
    assert "123456" not in codes[0].code_hash
    assert codes[0].purpose == "parent_login"


def test_request_response_is_identical_for_existing_and_new_email(client, session):
    existing = ParentAccount(email_normalized="parent@example.com", email_verified_at=utcnow())
    session.add(existing)
    session.commit()

    existing_response = _request_code(client, "parent@example.com")
    new_response = _request_code(client, "new@example.com")

    assert existing_response.status_code == 200
    assert new_response.status_code == 200
    assert existing_response.json() == {"message": GENERIC_REQUEST_MESSAGE}
    assert existing_response.json() == new_response.json()


def test_request_magic_code_rate_limits_same_email_after_three_requests(client):
    for _ in range(3):
        response = _request_code(client, "parent@example.com")
        assert response.status_code == 200

    response = _request_code(client, "parent@example.com")

    assert response.status_code == 429
    assert response.json() == {"detail": RATE_LIMIT_ERROR}


def test_request_magic_code_rejects_invalid_email_without_server_error(client):
    response = _request_code(client, "not-an-email")

    assert response.status_code == 422


def test_request_magic_code_rate_limits_same_ip_after_twenty_requests(client):
    for index in range(20):
        response = _request_code(
            client,
            f"parent-{index}@example.com",
            alpha_session_id=f"alpha-{index}",
        )
        assert response.status_code == 200

    response = _request_code(client, "parent-20@example.com", alpha_session_id="alpha-20")

    assert response.status_code == 429
    assert response.json() == {"detail": RATE_LIMIT_ERROR}


def test_request_magic_code_rate_limits_same_alpha_session_after_five_requests(client):
    for index in range(5):
        response = _request_code(
            client,
            f"parent-{index}@example.com",
            alpha_session_id="same-alpha",
        )
        assert response.status_code == 200

    response = _request_code(client, "parent-5@example.com", alpha_session_id="same-alpha")

    assert response.status_code == 429
    assert response.json() == {"detail": RATE_LIMIT_ERROR}


def test_verify_magic_code_creates_account_masks_email_and_sets_session_cookie(client, session):
    _insert_code(session)

    response = client.post(
        "/api/auth/magic-codes/verify",
        json={"email": " Parent@Example.COM ", "code": "123456"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    assert body["account"]["email_masked"] == "pa***@example.com"
    assert response.cookies.get("wenlingo_parent_session")
    account = session.exec(
        select(ParentAccount).where(ParentAccount.email_normalized == "parent@example.com")
    ).one()
    assert account.email_verified_at is not None
    assert account.last_login_at is not None


@pytest.mark.parametrize(
    ("case", "code_kwargs", "submitted_code"),
    [
        ("missing", None, "123456"),
        ("wrong", {}, "000000"),
        ("expired", {"expires_delta": timedelta(minutes=-1)}, "123456"),
        ("consumed", {"consumed": True}, "123456"),
    ],
)
def test_verify_magic_code_rejects_expired_consumed_missing_and_wrong_codes(
    client, session, case, code_kwargs, submitted_code
):
    if code_kwargs is not None:
        _insert_code(session, **code_kwargs)

    response = client.post(
        "/api/auth/magic-codes/verify",
        json={"email": "parent@example.com", "code": submitted_code},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": GENERIC_VERIFY_ERROR}


def test_wrong_code_on_fourth_attempt_increments_to_five_and_consumes_code(client, session):
    magic_code = _insert_code(session, attempt_count=4)

    response = client.post(
        "/api/auth/magic-codes/verify",
        json={"email": "parent@example.com", "code": "000000"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": GENERIC_VERIFY_ERROR}
    session.refresh(magic_code)
    assert magic_code.attempt_count == 5
    assert magic_code.consumed_at is not None
