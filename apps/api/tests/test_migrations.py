import importlib
from pathlib import Path
import re

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.exc import IntegrityError


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


def test_v06d_essay_archive_revision_attempts_migrates_existing_sqlite_rows(monkeypatch):
    migration = importlib.import_module(
        "app.db.migrations.versions.20260630_v06d_essay_archive_revision_attempts"
    )
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "essay",
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    sa.Table(
        "essayversion",
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("essay_id", sa.String(), nullable=False),
        sa.Column("version_label", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(
            sa.text("INSERT INTO essay (id, created_at) VALUES (:id, :created_at)"),
            [
                {"id": "essay-1", "created_at": "2026-06-01 09:00:00+00:00"},
                {"id": "essay-2", "created_at": "2026-06-02 10:00:00+00:00"},
            ],
        )
        connection.execute(
            sa.text(
                "INSERT INTO essayversion (id, essay_id, version_label, created_at) "
                "VALUES (:id, :essay_id, :version_label, :created_at)"
            ),
            [
                {
                    "id": "version-1",
                    "essay_id": "essay-1",
                    "version_label": "first_draft",
                    "created_at": "2026-06-01 09:30:00+00:00",
                },
                {
                    "id": "version-2",
                    "essay_id": "essay-1",
                    "version_label": "revision",
                    "created_at": "2026-06-03 11:30:00+00:00",
                },
                {
                    "id": "version-3",
                    "essay_id": "essay-2",
                    "version_label": "first_draft",
                    "created_at": "2026-06-02 10:30:00+00:00",
                },
            ],
        )
        context = MigrationContext.configure(connection)
        monkeypatch.setattr(migration, "op", Operations(context))

        migration.upgrade()

        essay_1 = connection.execute(
            sa.text(
                "SELECT updated_at, last_version_submitted_at, hidden_by "
                "FROM essay WHERE id = 'essay-1'"
            )
        ).mappings().one()
        assert essay_1["updated_at"] == "2026-06-01 09:00:00+00:00"
        assert essay_1["last_version_submitted_at"] == "2026-06-03 11:30:00+00:00"
        assert essay_1["hidden_by"] == ""

        round_indexes = connection.execute(
            sa.text("SELECT id, round_index FROM essayversion ORDER BY id")
        ).all()
        assert round_indexes == [("version-1", 1), ("version-2", 2), ("version-3", 1)]

        connection.execute(
            sa.text(
                "INSERT INTO essayrevisionattempt "
                "(id, essay_id, base_version_id, target_round_index, "
                "submitted_content_hash, idempotency_key, status, created_at, updated_at) "
                "VALUES "
                "('attempt-1', 'essay-1', 'version-2', 3, 'hash-1', 'idem-1', "
                "'pending_comparison', '2026-06-03 12:00:00+00:00', "
                "'2026-06-03 12:00:00+00:00')"
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO essayrevisionattempt "
                    "(id, essay_id, base_version_id, target_round_index, "
                    "submitted_content_hash, idempotency_key, status, created_at, updated_at) "
                    "VALUES "
                    "('attempt-2', 'essay-1', 'version-2', 3, 'hash-2', 'idem-2', "
                    "'pending_comparison', '2026-06-03 12:01:00+00:00', "
                    "'2026-06-03 12:01:00+00:00')"
                )
            )


def test_v06e_streaming_reliability_migrates_existing_sqlite_rows(monkeypatch):
    migration = importlib.import_module(
        "app.db.migrations.versions.20260703_v06e_streaming_reliability"
    )
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "studentprofile",
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
    )
    sa.Table(
        "essay",
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("student_id", sa.String(), nullable=False),
    )
    sa.Table(
        "essayversion",
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("essay_id", sa.String(), nullable=False),
    )
    sa.Table(
        "llmcalllog",
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("student_id", sa.String(), nullable=True),
        sa.Column("task_type", sa.String(), nullable=False),
        sa.Column("task_name", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("prompt_key", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("provider", sa.String(), nullable=False, server_default="mock"),
        sa.Column("model", sa.String(), nullable=False, server_default="mock"),
        sa.Column("resolved_provider", sa.String(), nullable=False, server_default=""),
        sa.Column("resolved_model", sa.String(), nullable=False, server_default=""),
        sa.Column("primary_provider", sa.String(), nullable=False, server_default=""),
        sa.Column("primary_model", sa.String(), nullable=False, server_default=""),
        sa.Column("fallback_provider", sa.String(), nullable=False, server_default=""),
        sa.Column("fallback_model", sa.String(), nullable=False, server_default=""),
        sa.Column("fallback_reason", sa.String(), nullable=False, server_default=""),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("final_status", sa.String(), nullable=False, server_default=""),
        sa.Column("pricing_status", sa.String(), nullable=False, server_default=""),
        sa.Column("attempt_summaries", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("prompt_version", sa.String(), nullable=False, server_default=""),
        sa.Column("input_summary", sa.String(), nullable=False),
        sa.Column("raw_response", sa.String(), nullable=False, server_default=""),
        sa.Column("output_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("validation_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_message", sa.String(), nullable=False, server_default=""),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("topic_type", sa.String(), nullable=False, server_default=""),
        sa.Column("topic_variant", sa.String(), nullable=False, server_default=""),
        sa.Column("scaffold_template_version", sa.String(), nullable=False, server_default=""),
        sa.Column("source_policy_summary", sa.String(), nullable=False, server_default=""),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(
            sa.text(
                "INSERT INTO llmcalllog "
                "(id, task_type, task_name, prompt_key, input_summary, created_at) "
                "VALUES "
                "('log-1', 'essay', 'essay_feedback', 'essay_feedback', "
                "'essay feedback draft length 24', '2026-07-03 09:00:00+00:00')"
            )
        )
        context = MigrationContext.configure(connection)
        monkeypatch.setattr(migration, "op", Operations(context))

        migration.upgrade()

        inspector = sa.inspect(connection)
        llm_columns = {
            column["name"]: column
            for column in inspector.get_columns("llmcalllog")
        }
        expected_llm_columns = {
            "streaming_enabled",
            "stream_protocol",
            "stream_started_at",
            "first_provider_delta_at",
            "first_visible_content_at",
            "last_content_at",
            "usage_received_at",
            "client_disconnected_at",
            "provider_stream_completed_at",
            "usage_available",
            "usage_source",
            "usage_is_estimated",
            "usage_details_json",
            "stream_final_status",
            "cost_source",
            "cost_error_code",
            "pricing_snapshot_id",
            "pricing_snapshot_version",
            "provider_reported_cost_usd",
            "cost_calculation_version",
            "provider_request_id",
            "provider_generation_id",
        }
        assert expected_llm_columns <= set(llm_columns)
        for column_name in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "estimated_cost",
        ):
            assert llm_columns[column_name]["nullable"] is True

        llm_defaults = connection.execute(
            sa.text(
                "SELECT streaming_enabled, stream_protocol, usage_available, "
                "usage_source, usage_is_estimated, usage_details_json, cost_source, "
                "cost_error_code, stream_final_status, pricing_snapshot_version, "
                "provider_reported_cost_usd, cost_calculation_version, "
                "provider_request_id, provider_generation_id "
                "FROM llmcalllog WHERE id = 'log-1'"
            )
        ).mappings().one()
        assert llm_defaults["streaming_enabled"] in (False, 0)
        assert llm_defaults["stream_protocol"] == "none"
        assert llm_defaults["usage_available"] in (False, 0)
        assert llm_defaults["usage_source"] == "unavailable"
        assert llm_defaults["usage_is_estimated"] in (False, 0)
        assert llm_defaults["usage_details_json"] in ({}, "{}")
        assert llm_defaults["cost_source"] == "unavailable"
        assert llm_defaults["cost_error_code"] == ""
        assert llm_defaults["stream_final_status"] == "not_streaming"
        assert llm_defaults["pricing_snapshot_version"] == ""
        assert llm_defaults["provider_reported_cost_usd"] is None
        assert llm_defaults["cost_calculation_version"] == "v0.6e.1"
        assert llm_defaults["provider_request_id"] is None
        assert llm_defaults["provider_generation_id"] is None

        assert "prewritingaijob" in inspector.get_table_names()
        assert "essayfeedbacksubmission" in inspector.get_table_names()
        prewriting_columns = {
            column["name"]
            for column in inspector.get_columns("prewritingaijob")
        }
        assert {"llm_call_log_id", "started_at", "completed_at"} <= prewriting_columns
        feedback_submission_columns = {
            column["name"]
            for column in inspector.get_columns("essayfeedbacksubmission")
        }
        assert {"route_scope", "payload_schema_version"} <= feedback_submission_columns

        prewriting_unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("prewritingaijob")
        }
        feedback_unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("essayfeedbacksubmission")
        }
        assert "uq_prewriting_ai_job_idempotency" in prewriting_unique_constraints
        assert "uq_essay_feedback_submission_idempotency" in feedback_unique_constraints

        llm_indexes = {
            index["name"]
            for index in inspector.get_indexes("llmcalllog")
        }
        prewriting_indexes = {
            index["name"]
            for index in inspector.get_indexes("prewritingaijob")
        }
        feedback_submission_indexes = {
            index["name"]
            for index in inspector.get_indexes("essayfeedbacksubmission")
        }
        assert {
            "ix_llmcalllog_streaming_enabled",
            "ix_llmcalllog_stream_protocol",
            "ix_llmcalllog_usage_available",
            "ix_llmcalllog_usage_source",
            "ix_llmcalllog_usage_is_estimated",
            "ix_llmcalllog_stream_final_status",
            "ix_llmcalllog_cost_source",
            "ix_llmcalllog_cost_error_code",
            "ix_llmcalllog_pricing_snapshot_id",
            "ix_llmcalllog_provider_request_id",
            "ix_llmcalllog_provider_generation_id",
        } <= llm_indexes
        assert {
            "ix_prewritingaijob_student_id",
            "ix_prewritingaijob_essay_id",
            "ix_prewritingaijob_task_name",
            "ix_prewritingaijob_idempotency_key",
            "ix_prewritingaijob_status",
            "ix_prewritingaijob_stage",
            "ix_prewritingaijob_locked_by",
            "ix_prewritingaijob_lease_expires_at",
            "ix_prewritingaijob_result_ref_id",
            "ix_prewritingaijob_error_code",
            "ix_prewritingaijob_llm_call_log_id",
        } <= prewriting_indexes
        assert {
            "ix_essayfeedbacksubmission_student_id",
            "ix_essayfeedbacksubmission_essay_id",
            "ix_essayfeedbacksubmission_idempotency_scope",
            "ix_essayfeedbacksubmission_route_scope",
            "ix_essayfeedbacksubmission_payload_schema_version",
            "ix_essayfeedbacksubmission_task_name",
            "ix_essayfeedbacksubmission_client_submission_id",
            "ix_essayfeedbacksubmission_payload_hash",
            "ix_essayfeedbacksubmission_status",
            "ix_essayfeedbacksubmission_llm_call_log_id",
            "ix_essayfeedbacksubmission_essay_version_id",
            "ix_essayfeedbacksubmission_daily_limit_counter_id",
            "ix_essayfeedbacksubmission_daily_limit_reservation_token",
            "ix_essayfeedbacksubmission_error_code",
        } <= feedback_submission_indexes
