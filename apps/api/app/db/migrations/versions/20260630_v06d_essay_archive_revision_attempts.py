from alembic import op
import sqlalchemy as sa


revision = "20260630_v06d_essay_archive"
down_revision = "20260629_v06c_idea_batch"
branch_labels = None
depends_on = None


_EPOCH_DEFAULT = sa.text("'1970-01-01 00:00:00+00:00'")


def _raise_if_rows_exist(query: str, message: str) -> None:
    rows = op.get_bind().execute(sa.text(query)).fetchall()
    if rows:
        raise RuntimeError(f"{message}: {rows[:5]}")


def upgrade() -> None:
    op.add_column(
        "essay",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_EPOCH_DEFAULT,
        ),
    )
    op.add_column(
        "essay",
        sa.Column("last_version_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "essay",
        sa.Column("visibility_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "essay",
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "essay",
        sa.Column("hidden_by", sa.String(), nullable=False, server_default=""),
    )
    op.create_index("ix_essay_last_version_submitted_at", "essay", ["last_version_submitted_at"])
    op.create_index("ix_essay_visibility_changed_at", "essay", ["visibility_changed_at"])
    op.create_index("ix_essay_hidden_at", "essay", ["hidden_at"])
    op.create_index("ix_essay_hidden_by", "essay", ["hidden_by"])

    op.add_column("essayversion", sa.Column("round_index", sa.Integer(), nullable=True))
    op.create_index("ix_essayversion_round_index", "essayversion", ["round_index"])

    op.execute("UPDATE essay SET updated_at = created_at WHERE updated_at IS NULL")
    op.execute(
        "UPDATE essayversion SET round_index = 1 "
        "WHERE version_label = 'first_draft' AND round_index IS NULL"
    )
    op.execute(
        "UPDATE essayversion SET round_index = 2 "
        "WHERE version_label = 'revision' AND round_index IS NULL"
    )
    _raise_if_rows_exist(
        """
        SELECT id, version_label
        FROM essayversion
        WHERE version_label IS NULL
           OR (
                version_label NOT IN ('first_draft', 'revision')
                AND version_label NOT LIKE 'revision_round_%'
           )
        """,
        "essayversion contains unknown version_label values before V0.6d migration",
    )
    _raise_if_rows_exist(
        """
        SELECT essay_id, round_index, COUNT(*) AS duplicate_count
        FROM essayversion
        WHERE round_index IS NOT NULL
        GROUP BY essay_id, round_index
        HAVING COUNT(*) > 1
        """,
        "essayversion contains duplicate essay_id + round_index values",
    )
    op.execute(
        """
        UPDATE essay
        SET last_version_submitted_at = (
            SELECT MAX(essayversion.created_at)
            FROM essayversion
            WHERE essayversion.essay_id = essay.id
        )
        WHERE EXISTS (
            SELECT 1
            FROM essayversion
            WHERE essayversion.essay_id = essay.id
        )
        """
    )

    # SQLite and Postgres both support partial unique indexes for this case.
    # SQLModel exposes a same-named UniqueConstraint for create_all/test metadata.
    op.create_index(
        "uq_essay_version_round_per_essay",
        "essayversion",
        ["essay_id", "round_index"],
        unique=True,
        sqlite_where=sa.text("round_index IS NOT NULL"),
        postgresql_where=sa.text("round_index IS NOT NULL"),
    )

    op.create_table(
        "essayrevisionattempt",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("essay_id", sa.String(), nullable=False),
        sa.Column("base_version_id", sa.String(), nullable=False),
        sa.Column("target_round_index", sa.Integer(), nullable=False),
        sa.Column("submitted_content", sa.String(), nullable=True),
        sa.Column("submitted_content_hash", sa.String(), nullable=False, server_default=""),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending_comparison"),
        sa.Column("new_version_id", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_EPOCH_DEFAULT,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_EPOCH_DEFAULT,
        ),
        sa.ForeignKeyConstraint(["essay_id"], ["essay.id"]),
        sa.ForeignKeyConstraint(["base_version_id"], ["essayversion.id"]),
        sa.ForeignKeyConstraint(["new_version_id"], ["essayversion.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "essay_id",
            "base_version_id",
            "idempotency_key",
            name="uq_essay_revision_attempt_idempotency",
        ),
    )
    op.create_index("ix_essayrevisionattempt_essay_id", "essayrevisionattempt", ["essay_id"])
    op.create_index(
        "ix_essayrevisionattempt_base_version_id",
        "essayrevisionattempt",
        ["base_version_id"],
    )
    op.create_index(
        "ix_essayrevisionattempt_target_round_index",
        "essayrevisionattempt",
        ["target_round_index"],
    )
    op.create_index(
        "ix_essayrevisionattempt_submitted_content_hash",
        "essayrevisionattempt",
        ["submitted_content_hash"],
    )
    op.create_index(
        "ix_essayrevisionattempt_idempotency_key",
        "essayrevisionattempt",
        ["idempotency_key"],
    )
    op.create_index("ix_essayrevisionattempt_status", "essayrevisionattempt", ["status"])
    op.create_index(
        "ix_essayrevisionattempt_new_version_id",
        "essayrevisionattempt",
        ["new_version_id"],
    )
    op.create_index("ix_essayrevisionattempt_error_code", "essayrevisionattempt", ["error_code"])
    op.create_index(
        "uq_essay_revision_attempt_target_round_active",
        "essayrevisionattempt",
        ["essay_id", "base_version_id", "target_round_index"],
        unique=True,
        sqlite_where=sa.text("status IN ('pending_comparison', 'completed')"),
        postgresql_where=sa.text("status IN ('pending_comparison', 'completed')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_essay_revision_attempt_target_round_active",
        table_name="essayrevisionattempt",
    )
    op.drop_index("ix_essayrevisionattempt_error_code", table_name="essayrevisionattempt")
    op.drop_index("ix_essayrevisionattempt_new_version_id", table_name="essayrevisionattempt")
    op.drop_index("ix_essayrevisionattempt_status", table_name="essayrevisionattempt")
    op.drop_index("ix_essayrevisionattempt_idempotency_key", table_name="essayrevisionattempt")
    op.drop_index(
        "ix_essayrevisionattempt_submitted_content_hash",
        table_name="essayrevisionattempt",
    )
    op.drop_index(
        "ix_essayrevisionattempt_target_round_index",
        table_name="essayrevisionattempt",
    )
    op.drop_index("ix_essayrevisionattempt_base_version_id", table_name="essayrevisionattempt")
    op.drop_index("ix_essayrevisionattempt_essay_id", table_name="essayrevisionattempt")
    op.drop_table("essayrevisionattempt")

    op.drop_index("uq_essay_version_round_per_essay", table_name="essayversion")
    op.drop_index("ix_essayversion_round_index", table_name="essayversion")
    op.drop_column("essayversion", "round_index")

    op.drop_index("ix_essay_hidden_by", table_name="essay")
    op.drop_index("ix_essay_hidden_at", table_name="essay")
    op.drop_index("ix_essay_visibility_changed_at", table_name="essay")
    op.drop_index("ix_essay_last_version_submitted_at", table_name="essay")
    op.drop_column("essay", "hidden_by")
    op.drop_column("essay", "hidden_at")
    op.drop_column("essay", "visibility_changed_at")
    op.drop_column("essay", "last_version_submitted_at")
    op.drop_column("essay", "updated_at")
