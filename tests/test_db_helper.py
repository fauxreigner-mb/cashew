"""
Integration tests for core.db — the shared DB chokepoint.

These exercise the helper against real ephemeral sqlite files (no mocks).
They mirror the flows that declassify.py and backfill_referent_time.py use
so regressions in the helper surface before they hit the scripts.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from core import db as cdb


# --------------------------------------------------------------------------
# Fixtures: ephemeral DB with the minimal schema scripts depend on.
# --------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE thought_nodes (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    node_type TEXT NOT NULL,
    domain TEXT,
    timestamp TEXT,
    access_count INTEGER DEFAULT 0,
    last_accessed TEXT,
    confidence REAL,
    source_file TEXT,
    decayed INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    last_updated TEXT,
    mood_state TEXT,
    permanent INTEGER DEFAULT 0,
    tags TEXT,
    referent_time TEXT
);

CREATE TABLE derivation_edges (
    parent_id TEXT,
    child_id TEXT,
    weight REAL,
    reasoning TEXT,
    PRIMARY KEY (parent_id, child_id)
);

CREATE TABLE embeddings (
    node_id TEXT PRIMARY KEY,
    vector BLOB NOT NULL,
    model TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "graph.db"
    conn = sqlite3.connect(str(path))
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def seeded_db(db_path: str) -> str:
    """DB pre-populated with a few nodes, including a vault:private one."""
    conn = cdb.connect(db_path)
    conn.executemany(
        "INSERT INTO thought_nodes (id, content, node_type, timestamp, tags) VALUES (?, ?, ?, ?, ?)",
        [
            ("n1", "public insight",  "insight",     "2024-01-01T00:00:00", "public,blue"),
            ("n2", "private thought", "observation", "2024-01-02T00:00:00", "vault:private,red"),
            ("n3", "another public",  "fact",        "2024-01-03T00:00:00", ""),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


# --------------------------------------------------------------------------
# Connection lifecycle
# --------------------------------------------------------------------------

def test_connect_returns_sqlite_connection(db_path):
    conn = cdb.connect(db_path)
    try:
        assert isinstance(conn, sqlite3.Connection)
        # Fresh connection must be usable for ad-hoc queries.
        row = conn.execute("SELECT 1").fetchone()
        assert row == (1,)
    finally:
        conn.close()


def test_resolve_db_path_override_wins(monkeypatch, db_path):
    monkeypatch.setenv("CASHEW_DB_PATH", "/nonexistent/path.db")
    assert cdb.resolve_db_path(db_path) == db_path


def test_resolve_db_path_env_var(monkeypatch, db_path):
    monkeypatch.setenv("CASHEW_DB_PATH", db_path)
    assert cdb.resolve_db_path(None) == db_path


# --------------------------------------------------------------------------
# Transaction semantics
# --------------------------------------------------------------------------

def test_transaction_commits_on_success(db_path):
    with cdb.transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO thought_nodes (id, content, node_type) VALUES (?, ?, ?)",
            ("n-ok", "ok", "fact"),
        )
    # Independent connection sees the write.
    check = cdb.connect(db_path)
    try:
        assert check.execute(
            "SELECT content FROM thought_nodes WHERE id = ?", ("n-ok",)
        ).fetchone() == ("ok",)
    finally:
        check.close()


def test_transaction_rolls_back_on_error(db_path):
    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom):
        with cdb.transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO thought_nodes (id, content, node_type) VALUES (?, ?, ?)",
                ("n-bad", "bad", "fact"),
            )
            raise Boom("fail mid-transaction")

    check = cdb.connect(db_path)
    try:
        row = check.execute(
            "SELECT id FROM thought_nodes WHERE id = ?", ("n-bad",)
        ).fetchone()
        assert row is None
    finally:
        check.close()


# --------------------------------------------------------------------------
# Schema introspection / migration idempotency
# --------------------------------------------------------------------------

def test_pragma_columns_and_table_exists(db_path):
    conn = cdb.connect(db_path)
    try:
        cols = cdb.pragma_columns(conn, cdb.NODES_TABLE)
        assert "referent_time" in cols
        assert "tags" in cols
        assert cdb.table_exists(conn, cdb.EDGES_TABLE)
        assert not cdb.table_exists(conn, "does_not_exist")
    finally:
        conn.close()


def test_execute_migration_is_idempotent(db_path):
    migration = """
    CREATE TABLE IF NOT EXISTS notes (
        id TEXT PRIMARY KEY,
        body TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_notes_id ON notes(id);
    """
    # Run twice — second run must not error.
    cdb.execute_migration(migration, db_path)
    cdb.execute_migration(migration, db_path)

    conn = cdb.connect(db_path)
    try:
        assert cdb.table_exists(conn, "notes")
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Query primitives — CRUD
# --------------------------------------------------------------------------

def test_get_node_and_tags(seeded_db):
    conn = cdb.connect(seeded_db)
    try:
        row = cdb.get_node(conn, "n2", columns=("id", "content", "tags"))
        assert row == ("n2", "private thought", "vault:private,red")
        assert cdb.get_node(conn, "missing") is None
        assert cdb.get_node_tags(conn, "n1") == "public,blue"
    finally:
        conn.close()


def test_set_and_merge_node_tags(seeded_db):
    with cdb.transaction(seeded_db) as conn:
        cdb.set_node_tags(conn, "n3", "alpha,beta")
        cdb.merge_node_tags(conn, "n1", ["green", "blue"])  # blue already present

    conn = cdb.connect(seeded_db)
    try:
        assert cdb.get_node_tags(conn, "n3") == "alpha,beta"
        # Merge should union + sort, no duplicates.
        assert cdb.get_node_tags(conn, "n1") == "blue,green,public"
    finally:
        conn.close()


def test_iter_nodes_streams_all(seeded_db):
    conn = cdb.connect(seeded_db)
    try:
        ids = sorted(
            row[0]
            for row in cdb.iter_nodes(
                conn, columns=("id",), batch_size=1
            )
        )
        assert ids == ["n1", "n2", "n3"]

        # With where clause.
        private = [
            row[0]
            for row in cdb.iter_nodes(
                conn,
                where="tags LIKE ?",
                params=("%vault:private%",),
                columns=("id",),
            )
        ]
        assert private == ["n2"]
    finally:
        conn.close()


# --------------------------------------------------------------------------
# End-to-end flows mirroring the scripts we migrated.
# --------------------------------------------------------------------------

def test_declassify_flow_via_helper(seeded_db):
    """Mirrors scripts/declassify.py: find vault:private nodes, strip the tag."""
    # Find candidates.
    with cdb.transaction(seeded_db) as conn:
        candidates = list(
            cdb.iter_nodes(
                conn,
                where="tags LIKE ?",
                params=("%vault:private%",),
                columns=("id",),
            )
        )
    assert [c[0] for c in candidates] == ["n2"]

    # Strip the tag using the same REPLACE pattern the script uses.
    with cdb.transaction(seeded_db) as conn:
        for (node_id,) in candidates:
            for pat in ("vault:private,", ",vault:private", "vault:private"):
                cdb.execute(
                    conn,
                    f"UPDATE {cdb.NODES_TABLE} SET tags = REPLACE(tags, ?, '') WHERE id = ?",
                    (pat, node_id),
                )

    conn = cdb.connect(seeded_db)
    try:
        tags = cdb.get_node_tags(conn, "n2")
        assert "vault:private" not in tags
        assert "red" in tags
    finally:
        conn.close()


def test_backfill_referent_time_flow_via_helper(seeded_db):
    """Mirrors scripts/backfill_referent_time.py: set referent_time for null rows."""
    # Baseline: all rows have referent_time NULL.
    conn = cdb.connect(seeded_db)
    try:
        rows = cdb.execute(
            conn,
            f"SELECT id, referent_time FROM {cdb.NODES_TABLE}",
        ).fetchall()
        assert all(rt is None for _id, rt in rows)
    finally:
        conn.close()

    updates = [("2024-06-01T00:00:00+00:00", "n1"), ("2024-06-02T00:00:00+00:00", "n3")]
    with cdb.transaction(seeded_db) as conn:
        cursor = cdb.executemany(
            conn,
            f"UPDATE {cdb.NODES_TABLE} SET referent_time = ? "
            "WHERE id = ? AND referent_time IS NULL",
            updates,
        )
        # Both target rows updated.
        assert cursor.rowcount == 2

    conn = cdb.connect(seeded_db)
    try:
        mapping = {
            r[0]: r[1]
            for r in cdb.execute(
                conn, f"SELECT id, referent_time FROM {cdb.NODES_TABLE}"
            ).fetchall()
        }
        assert mapping["n1"] == "2024-06-01T00:00:00+00:00"
        assert mapping["n3"] == "2024-06-02T00:00:00+00:00"
        assert mapping["n2"] is None
    finally:
        conn.close()


def test_schema_constants_match_real_table(db_path):
    """Guardrail: the column names we hard-code as constants must actually
    exist on the freshly-created schema. Catches drift between the constant
    list and cashew_init.py."""
    conn = cdb.connect(db_path)
    try:
        actual = set(cdb.pragma_columns(conn, cdb.NODES_TABLE))
        # Every declared constant column must exist in the real table.
        for col in cdb.NODE_COLUMNS:
            assert col in actual, f"constant column '{col}' missing from real schema"
    finally:
        conn.close()
