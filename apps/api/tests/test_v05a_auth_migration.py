from pathlib import Path


def test_v05a_alpha_user_foundation_has_additive_migration():
    migration_path = Path(
        "app/db/migrations/versions/20260601_v05a_alpha_user_foundation.py"
    )
    text = migration_path.read_text(encoding="utf-8")

    assert 'revision = "20260601_v05a_user_foundation"' in text
    assert 'down_revision = "20260527_alpha_feedback_obs"' in text
    assert "parentaccount" in text
    assert "authmagiccode" in text
    assert "parentsession" in text
    assert "account_id" in text
    assert "account_linked_at" in text
    assert "email_normalized" in text
    assert "request_ip_hash" in text
    assert "token_hash" in text
    assert "ix_authmagiccode_request_ip_hash" in text
    assert "ix_authmagiccode_alpha_session_id" in text
    assert "ix_parentsession_token_hash" in text
    assert "fk_parentuser_account_id_parentaccount" in text


def test_v05a_migration_does_not_drop_learning_tables():
    migration_path = Path(
        "app/db/migrations/versions/20260601_v05a_alpha_user_foundation.py"
    )
    text = migration_path.read_text(encoding="utf-8")

    assert 'drop_table("studentprofile")' not in text
    assert 'drop_table("assessment")' not in text
    assert 'drop_table("sentencetraining")' not in text
    assert 'drop_table("essay")' not in text
    assert 'drop_table("essayversion")' not in text
    assert 'drop_table("feedbackreaction")' not in text
    assert 'drop_table("parentfeedback")' not in text
