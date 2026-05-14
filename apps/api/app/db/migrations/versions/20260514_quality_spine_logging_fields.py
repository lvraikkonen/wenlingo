"""Add V0.2 quality spine traceability fields."""

import sqlalchemy as sa
from alembic import op


revision = "20260514_quality_spine_logging_fields"
down_revision = "20260507_essay_version_uniqueness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llmcalllog", sa.Column("provider", sa.String(), nullable=True))
    op.add_column("llmcalllog", sa.Column("model", sa.String(), nullable=True))
    op.add_column("llmcalllog", sa.Column("prompt_version", sa.String(), nullable=True))
    op.add_column("llmcalllog", sa.Column("raw_response", sa.Text(), nullable=True))
    op.add_column("llmcalllog", sa.Column("retry_count", sa.Integer(), nullable=True))
    op.add_column("essayversion", sa.Column("duration_seconds", sa.Integer(), nullable=True))
    op.add_column("essayversion", sa.Column("completed_tasks", sa.JSON(), nullable=True))
    op.add_column("essayversion", sa.Column("skipped_tasks", sa.JSON(), nullable=True))
    op.add_column("essayversion", sa.Column("llm_call_log_id", sa.String(), nullable=True))
    op.create_index(
        "ix_essayversion_llm_call_log_id",
        "essayversion",
        ["llm_call_log_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_essayversion_llm_call_log_id", table_name="essayversion")
    op.drop_column("essayversion", "llm_call_log_id")
    op.drop_column("essayversion", "skipped_tasks")
    op.drop_column("essayversion", "completed_tasks")
    op.drop_column("essayversion", "duration_seconds")
    op.drop_column("llmcalllog", "retry_count")
    op.drop_column("llmcalllog", "raw_response")
    op.drop_column("llmcalllog", "prompt_version")
    op.drop_column("llmcalllog", "model")
    op.drop_column("llmcalllog", "provider")
