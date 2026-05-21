"""Add assessment artifact references."""

import sqlalchemy as sa
from alembic import op


revision = "20260521_assessment_artifacts"
down_revision = "20260520_ability_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assessment", sa.Column("sentence_training_id", sa.String(), nullable=True))
    op.add_column("assessment", sa.Column("essay_id", sa.String(), nullable=True))
    op.create_index(
        "ix_assessment_sentence_training_id",
        "assessment",
        ["sentence_training_id"],
        unique=False,
    )
    op.create_index("ix_assessment_essay_id", "assessment", ["essay_id"], unique=False)
    op.create_foreign_key(
        "fk_assessment_sentence_training_id_sentencetraining",
        "assessment",
        "sentencetraining",
        ["sentence_training_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_assessment_essay_id_essay",
        "assessment",
        "essay",
        ["essay_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_assessment_essay_id_essay",
        "assessment",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_assessment_sentence_training_id_sentencetraining",
        "assessment",
        type_="foreignkey",
    )
    op.drop_index("ix_assessment_essay_id", table_name="assessment")
    op.drop_index("ix_assessment_sentence_training_id", table_name="assessment")
    op.drop_column("assessment", "essay_id")
    op.drop_column("assessment", "sentence_training_id")
