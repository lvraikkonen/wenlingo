from pathlib import Path


def test_essay_version_unique_constraint_has_migration():
    versions_dir = Path("app/db/migrations/versions")
    migration_text = "\n".join(path.read_text(encoding="utf-8") for path in versions_dir.glob("*.py"))

    assert "uq_essay_version_label_per_essay" in migration_text
    assert "essayversion" in migration_text
    assert "essay_id" in migration_text
    assert "version_label" in migration_text


def test_quality_spine_logging_fields_have_migration():
    versions_dir = Path("app/db/migrations/versions")
    migration_text = "\n".join(path.read_text(encoding="utf-8") for path in versions_dir.glob("*.py"))

    assert "20260514_quality_spine_logging_fields" in migration_text
    assert "llmcalllog" in migration_text
    assert "essayversion" in migration_text
    assert "raw_response" in migration_text
    assert "prompt_version" in migration_text
    assert "retry_count" in migration_text
    assert "completed_tasks" in migration_text
    assert "skipped_tasks" in migration_text
    assert "duration_seconds" in migration_text
