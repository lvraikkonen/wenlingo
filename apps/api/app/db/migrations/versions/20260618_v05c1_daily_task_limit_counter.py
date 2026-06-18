"""Add V0.5c.1 daily task limit counter."""

import sqlalchemy as sa
from alembic import op


revision = "20260618_v05c1_daily_task_limit_counter"
down_revision = "20260617_v05c_ai_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dailytasklimitcounter",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("student_id", sa.String(), nullable=False),
        sa.Column("task_name", sa.String(), nullable=False),
        sa.Column("product_day", sa.String(), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=False),
        sa.Column("reserved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("released_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reservation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["studentprofile.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id",
            "task_name",
            "product_day",
            name="uq_daily_task_limit_counter_key",
        ),
    )
    op.create_index(
        "ix_dailytasklimitcounter_student_id",
        "dailytasklimitcounter",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        "ix_dailytasklimitcounter_task_name",
        "dailytasklimitcounter",
        ["task_name"],
        unique=False,
    )
    op.create_index(
        "ix_dailytasklimitcounter_product_day",
        "dailytasklimitcounter",
        ["product_day"],
        unique=False,
    )
    op.create_index(
        "ix_dailytasklimitcounter_reservation_expires_at",
        "dailytasklimitcounter",
        ["reservation_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dailytasklimitcounter_reservation_expires_at",
        table_name="dailytasklimitcounter",
    )
    op.drop_index(
        "ix_dailytasklimitcounter_product_day",
        table_name="dailytasklimitcounter",
    )
    op.drop_index(
        "ix_dailytasklimitcounter_task_name",
        table_name="dailytasklimitcounter",
    )
    op.drop_index(
        "ix_dailytasklimitcounter_student_id",
        table_name="dailytasklimitcounter",
    )
    op.drop_table("dailytasklimitcounter")
