from app.api.deps import get_db_session
from app.domain.models import ParentAccount, utcnow
from app.main import create_app
from app.services.admin_test_account_cleanup import is_test_account_email


def create_admin_client(session, monkeypatch, token: str = "secret"):
    monkeypatch.setenv("ALPHA_ADMIN_TOKEN", token)
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    return app


def add_account(session, email: str, status: str = "active") -> ParentAccount:
    account = ParentAccount(
        email_normalized=email,
        email_verified_at=utcnow(),
        status=status,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def test_test_account_email_allowlist_accepts_only_dev_qa_patterns():
    allowed = [
        "parent@example.com",
        "qa-parent@real-domain.invalid",
        "alpha-test@domain.invalid",
        "dev-family@test.local",
        "playwright-family@wenlingo.local",
    ]
    rejected = [
        "parent@gmail.com",
        "family@qq.com",
        "invited-family@school.example.org",
        "demo@wenlingo.local",
        "devon@gmail.com",
        "contest@school.org",
        "seqa@example.org",
    ]

    for email in allowed:
        assert is_test_account_email(email) is True
    for email in rejected:
        assert is_test_account_email(email) is False
