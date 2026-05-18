from pathlib import Path


def test_essay_version_unique_constraint_has_migration():
    versions_dir = Path("app/db/migrations/versions")
    migration_text = "\n".join(path.read_text(encoding="utf-8") for path in versions_dir.glob("*.py"))

    assert "uq_essay_version_label_per_essay" in migration_text
    assert "essayversion" in migration_text
    assert "essay_id" in migration_text
    assert "version_label" in migration_text


def test_quality_spine_logging_fields_have_migration():
    migration_path = Path(
        "app/db/migrations/versions/20260514_quality_spine_logging_fields.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "20260514_quality_spine_logging_fields" in migration_text
    assert 'down_revision = "20260507_essay_version_uniqueness"' in migration_text
    assert "llmcalllog" in migration_text
    assert "essayversion" in migration_text
    assert "raw_response" in migration_text
    assert "prompt_version" in migration_text
    assert "retry_count" in migration_text
    assert "completed_tasks" in migration_text
    assert "skipped_tasks" in migration_text
    assert "duration_seconds" in migration_text
    assert "fk_essayversion_llm_call_log_id_llmcalllog" in migration_text
    assert "create_foreign_key" in migration_text
    assert "drop_constraint" in migration_text
    assert "ix_essayversion_llm_call_log_id" in migration_text


def test_family_test_llm_student_usage_has_migration():
    versions_dir = Path("app/db/migrations/versions")
    migration_text = "\n".join(path.read_text(encoding="utf-8") for path in versions_dir.glob("*.py"))

    assert "20260515_family_test_llm_student_usage" in migration_text
    assert "llmcalllog" in migration_text
    assert "student_id" in migration_text
    assert "task_name" in migration_text
