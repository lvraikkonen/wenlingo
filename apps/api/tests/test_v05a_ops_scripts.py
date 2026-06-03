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
