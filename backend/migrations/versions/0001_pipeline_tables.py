"""Summary pipeline tables: repos, runs, summaries, usage.

These existed before migrations (created at app start), so each one is created only if
it is missing. That lets this migration adopt an existing local database safely.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _missing(name: str) -> bool:
    return not sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _missing("repos"):
        op.create_table(
            "repos",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("github_id", sa.BigInteger, unique=True),
            sa.Column("full_name", sa.String(300), nullable=False),
            sa.Column("installed_at", sa.DateTime, nullable=False),
        )
    if _missing("runs"):
        op.create_table(
            "runs",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("repo_id", sa.Integer, sa.ForeignKey("repos.id")),
            sa.Column("pr_number", sa.Integer),
            sa.Column("commit_sha", sa.String(64)),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("source", sa.String(20), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("message", sa.Text, nullable=False),
            sa.Column("error_kind", sa.String(40)),
            sa.Column("files_total", sa.Integer, nullable=False),
            sa.Column("files_kept", sa.Integer, nullable=False),
            sa.Column("ai_calls", sa.Integer, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("finished_at", sa.DateTime),
        )
    if _missing("summaries"):
        op.create_table(
            "summaries",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id"), unique=True, nullable=False),
            sa.Column("model", sa.String(64), nullable=False),
            sa.Column("comment_markdown", sa.Text, nullable=False),
            sa.Column("result_json", sa.JSON, nullable=False),
            sa.Column("verdict_accurate", sa.String(10)),
            sa.Column("verdict_saved_time", sa.Boolean),
            sa.Column("verdict_note", sa.Text),
            sa.Column("verdict_at", sa.DateTime),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )
    if _missing("usage"):
        op.create_table(
            "usage",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id"), nullable=False),
            sa.Column("model", sa.String(64), nullable=False),
            sa.Column("input_tokens", sa.Integer, nullable=False),
            sa.Column("output_tokens", sa.Integer, nullable=False),
            sa.Column("cost_microusd", sa.Integer, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )


def downgrade() -> None:
    for name in ("usage", "summaries", "runs", "repos"):
        op.drop_table(name)
