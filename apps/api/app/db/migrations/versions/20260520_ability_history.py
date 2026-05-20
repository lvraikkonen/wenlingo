"""Add ability history audit table."""

import sqlalchemy as sa
from alembic import op


revision = "20260520_ability_history"
down_revision = "20260515_family_test_llm_student_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "abilityhistory",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("student_id", sa.String(), nullable=False),
        sa.Column("ability_name", sa.String(), nullable=False),
        sa.Column("old_value", sa.Integer(), nullable=False),
        sa.Column("new_value", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=10), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["studentprofile.id"],
            name="fk_abilityhistory_student_id_studentprofile",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_abilityhistory_student_id",
        "abilityhistory",
        ["student_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_abilityhistory_student_id", table_name="abilityhistory")
    op.drop_table("abilityhistory")
