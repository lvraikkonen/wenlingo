from alembic import op
import sqlalchemy as sa

revision = "20260625_v06b_llm_meta"
down_revision = "20260618_v05c1_daily_limit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llmcalllog", sa.Column("topic_type", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("topic_variant", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("scaffold_template_version", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("source_policy_summary", sa.String(), nullable=False, server_default=""))
    op.add_column("llmcalllog", sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("llmcalllog", sa.Column("request_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("llmcalllog", sa.Column("response_received_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_llmcalllog_topic_type", "llmcalllog", ["topic_type"])
    op.create_index("ix_llmcalllog_topic_variant", "llmcalllog", ["topic_variant"])
    op.create_index("ix_llmcalllog_scaffold_template_version", "llmcalllog", ["scaffold_template_version"])


def downgrade() -> None:
    op.drop_index("ix_llmcalllog_scaffold_template_version", table_name="llmcalllog")
    op.drop_index("ix_llmcalllog_topic_variant", table_name="llmcalllog")
    op.drop_index("ix_llmcalllog_topic_type", table_name="llmcalllog")
    op.drop_column("llmcalllog", "response_received_at")
    op.drop_column("llmcalllog", "request_started_at")
    op.drop_column("llmcalllog", "duration_ms")
    op.drop_column("llmcalllog", "source_policy_summary")
    op.drop_column("llmcalllog", "scaffold_template_version")
    op.drop_column("llmcalllog", "topic_variant")
    op.drop_column("llmcalllog", "topic_type")
