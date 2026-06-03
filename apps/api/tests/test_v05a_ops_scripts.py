from pathlib import Path

import pytest


def test_v05a_ops_scripts_exist_and_use_safe_models():
    scripts = {
        "list": Path("app/ops/list_unlinked_alpha_parents.py"),
        "bind": Path("app/ops/bind_parent_account.py"),
        "revoke": Path("app/ops/revoke_parent_sessions.py"),
    }
    for path in scripts.values():
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "ParentAccount" in text
        assert "ParentUser" in text or "ParentSession" in text

    assert "revoked_at" in scripts["revoke"].read_text(encoding="utf-8")
    assert "account_id" in scripts["bind"].read_text(encoding="utf-8")


def test_bind_parent_account_refuses_account_already_linked_to_another_parent():
    text = Path("app/ops/bind_parent_account.py").read_text(encoding="utf-8")

    assert "existing_parent_for_account" in text
    assert "ParentUser.account_id == account.id" in text
    assert "ParentUser.id != parent.id" in text
    assert "already linked to another parent" in text
    assert "SystemExit" in text


def test_revoke_parent_sessions_validates_account_id_target_exists():
    text = Path("app/ops/revoke_parent_sessions.py").read_text(encoding="utf-8")

    assert "session.get(ParentAccount, account_id)" in text
    assert 'SystemExit("account not found")' in text


def test_playwright_alpha_seed_requires_explicit_flag(monkeypatch):
    from app.db import seed_playwright_alpha

    monkeypatch.delenv("PLAYWRIGHT_ALPHA_SEED", raising=False)

    with pytest.raises(SystemExit, match="PLAYWRIGHT_ALPHA_SEED"):
        seed_playwright_alpha._assert_playwright_alpha_seed_is_safe(
            "sqlite:///./playwright-e2e.db"
        )


def test_playwright_alpha_seed_rejects_unsafe_database_urls(monkeypatch):
    from app.db import seed_playwright_alpha

    monkeypatch.setenv("PLAYWRIGHT_ALPHA_SEED", "1")

    with pytest.raises(SystemExit, match="Refusing"):
        seed_playwright_alpha._assert_playwright_alpha_seed_is_safe(
            "postgresql+psycopg://wenlingo:wenlingo@staging-db/wenlingo"
        )
    with pytest.raises(SystemExit, match="Refusing"):
        seed_playwright_alpha._assert_playwright_alpha_seed_is_safe(
            "sqlite:///./latest.db"
        )
    with pytest.raises(SystemExit, match="Refusing") as exc_info:
        seed_playwright_alpha._assert_playwright_alpha_seed_is_safe(
            "postgresql+psycopg://testuser:secret@localhost:5432/wenlingo"
        )

    message = str(exc_info.value)
    assert "secret" not in message
    assert "testuser" not in message
    assert "localhost" not in message
    assert "postgresql+psycopg://testuser:secret@localhost:5432/wenlingo" not in message


def test_playwright_alpha_seed_accepts_disposable_database_urls(monkeypatch):
    from app.db import seed_playwright_alpha

    monkeypatch.setenv("PLAYWRIGHT_ALPHA_SEED", "1")

    seed_playwright_alpha._assert_playwright_alpha_seed_is_safe(
        "sqlite:///./playwright-e2e.db"
    )
    seed_playwright_alpha._assert_playwright_alpha_seed_is_safe(
        "postgresql+psycopg://wenlingo:wenlingo@localhost:5433/wenlingo_test"
    )
    seed_playwright_alpha._assert_playwright_alpha_seed_is_safe(
        "sqlite:////tmp/playwright-e2e.db"
    )
    seed_playwright_alpha._assert_playwright_alpha_seed_is_safe(
        "postgresql+psycopg://wenlingo:wenlingo@127.0.0.1:5433/playwright_e2e"
    )
