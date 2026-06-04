"""Add student LLM traceability and task name."""

import sqlalchemy as sa
from alembic import op


revision = "20260515_llm_student_usage"
down_revision = "20260514_quality_spine_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llmcalllog", sa.Column("student_id", sa.String(), nullable=True))
    op.add_column(
        "llmcalllog",
        sa.Column("task_name", sa.String(), nullable=False, server_default="unknown"),
    )
    op.create_foreign_key(
        "fk_llmcalllog_student_id_studentprofile",
        "llmcalllog",
        "studentprofile",
        ["student_id"],
        ["id"],
    )
    op.create_index("ix_llmcalllog_student_id", "llmcalllog", ["student_id"], unique=False)
    op.create_index("ix_llmcalllog_task_name", "llmcalllog", ["task_name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_llmcalllog_task_name", table_name="llmcalllog")
    op.drop_index("ix_llmcalllog_student_id", table_name="llmcalllog")
    op.drop_constraint(
        "fk_llmcalllog_student_id_studentprofile",
        "llmcalllog",
        type_="foreignkey",
    )
    op.drop_column("llmcalllog", "task_name")
    op.drop_column("llmcalllog", "student_id")
