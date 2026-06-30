from pathlib import Path
import re


def test_alembic_revision_ids_fit_default_version_column():
    versions_dir = Path("app/db/migrations/versions")
    revision_ids = []

    for path in versions_dir.glob("*.py"):
        migration_text = path.read_text(encoding="utf-8")
        match = re.search(r'^revision = "([^"]+)"', migration_text, re.MULTILINE)
        if match:
            revision_ids.append((path.name, match.group(1)))

    too_long = [
        f"{name}: {revision_id} ({len(revision_id)})"
        for name, revision_id in revision_ids
        if len(revision_id) > 32
    ]
    assert too_long == []


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

    assert "20260514_quality_spine_logs" in migration_text
    assert 'down_revision = "20260507_essay_version_unique"' in migration_text
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

    assert "20260515_llm_student_usage" in migration_text
    assert "llmcalllog" in migration_text
    assert "student_id" in migration_text
    assert "task_name" in migration_text


def test_ability_history_has_migration():
    migration_path = Path("app/db/migrations/versions/20260520_ability_history.py")
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "abilityhistory" in migration_text
    assert "student_id" in migration_text
    assert "ability_name" in migration_text
    assert "old_value" in migration_text
    assert "new_value" in migration_text
    assert "delta" in migration_text
    assert "source_type" in migration_text
    assert "source_id" in migration_text
    assert "created_at" in migration_text
    assert "ix_abilityhistory_ability_name" in migration_text
    assert "ix_abilityhistory_source_id" in migration_text
    assert "ix_abilityhistory_student_id" in migration_text
    assert "fk_abilityhistory_student_id_studentprofile" in migration_text
    assert 'down_revision = "20260515_llm_student_usage"' in migration_text


def test_assessment_artifact_references_have_migration():
    migration_path = Path("app/db/migrations/versions/20260521_assessment_artifacts.py")
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "20260521_assessment_artifacts" in migration_text
    assert 'down_revision = "20260520_ability_history"' in migration_text
    assert "assessment" in migration_text
    assert "sentence_training_id" in migration_text
    assert "essay_id" in migration_text
    assert "ix_assessment_sentence_training_id" in migration_text
    assert "ix_assessment_essay_id" in migration_text
    assert "fk_assessment_sentence_training_id_sentencetraining" in migration_text
    assert "fk_assessment_essay_id_essay" in migration_text


def test_v05b_ai_sentence_training_has_migration():
    migration_path = Path(
        "app/db/migrations/versions/20260608_v05b_ai_sentence_training.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "20260608_v05b_ai_sentence" in migration_text
    assert 'down_revision = "20260601_v05a_user_foundation"' in migration_text
    assert "sentencetraining" in migration_text
    assert "status" in migration_text
    assert "challenge_prompt" in migration_text
    assert "target_skill" in migration_text
    assert "completed_at" in migration_text
    assert "llmcalllog" in migration_text
    assert "prompt_key" in migration_text
    assert "prompt_tokens" in migration_text
    assert "completion_tokens" in migration_text
    assert "total_tokens" in migration_text
    assert "estimated_cost" in migration_text
    assert "latency_ms" in migration_text


def test_v06c_topic_idea_batch_has_migration():
    migration_path = Path("app/db/migrations/versions/20260629_v06c_topic_idea_batch.py")
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "20260629_v06c_idea_batch" in migration_text
    assert 'down_revision = "20260625_v06b_llm_meta"' in migration_text
    assert "writingtopicideabatch" in migration_text
    assert "student_id" in migration_text
    assert "ideas" in migration_text
    assert "expires_at" in migration_text
    assert "consumed_at" in migration_text
    assert "selected_idea_id" in migration_text
    assert "created_essay_id" in migration_text


def test_v06d_essay_archive_revision_attempts_has_migration():
    migration_path = Path(
        "app/db/migrations/versions/20260630_v06d_essay_archive_revision_attempts.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "20260630_v06d_essay_archive" in migration_text
    assert 'down_revision = "20260629_v06c_idea_batch"' in migration_text
    assert "last_version_submitted_at" in migration_text
    assert "visibility_changed_at" in migration_text
    assert "hidden_at" in migration_text
    assert "hidden_by" in migration_text
    assert "round_index" in migration_text
    assert "essayrevisionattempt" in migration_text
    assert "target_round_index" in migration_text
    assert "submitted_content_hash" in migration_text
    assert "uq_essay_revision_attempt_idempotency" in migration_text
    assert "uq_essay_revision_attempt_target_round_active" in migration_text
    assert "uq_essay_version_round_per_essay" in migration_text
