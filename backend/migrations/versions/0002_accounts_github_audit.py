"""Accounts, sessions, audit log, GitHub App installations, our PR comments; runs.user_id.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(320), unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("github_user_id", sa.BigInteger, unique=True),
        sa.Column("github_login", sa.String(100)),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("last_login_at", sa.DateTime),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("last_seen_at", sa.DateTime, nullable=False),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(300)),
    )
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"], unique=True)
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("ip", sa.String(64)),
        sa.Column("request_id", sa.String(64)),
        sa.Column("detail", sa.JSON, nullable=False),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_event", "audit_log", ["event"])
    op.create_table(
        "github_installations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("installation_id", sa.BigInteger, nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("account_login", sa.String(100), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("account_id", sa.BigInteger),
        sa.Column("repository_selection", sa.String(20)),
        sa.Column("repo_count", sa.Integer),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("suspended_at", sa.DateTime),
        sa.Column("deleted_at", sa.DateTime),
    )
    op.create_index(
        "ix_github_installations_installation_id",
        "github_installations",
        ["installation_id"],
        unique=True,
    )
    op.create_index("ix_github_installations_user_id", "github_installations", ["user_id"])
    op.create_table(
        "pr_comments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("repo_full_name", sa.String(200), nullable=False),
        sa.Column("pr_number", sa.Integer, nullable=False),
        sa.Column("comment_id", sa.BigInteger, nullable=False),
        sa.Column("installation_id", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("repo_full_name", "pr_number", name="uq_pr_comment"),
    )
    with op.batch_alter_table("runs") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer))
        batch.create_foreign_key("fk_runs_user_id", "users", ["user_id"], ["id"])
        batch.create_index("ix_runs_user_id", ["user_id"])


def downgrade() -> None:
    with op.batch_alter_table("runs") as batch:
        batch.drop_index("ix_runs_user_id")
        batch.drop_constraint("fk_runs_user_id", type_="foreignkey")
        batch.drop_column("user_id")
    for name in ("pr_comments", "github_installations", "audit_log", "sessions", "users"):
        op.drop_table(name)
