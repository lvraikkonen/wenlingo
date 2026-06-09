"""Add V0.5b AI sentence challenge fields."""

import sqlalchemy as sa
from alembic import op


revision = "20260608_v05b_ai_sentence"
down_revision = "20260601_v05a_user_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sentencetraining", sa.Column("status", sa.String(), nullable=False, server_default="completed"))
    op.add_column("sentencetraining", sa.Column("challenge_prompt", sa.String(), nullable=False, server_default=""))
    op.add_column("sentencetraining", sa.Column("hint", sa.String(), nullable=False, server_default=""))
    op.add_column("sentencetraining", sa.Column("target_skill", sa.String(), nullable=False, server_default=""))
    op.add_column("sentencetraining", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_sentencetraining_status", "sentencetraining", ["status"], unique=False)
    op.create_index("ix_sentencetraining_target_skill", "sentencetraining", ["target_skill"], unique=False)
    op.create_index("ix_sentencetraining_completed_at", "sentencetraining", ["completed_at"], unique=False)

    op.add_column("llmcalllog", sa.Column("prompt_key", sa.String(), nullable=False, server_default="unknown"))
    op.add_column("llmcalllog", sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("llmcalllog", sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("llmcalllog", sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("llmcalllog", sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"))
    op.add_column("llmcalllog", sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_llmcalllog_prompt_key", "llmcalllog", ["prompt_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_llmcalllog_prompt_key", table_name="llmcalllog")
    op.drop_column("llmcalllog", "latency_ms")
    op.drop_column("llmcalllog", "estimated_cost")
    op.drop_column("llmcalllog", "total_tokens")
    op.drop_column("llmcalllog", "completion_tokens")
    op.drop_column("llmcalllog", "prompt_tokens")
    op.drop_column("llmcalllog", "prompt_key")

    op.drop_index("ix_sentencetraining_completed_at", table_name="sentencetraining")
    op.drop_index("ix_sentencetraining_target_skill", table_name="sentencetraining")
    op.drop_index("ix_sentencetraining_status", table_name="sentencetraining")
    op.drop_column("sentencetraining", "completed_at")
    op.drop_column("sentencetraining", "target_skill")
    op.drop_column("sentencetraining", "hint")
    op.drop_column("sentencetraining", "challenge_prompt")
    op.drop_column("sentencetraining", "status")
