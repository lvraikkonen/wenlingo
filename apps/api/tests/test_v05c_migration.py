from pathlib import Path


def test_v05c_ai_platform_has_migration():
    migration_path = Path("app/db/migrations/versions/20260617_v05c_ai_platform.py")
    migration_text = migration_path.read_text(encoding="utf-8")

    assert 'revision = "20260617_v05c_ai_platform"' in migration_text
    assert 'down_revision = "20260608_v05b_ai_sentence"' in migration_text
    assert "llmcalllog" in migration_text
    assert "resolved_provider" in migration_text
    assert "resolved_model" in migration_text
    assert "primary_provider" in migration_text
    assert "primary_model" in migration_text
    assert "fallback_provider" in migration_text
    assert "fallback_model" in migration_text
    assert "fallback_reason" in migration_text
    assert "attempt_count" in migration_text
    assert "final_status" in migration_text
    assert "pricing_status" in migration_text
    assert "attempt_summaries" in migration_text
