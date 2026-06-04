"""Add uniqueness for essay version labels.

Existing duplicate (essay_id, version_label) rows must be resolved before
applying this migration.
"""

from alembic import op


revision = "20260507_essay_version_unique"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_essay_version_label_per_essay",
        "essayversion",
        ["essay_id", "version_label"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_essay_version_label_per_essay",
        "essayversion",
        type_="unique",
    )
