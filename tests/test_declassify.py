#!/usr/bin/env python3
"""Tests for scripts/declassify.py"""

import sqlite3
import json
import pytest
from datetime import datetime, timezone, timedelta

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.declassify import (
    is_permanently_private,
    classify_node,
    get_candidates,
    declassify_nodes,
    get_stats,
)


@pytest.fixture
def vault_db(temp_db):
    """temp_db with vault:private nodes of varying ages."""
    conn = sqlite3.connect(temp_db)
    c = conn.cursor()
    # Add tags column if missing (conftest schema may not include it)
    try:
        c.execute("ALTER TABLE thought_nodes ADD COLUMN tags TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    now = datetime.now(timezone.utc)

    nodes = [
        # Old enough to be candidates (>7 days)
        ("v1", "Raj prefers functional programming", "insight", "tech",
         "vault:private", (now - timedelta(days=14)).isoformat()),
        ("v2", "My salary is 200k", "fact", "career",
         "vault:private", (now - timedelta(days=10)).isoformat()),
        ("v3", "Systems thinking is powerful", "belief", "philosophy",
         "vault:private", (now - timedelta(days=20)).isoformat()),
        # Too recent
        ("v4", "New project idea about graphs", "observation", "tech",
         "vault:private", (now - timedelta(days=2)).isoformat()),
        # Public node
        ("p1", "Python is great", "fact", "tech",
         None, (now - timedelta(days=30)).isoformat()),
        # Decayed private
        ("d1", "Old private thought", "fact", "tech",
         "vault:private", (now - timedelta(days=60)).isoformat()),
    ]
    for nid, content, ntype, domain, tags, ts in nodes:
        decayed = 1 if nid == "d1" else 0
        c.execute("""INSERT INTO thought_nodes 
                     (id, content, node_type, domain, tags, timestamp, confidence, decayed, metadata)
                     VALUES (?,?,?,?,?,?,0.8,?,'{}'
                  )""", (nid, content, ntype, domain, tags, ts, decayed))
    conn.commit()
    conn.close()
    return temp_db


class TestIsPermanentlyPrivate:
    def test_salary(self):
        assert is_permanently_private("My salary is $200,000") is True

    def test_password(self):
        assert is_permanently_private("The password for the server is abc123") is True

    def test_safe_content(self):
        assert is_permanently_private("Python is a good programming language") is False

    def test_api_key(self):
        assert is_permanently_private("Use this API key: sk-xxx") is True

    def test_case_insensitive(self):
        assert is_permanently_private("My SALARY is high") is True


class TestClassifyNode:
    def test_permanent_private(self):
        node = {"content": "Bank account number: 12345", "node_type": "fact"}
        assert classify_node(node) == "permanent_private"

    def test_needs_review(self):
        node = {"content": "Graph databases are interesting", "node_type": "insight"}
        assert classify_node(node) == "needs_review"


class TestGetCandidates:
    def test_finds_old_private_nodes(self, vault_db):
        candidates = get_candidates(vault_db, min_age_days=7)
        ids = [c["id"] for c in candidates]
        assert "v1" in ids
        assert "v2" in ids
        assert "v3" in ids

    def test_excludes_recent(self, vault_db):
        candidates = get_candidates(vault_db, min_age_days=7)
        ids = [c["id"] for c in candidates]
        assert "v4" not in ids

    def test_excludes_decayed(self, vault_db):
        candidates = get_candidates(vault_db, min_age_days=7)
        ids = [c["id"] for c in candidates]
        assert "d1" not in ids

    def test_excludes_public(self, vault_db):
        candidates = get_candidates(vault_db, min_age_days=7)
        ids = [c["id"] for c in candidates]
        assert "p1" not in ids

    def test_custom_age(self, vault_db):
        candidates = get_candidates(vault_db, min_age_days=15)
        ids = [c["id"] for c in candidates]
        assert "v3" in ids
        assert "v1" not in ids  # only 14 days old


class TestDeclassifyNodes:
    def test_removes_vault_tag(self, vault_db):
        count = declassify_nodes(vault_db, ["v1", "v3"])
        assert count == 2

        conn = sqlite3.connect(vault_db)
        c = conn.cursor()
        c.execute("SELECT tags FROM thought_nodes WHERE id = 'v1'")
        tags = c.fetchone()[0]
        assert "vault:private" not in (tags or "")
        conn.close()

    def test_empty_list(self, vault_db):
        count = declassify_nodes(vault_db, [])
        assert count == 0

    def test_nonexistent_id(self, vault_db):
        count = declassify_nodes(vault_db, ["nonexistent"])
        assert count == 0

    def test_preserves_other_tags(self, vault_db):
        # Add multi-tag node
        conn = sqlite3.connect(vault_db)
        c = conn.cursor()
        c.execute("UPDATE thought_nodes SET tags = 'vault:private,engineering,important' WHERE id = 'v1'")
        conn.commit()
        conn.close()

        declassify_nodes(vault_db, ["v1"])

        conn = sqlite3.connect(vault_db)
        c = conn.cursor()
        c.execute("SELECT tags FROM thought_nodes WHERE id = 'v1'")
        tags = c.fetchone()[0]
        conn.close()
        assert "vault:private" not in tags
        assert "engineering" in tags
        assert "important" in tags


class TestGetStats:
    def test_returns_stats(self, vault_db):
        stats = get_stats(vault_db)
        assert stats["private"] == 4  # v1, v2, v3, v4 (not d1 — decayed)
        assert stats["total_active"] == 5  # all except d1
        assert stats["public"] == 1  # p1
        assert 0 < stats["private_pct"] < 100
