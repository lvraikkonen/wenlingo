"""Add alpha feedback observation tables."""

import sqlalchemy as sa
from alembic import op


revision = "20260527_alpha_feedback_obs"
down_revision = "20260521_assessment_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alphainvitecode",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("issued_to_note", sa.String(), nullable=False),
        sa.Column("consumed_by_parent_id", sa.String(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["consumed_by_parent_id"],
            ["parentuser.id"],
            name="fk_alphainvitecode_consumed_by_parent_id_parentuser",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_alphainvitecode_code_hash",
        "alphainvitecode",
        ["code_hash"],
        unique=True,
    )
    op.create_index(
        "ix_alphainvitecode_consumed_by_parent_id",
        "alphainvitecode",
        ["consumed_by_parent_id"],
        unique=False,
    )
    op.create_index(
        "ix_alphainvitecode_status",
        "alphainvitecode",
        ["status"],
        unique=False,
    )

    op.create_table(
        "productevent",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("student_id", sa.String(), nullable=True),
        sa.Column("invite_code_id", sa.String(), nullable=True),
        sa.Column("alpha_session_id", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["invite_code_id"],
            ["alphainvitecode.id"],
            name="fk_productevent_invite_code_id_alphainvitecode",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["parentuser.id"],
            name="fk_productevent_parent_id_parentuser",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["studentprofile.id"],
            name="fk_productevent_student_id_studentprofile",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_productevent_alpha_session_id",
        "productevent",
        ["alpha_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_productevent_event_type",
        "productevent",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_productevent_invite_code_id",
        "productevent",
        ["invite_code_id"],
        unique=False,
    )
    op.create_index(
        "ix_productevent_parent_id",
        "productevent",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        "ix_productevent_student_id",
        "productevent",
        ["student_id"],
        unique=False,
    )

    op.create_table(
        "feedbackreaction",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("student_id", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("reaction", sa.String(), nullable=False),
        sa.Column("alpha_session_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["parentuser.id"],
            name="fk_feedbackreaction_parent_id_parentuser",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["studentprofile.id"],
            name="fk_feedbackreaction_student_id_studentprofile",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id",
            "target_type",
            "target_id",
            name="uq_feedbackreaction_student_target",
        ),
    )
    op.create_index(
        "ix_feedbackreaction_alpha_session_id",
        "feedbackreaction",
        ["alpha_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_feedbackreaction_parent_id",
        "feedbackreaction",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        "ix_feedbackreaction_student_id",
        "feedbackreaction",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        "ix_feedbackreaction_target_id",
        "feedbackreaction",
        ["target_id"],
        unique=False,
    )
    op.create_index(
        "ix_feedbackreaction_target_type",
        "feedbackreaction",
        ["target_type"],
        unique=False,
    )

    op.create_table(
        "parentfeedback",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=False),
        sa.Column("student_id", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("usefulness", sa.String(), nullable=False),
        sa.Column("alpha_session_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["parentuser.id"],
            name="fk_parentfeedback_parent_id_parentuser",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["studentprofile.id"],
            name="fk_parentfeedback_student_id_studentprofile",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parent_id",
            "student_id",
            "target_type",
            name="uq_parentfeedback_parent_student_target",
        ),
    )
    op.create_index(
        "ix_parentfeedback_alpha_session_id",
        "parentfeedback",
        ["alpha_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_parentfeedback_parent_id",
        "parentfeedback",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        "ix_parentfeedback_student_id",
        "parentfeedback",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        "ix_parentfeedback_target_type",
        "parentfeedback",
        ["target_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_parentfeedback_target_type", table_name="parentfeedback")
    op.drop_index("ix_parentfeedback_student_id", table_name="parentfeedback")
    op.drop_index("ix_parentfeedback_parent_id", table_name="parentfeedback")
    op.drop_index("ix_parentfeedback_alpha_session_id", table_name="parentfeedback")
    op.drop_table("parentfeedback")

    op.drop_index("ix_feedbackreaction_target_type", table_name="feedbackreaction")
    op.drop_index("ix_feedbackreaction_target_id", table_name="feedbackreaction")
    op.drop_index("ix_feedbackreaction_student_id", table_name="feedbackreaction")
    op.drop_index("ix_feedbackreaction_parent_id", table_name="feedbackreaction")
    op.drop_index("ix_feedbackreaction_alpha_session_id", table_name="feedbackreaction")
    op.drop_table("feedbackreaction")

    op.drop_index("ix_productevent_student_id", table_name="productevent")
    op.drop_index("ix_productevent_parent_id", table_name="productevent")
    op.drop_index("ix_productevent_invite_code_id", table_name="productevent")
    op.drop_index("ix_productevent_event_type", table_name="productevent")
    op.drop_index("ix_productevent_alpha_session_id", table_name="productevent")
    op.drop_table("productevent")

    op.drop_index("ix_alphainvitecode_status", table_name="alphainvitecode")
    op.drop_index("ix_alphainvitecode_consumed_by_parent_id", table_name="alphainvitecode")
    op.drop_index("ix_alphainvitecode_code_hash", table_name="alphainvitecode")
    op.drop_table("alphainvitecode")
