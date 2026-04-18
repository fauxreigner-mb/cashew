"""
Happy-path integration test for core.backup.

Exercises create_backup end-to-end against an ephemeral SQLite DB,
verifying that the VACUUM INTO path (routed through core.db) produces
a readable backup file. Mirrors the fixture style in test_db_helper.py.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core import backup as cbackup


_SCHEMA_SQL = """
CREATE TABLE thought_nodes (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    node_type TEXT NOT NULL
);
"""


@pytest.fixture
def seeded_db(tmp_path: Path) -> Path:
    path = tmp_path / "graph.db"
    conn = sqlite3.connect(str(path))
    conn.executescript(_SCHEMA_SQL)
    conn.execute(
        "INSERT INTO thought_nodes (id, content, node_type) VALUES (?, ?, ?)",
        ("n1", "hello", "fact"),
    )
    conn.commit()
    conn.close()
    return path


def test_create_backup_produces_readable_file(seeded_db: Path, tmp_path: Path):
    backup_dir = tmp_path / "backups"
    result = cbackup.create_backup(
        db_path=str(seeded_db),
        backup_dir=str(backup_dir),
    )
    assert result is not None, "create_backup returned None on happy path"

    backup_path = Path(result)
    assert backup_path.exists(), "backup file was not created on disk"
    assert backup_path.stat().st_size > 0
    assert backup_path.parent == backup_dir
    assert backup_path.name.startswith("graph.db.")

    # The backup must be a valid SQLite DB with our seeded row intact.
    conn = sqlite3.connect(str(backup_path))
    try:
        row = conn.execute(
            "SELECT content FROM thought_nodes WHERE id = ?", ("n1",)
        ).fetchone()
        assert row == ("hello",)
    finally:
        conn.close()


def test_create_backup_missing_source_returns_none(tmp_path: Path):
    missing = tmp_path / "nope.db"
    backup_dir = tmp_path / "backups"
    assert cbackup.create_backup(
        db_path=str(missing), backup_dir=str(backup_dir)
    ) is None
