from alembic import op
import sqlalchemy as sa

revision = "20260629_v06c_idea_batch"
down_revision = "20260625_v06b_llm_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "writingtopicideabatch",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("student_id", sa.String(), nullable=False),
        sa.Column("grade_label", sa.String(), nullable=False),
        sa.Column("interest_input_present", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ideas", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("selected_idea_id", sa.String(), nullable=False, server_default=""),
        sa.Column("created_essay_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["studentprofile.id"]),
        sa.ForeignKeyConstraint(["created_essay_id"], ["essay.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_writingtopicideabatch_student_id", "writingtopicideabatch", ["student_id"])
    op.create_index("ix_writingtopicideabatch_grade_label", "writingtopicideabatch", ["grade_label"])
    op.create_index("ix_writingtopicideabatch_expires_at", "writingtopicideabatch", ["expires_at"])
    op.create_index("ix_writingtopicideabatch_consumed_at", "writingtopicideabatch", ["consumed_at"])
    op.create_index(
        "ix_writingtopicideabatch_selected_idea_id",
        "writingtopicideabatch",
        ["selected_idea_id"],
    )
    op.create_index(
        "ix_writingtopicideabatch_created_essay_id",
        "writingtopicideabatch",
        ["created_essay_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_writingtopicideabatch_created_essay_id", table_name="writingtopicideabatch")
    op.drop_index("ix_writingtopicideabatch_selected_idea_id", table_name="writingtopicideabatch")
    op.drop_index("ix_writingtopicideabatch_consumed_at", table_name="writingtopicideabatch")
    op.drop_index("ix_writingtopicideabatch_expires_at", table_name="writingtopicideabatch")
    op.drop_index("ix_writingtopicideabatch_grade_label", table_name="writingtopicideabatch")
    op.drop_index("ix_writingtopicideabatch_student_id", table_name="writingtopicideabatch")
    op.drop_table("writingtopicideabatch")
