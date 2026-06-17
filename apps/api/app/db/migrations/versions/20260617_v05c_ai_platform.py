"""Add V0.5c AI platform observability fields."""

import sqlalchemy as sa
from alembic import op


revision = "20260617_v05c_ai_platform"
down_revision = "20260608_v05b_ai_sentence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llmcalllog", sa.Column("resolved_provider", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("resolved_model", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("primary_provider", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("primary_model", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("fallback_provider", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("fallback_model", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("fallback_reason", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("llmcalllog", sa.Column("final_status", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("pricing_status", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("attempt_summaries", sa.JSON(), nullable=False, server_default="[]"))
    op.create_index("ix_llmcalllog_resolved_provider", "llmcalllog", ["resolved_provider"], unique=False)
    op.create_index("ix_llmcalllog_resolved_model", "llmcalllog", ["resolved_model"], unique=False)
    op.create_index("ix_llmcalllog_primary_provider", "llmcalllog", ["primary_provider"], unique=False)
    op.create_index("ix_llmcalllog_fallback_provider", "llmcalllog", ["fallback_provider"], unique=False)
    op.create_index("ix_llmcalllog_fallback_reason", "llmcalllog", ["fallback_reason"], unique=False)
    op.create_index("ix_llmcalllog_final_status", "llmcalllog", ["final_status"], unique=False)
    op.create_index("ix_llmcalllog_pricing_status", "llmcalllog", ["pricing_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_llmcalllog_pricing_status", table_name="llmcalllog")
    op.drop_index("ix_llmcalllog_final_status", table_name="llmcalllog")
    op.drop_index("ix_llmcalllog_fallback_reason", table_name="llmcalllog")
    op.drop_index("ix_llmcalllog_fallback_provider", table_name="llmcalllog")
    op.drop_index("ix_llmcalllog_primary_provider", table_name="llmcalllog")
    op.drop_index("ix_llmcalllog_resolved_model", table_name="llmcalllog")
    op.drop_index("ix_llmcalllog_resolved_provider", table_name="llmcalllog")
    op.drop_column("llmcalllog", "attempt_summaries")
    op.drop_column("llmcalllog", "pricing_status")
    op.drop_column("llmcalllog", "final_status")
    op.drop_column("llmcalllog", "attempt_count")
    op.drop_column("llmcalllog", "fallback_reason")
    op.drop_column("llmcalllog", "fallback_model")
    op.drop_column("llmcalllog", "fallback_provider")
    op.drop_column("llmcalllog", "primary_model")
    op.drop_column("llmcalllog", "primary_provider")
    op.drop_column("llmcalllog", "resolved_model")
    op.drop_column("llmcalllog", "resolved_provider")
