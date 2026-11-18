"""Migrations build the same schema as the models, and adopt a pre-migration database."""

from alembic import command
from alembic.config import Config
from sqlalchemy import Column, MetaData, Table, create_engine, inspect

import app.models  # noqa: F401
from app.db import Base


def alembic_cfg(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def columns(url: str) -> dict[str, set[str]]:
    engine = create_engine(url)
    insp = inspect(engine)
    out = {
        t: {c["name"] for c in insp.get_columns(t)}
        for t in insp.get_table_names()
        if t != "alembic_version"
    }
    engine.dispose()
    return out


def test_upgrade_matches_models_and_downgrades(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    command.upgrade(alembic_cfg(url), "head")
    expected = {t.name: {c.name for c in t.columns} for t in Base.metadata.sorted_tables}
    assert columns(url) == expected
    command.downgrade(alembic_cfg(url), "base")
    assert columns(url) == {}


def test_adopts_a_database_created_before_migrations(tmp_path):
    """The local Postgres was made by create_all with the 4 original tables."""
    url = f"sqlite:///{tmp_path / 'old.db'}"
    md = MetaData()
    for name in ("repos", "runs", "summaries", "usage"):
        cols = [
            Column(c.name, c.type, primary_key=c.primary_key)
            for c in Base.metadata.tables[name].columns
            if not (name == "runs" and c.name == "user_id")
        ]
        Table(name, md, *cols)
    engine = create_engine(url)
    md.create_all(engine)
    engine.dispose()

    command.upgrade(alembic_cfg(url), "head")
    cols = columns(url)
    assert "user_id" in cols["runs"]
    assert {"users", "sessions", "audit_log", "github_installations", "pr_comments"} <= set(cols)
