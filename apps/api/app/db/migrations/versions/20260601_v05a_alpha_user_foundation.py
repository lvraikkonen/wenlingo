"""Add alpha user foundation schema."""

import sqlalchemy as sa
from alembic import op


revision = "20260601_v05a_user_foundation"
down_revision = "20260527_alpha_feedback_obs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parentaccount",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email_normalized", sa.String(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("phone_e164", sa.String(), nullable=True),
        sa.Column("phone_bound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_parentaccount_email_normalized",
        "parentaccount",
        ["email_normalized"],
        unique=True,
    )
    op.create_index(
        "ix_parentaccount_phone_e164",
        "parentaccount",
        ["phone_e164"],
        unique=False,
    )
    op.create_index(
        "ix_parentaccount_status",
        "parentaccount",
        ["status"],
        unique=False,
    )

    op.add_column("parentuser", sa.Column("account_id", sa.String(), nullable=True))
    op.add_column(
        "parentuser",
        sa.Column("account_linked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_parentuser_account_id",
        "parentuser",
        ["account_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_parentuser_account_id_parentaccount",
        "parentuser",
        "parentaccount",
        ["account_id"],
        ["id"],
    )

    op.create_table(
        "authmagiccode",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email_normalized", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("alpha_session_id", sa.String(), nullable=False),
        sa.Column("request_ip_hash", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_authmagiccode_email_normalized",
        "authmagiccode",
        ["email_normalized"],
        unique=False,
    )
    op.create_index(
        "ix_authmagiccode_code_hash",
        "authmagiccode",
        ["code_hash"],
        unique=False,
    )
    op.create_index(
        "ix_authmagiccode_purpose",
        "authmagiccode",
        ["purpose"],
        unique=False,
    )
    op.create_index(
        "ix_authmagiccode_alpha_session_id",
        "authmagiccode",
        ["alpha_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_authmagiccode_request_ip_hash",
        "authmagiccode",
        ["request_ip_hash"],
        unique=False,
    )
    op.create_index(
        "ix_authmagiccode_expires_at",
        "authmagiccode",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_authmagiccode_consumed_at",
        "authmagiccode",
        ["consumed_at"],
        unique=False,
    )

    op.create_table(
        "parentsession",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["parentaccount.id"],
            name="fk_parentsession_account_id_parentaccount",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_parentsession_account_id",
        "parentsession",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_parentsession_token_hash",
        "parentsession",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_parentsession_expires_at",
        "parentsession",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_parentsession_revoked_at",
        "parentsession",
        ["revoked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_parentsession_revoked_at", table_name="parentsession")
    op.drop_index("ix_parentsession_expires_at", table_name="parentsession")
    op.drop_index("ix_parentsession_token_hash", table_name="parentsession")
    op.drop_index("ix_parentsession_account_id", table_name="parentsession")
    op.drop_table("parentsession")

    op.drop_index("ix_authmagiccode_consumed_at", table_name="authmagiccode")
    op.drop_index("ix_authmagiccode_expires_at", table_name="authmagiccode")
    op.drop_index("ix_authmagiccode_request_ip_hash", table_name="authmagiccode")
    op.drop_index("ix_authmagiccode_alpha_session_id", table_name="authmagiccode")
    op.drop_index("ix_authmagiccode_purpose", table_name="authmagiccode")
    op.drop_index("ix_authmagiccode_code_hash", table_name="authmagiccode")
    op.drop_index("ix_authmagiccode_email_normalized", table_name="authmagiccode")
    op.drop_table("authmagiccode")

    op.drop_constraint(
        "fk_parentuser_account_id_parentaccount",
        "parentuser",
        type_="foreignkey",
    )
    op.drop_index("ix_parentuser_account_id", table_name="parentuser")
    op.drop_column("parentuser", "account_linked_at")
    op.drop_column("parentuser", "account_id")

    op.drop_index("ix_parentaccount_status", table_name="parentaccount")
    op.drop_index("ix_parentaccount_phone_e164", table_name="parentaccount")
    op.drop_index("ix_parentaccount_email_normalized", table_name="parentaccount")
    op.drop_table("parentaccount")
