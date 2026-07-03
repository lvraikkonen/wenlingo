from alembic import op
import sqlalchemy as sa


revision = "20260703_v06e_streaming"
down_revision = "20260630_v06d_essay_archive"
branch_labels = None
depends_on = None


_EPOCH_DEFAULT = sa.text("'1970-01-01 00:00:00+00:00'")
_JSON_OBJECT_DEFAULT = sa.text("'{}'")


def upgrade() -> None:
    with op.batch_alter_table("llmcalllog") as batch_op:
        batch_op.add_column(
            sa.Column(
                "streaming_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("stream_protocol", sa.String(), nullable=False, server_default="none")
        )
        batch_op.add_column(
            sa.Column("stream_started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("first_provider_delta_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("first_visible_content_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_content_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("usage_received_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("client_disconnected_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("provider_stream_completed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "usage_available",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("usage_source", sa.String(), nullable=False, server_default="unavailable")
        )
        batch_op.add_column(
            sa.Column(
                "usage_is_estimated",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "usage_details_json",
                sa.JSON(),
                nullable=False,
                server_default=_JSON_OBJECT_DEFAULT,
            )
        )
        batch_op.add_column(
            sa.Column(
                "stream_final_status",
                sa.String(),
                nullable=False,
                server_default="not_streaming",
            )
        )
        batch_op.add_column(
            sa.Column("cost_source", sa.String(), nullable=False, server_default="unavailable")
        )
        batch_op.add_column(
            sa.Column("cost_error_code", sa.String(), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("pricing_snapshot_id", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("pricing_snapshot_version", sa.String(), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("provider_reported_cost_usd", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "cost_calculation_version",
                sa.String(),
                nullable=False,
                server_default="v0.6e.1",
            )
        )
        batch_op.add_column(sa.Column("provider_request_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("provider_generation_id", sa.String(), nullable=True))
        batch_op.alter_column(
            "prompt_tokens",
            existing_type=sa.Integer(),
            nullable=True,
            server_default=None,
        )
        batch_op.alter_column(
            "completion_tokens",
            existing_type=sa.Integer(),
            nullable=True,
            server_default=None,
        )
        batch_op.alter_column(
            "total_tokens",
            existing_type=sa.Integer(),
            nullable=True,
            server_default=None,
        )
        batch_op.alter_column(
            "estimated_cost",
            existing_type=sa.Float(),
            nullable=True,
            server_default=None,
        )
        batch_op.create_index("ix_llmcalllog_streaming_enabled", ["streaming_enabled"])
        batch_op.create_index("ix_llmcalllog_stream_protocol", ["stream_protocol"])
        batch_op.create_index("ix_llmcalllog_usage_available", ["usage_available"])
        batch_op.create_index("ix_llmcalllog_usage_source", ["usage_source"])
        batch_op.create_index("ix_llmcalllog_usage_is_estimated", ["usage_is_estimated"])
        batch_op.create_index("ix_llmcalllog_stream_final_status", ["stream_final_status"])
        batch_op.create_index("ix_llmcalllog_cost_source", ["cost_source"])
        batch_op.create_index("ix_llmcalllog_cost_error_code", ["cost_error_code"])
        batch_op.create_index("ix_llmcalllog_pricing_snapshot_id", ["pricing_snapshot_id"])
        batch_op.create_index("ix_llmcalllog_provider_request_id", ["provider_request_id"])
        batch_op.create_index("ix_llmcalllog_provider_generation_id", ["provider_generation_id"])

    op.create_table(
        "prewritingaijob",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("student_id", sa.String(), nullable=False),
        sa.Column("essay_id", sa.String(), nullable=False),
        sa.Column("task_name", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_by", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress_event_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("schema_version", sa.String(), nullable=False, server_default="v0.6e.1"),
        sa.Column("result_ref_type", sa.String(), nullable=False, server_default=""),
        sa.Column("result_ref_id", sa.String(), nullable=True),
        sa.Column("result_payload_json", sa.JSON(), nullable=False, server_default=_JSON_OBJECT_DEFAULT),
        sa.Column("error_code", sa.String(), nullable=False, server_default=""),
        sa.Column("error_message", sa.String(), nullable=False, server_default=""),
        sa.Column("llm_call_log_id", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_EPOCH_DEFAULT),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_EPOCH_DEFAULT),
        sa.ForeignKeyConstraint(["student_id"], ["studentprofile.id"]),
        sa.ForeignKeyConstraint(["essay_id"], ["essay.id"]),
        sa.ForeignKeyConstraint(["llm_call_log_id"], ["llmcalllog.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id",
            "essay_id",
            "task_name",
            "idempotency_key",
            name="uq_prewriting_ai_job_idempotency",
        ),
    )
    op.create_index("ix_prewritingaijob_student_id", "prewritingaijob", ["student_id"])
    op.create_index("ix_prewritingaijob_essay_id", "prewritingaijob", ["essay_id"])
    op.create_index("ix_prewritingaijob_task_name", "prewritingaijob", ["task_name"])
    op.create_index(
        "ix_prewritingaijob_idempotency_key",
        "prewritingaijob",
        ["idempotency_key"],
    )
    op.create_index("ix_prewritingaijob_status", "prewritingaijob", ["status"])
    op.create_index("ix_prewritingaijob_stage", "prewritingaijob", ["stage"])
    op.create_index("ix_prewritingaijob_locked_by", "prewritingaijob", ["locked_by"])
    op.create_index(
        "ix_prewritingaijob_lease_expires_at",
        "prewritingaijob",
        ["lease_expires_at"],
    )
    op.create_index("ix_prewritingaijob_result_ref_id", "prewritingaijob", ["result_ref_id"])
    op.create_index("ix_prewritingaijob_error_code", "prewritingaijob", ["error_code"])
    op.create_index(
        "ix_prewritingaijob_llm_call_log_id",
        "prewritingaijob",
        ["llm_call_log_id"],
    )

    op.create_table(
        "essayfeedbacksubmission",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("student_id", sa.String(), nullable=False),
        sa.Column("essay_id", sa.String(), nullable=True),
        sa.Column("idempotency_scope", sa.String(), nullable=False),
        sa.Column("route_scope", sa.String(), nullable=False),
        sa.Column("payload_schema_version", sa.String(), nullable=False, server_default="v0.6e.1"),
        sa.Column("task_name", sa.String(), nullable=False),
        sa.Column("client_submission_id", sa.String(), nullable=False),
        sa.Column("payload_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="created"),
        sa.Column("llm_call_log_id", sa.String(), nullable=True),
        sa.Column("essay_version_id", sa.String(), nullable=True),
        sa.Column("daily_limit_counter_id", sa.String(), nullable=True),
        sa.Column("daily_limit_reservation_token", sa.String(), nullable=True),
        sa.Column("result_fetch_url", sa.String(), nullable=False, server_default=""),
        sa.Column("error_code", sa.String(), nullable=False, server_default=""),
        sa.Column("error_message", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_EPOCH_DEFAULT),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_EPOCH_DEFAULT),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["studentprofile.id"]),
        sa.ForeignKeyConstraint(["essay_id"], ["essay.id"]),
        sa.ForeignKeyConstraint(["llm_call_log_id"], ["llmcalllog.id"]),
        sa.ForeignKeyConstraint(["essay_version_id"], ["essayversion.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_scope",
            "task_name",
            "client_submission_id",
            name="uq_essay_feedback_submission_idempotency",
        ),
    )
    op.create_index(
        "ix_essayfeedbacksubmission_student_id",
        "essayfeedbacksubmission",
        ["student_id"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_essay_id",
        "essayfeedbacksubmission",
        ["essay_id"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_idempotency_scope",
        "essayfeedbacksubmission",
        ["idempotency_scope"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_route_scope",
        "essayfeedbacksubmission",
        ["route_scope"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_payload_schema_version",
        "essayfeedbacksubmission",
        ["payload_schema_version"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_task_name",
        "essayfeedbacksubmission",
        ["task_name"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_client_submission_id",
        "essayfeedbacksubmission",
        ["client_submission_id"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_payload_hash",
        "essayfeedbacksubmission",
        ["payload_hash"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_status",
        "essayfeedbacksubmission",
        ["status"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_llm_call_log_id",
        "essayfeedbacksubmission",
        ["llm_call_log_id"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_essay_version_id",
        "essayfeedbacksubmission",
        ["essay_version_id"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_daily_limit_counter_id",
        "essayfeedbacksubmission",
        ["daily_limit_counter_id"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_daily_limit_reservation_token",
        "essayfeedbacksubmission",
        ["daily_limit_reservation_token"],
    )
    op.create_index(
        "ix_essayfeedbacksubmission_error_code",
        "essayfeedbacksubmission",
        ["error_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_essayfeedbacksubmission_error_code", table_name="essayfeedbacksubmission")
    op.drop_index(
        "ix_essayfeedbacksubmission_daily_limit_reservation_token",
        table_name="essayfeedbacksubmission",
    )
    op.drop_index(
        "ix_essayfeedbacksubmission_daily_limit_counter_id",
        table_name="essayfeedbacksubmission",
    )
    op.drop_index(
        "ix_essayfeedbacksubmission_essay_version_id",
        table_name="essayfeedbacksubmission",
    )
    op.drop_index(
        "ix_essayfeedbacksubmission_llm_call_log_id",
        table_name="essayfeedbacksubmission",
    )
    op.drop_index("ix_essayfeedbacksubmission_status", table_name="essayfeedbacksubmission")
    op.drop_index("ix_essayfeedbacksubmission_payload_hash", table_name="essayfeedbacksubmission")
    op.drop_index(
        "ix_essayfeedbacksubmission_client_submission_id",
        table_name="essayfeedbacksubmission",
    )
    op.drop_index("ix_essayfeedbacksubmission_task_name", table_name="essayfeedbacksubmission")
    op.drop_index(
        "ix_essayfeedbacksubmission_payload_schema_version",
        table_name="essayfeedbacksubmission",
    )
    op.drop_index("ix_essayfeedbacksubmission_route_scope", table_name="essayfeedbacksubmission")
    op.drop_index(
        "ix_essayfeedbacksubmission_idempotency_scope",
        table_name="essayfeedbacksubmission",
    )
    op.drop_index("ix_essayfeedbacksubmission_essay_id", table_name="essayfeedbacksubmission")
    op.drop_index("ix_essayfeedbacksubmission_student_id", table_name="essayfeedbacksubmission")
    op.drop_table("essayfeedbacksubmission")

    op.drop_index("ix_prewritingaijob_llm_call_log_id", table_name="prewritingaijob")
    op.drop_index("ix_prewritingaijob_error_code", table_name="prewritingaijob")
    op.drop_index("ix_prewritingaijob_result_ref_id", table_name="prewritingaijob")
    op.drop_index("ix_prewritingaijob_lease_expires_at", table_name="prewritingaijob")
    op.drop_index("ix_prewritingaijob_locked_by", table_name="prewritingaijob")
    op.drop_index("ix_prewritingaijob_stage", table_name="prewritingaijob")
    op.drop_index("ix_prewritingaijob_status", table_name="prewritingaijob")
    op.drop_index("ix_prewritingaijob_idempotency_key", table_name="prewritingaijob")
    op.drop_index("ix_prewritingaijob_task_name", table_name="prewritingaijob")
    op.drop_index("ix_prewritingaijob_essay_id", table_name="prewritingaijob")
    op.drop_index("ix_prewritingaijob_student_id", table_name="prewritingaijob")
    op.drop_table("prewritingaijob")

    with op.batch_alter_table("llmcalllog") as batch_op:
        batch_op.drop_index("ix_llmcalllog_provider_generation_id")
        batch_op.drop_index("ix_llmcalllog_provider_request_id")
        batch_op.drop_index("ix_llmcalllog_pricing_snapshot_id")
        batch_op.drop_index("ix_llmcalllog_cost_error_code")
        batch_op.drop_index("ix_llmcalllog_cost_source")
        batch_op.drop_index("ix_llmcalllog_stream_final_status")
        batch_op.drop_index("ix_llmcalllog_usage_is_estimated")
        batch_op.drop_index("ix_llmcalllog_usage_source")
        batch_op.drop_index("ix_llmcalllog_usage_available")
        batch_op.drop_index("ix_llmcalllog_stream_protocol")
        batch_op.drop_index("ix_llmcalllog_streaming_enabled")
        batch_op.alter_column(
            "estimated_cost",
            existing_type=sa.Float(),
            nullable=False,
            server_default="0",
        )
        batch_op.alter_column(
            "total_tokens",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )
        batch_op.alter_column(
            "completion_tokens",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )
        batch_op.alter_column(
            "prompt_tokens",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )
        batch_op.drop_column("provider_generation_id")
        batch_op.drop_column("provider_request_id")
        batch_op.drop_column("cost_calculation_version")
        batch_op.drop_column("provider_reported_cost_usd")
        batch_op.drop_column("pricing_snapshot_version")
        batch_op.drop_column("pricing_snapshot_id")
        batch_op.drop_column("cost_error_code")
        batch_op.drop_column("cost_source")
        batch_op.drop_column("stream_final_status")
        batch_op.drop_column("usage_details_json")
        batch_op.drop_column("usage_is_estimated")
        batch_op.drop_column("usage_source")
        batch_op.drop_column("usage_available")
        batch_op.drop_column("provider_stream_completed_at")
        batch_op.drop_column("client_disconnected_at")
        batch_op.drop_column("usage_received_at")
        batch_op.drop_column("last_content_at")
        batch_op.drop_column("first_visible_content_at")
        batch_op.drop_column("first_provider_delta_at")
        batch_op.drop_column("stream_started_at")
        batch_op.drop_column("stream_protocol")
        batch_op.drop_column("streaming_enabled")
