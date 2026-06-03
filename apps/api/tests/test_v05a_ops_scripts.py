from pathlib import Path


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
