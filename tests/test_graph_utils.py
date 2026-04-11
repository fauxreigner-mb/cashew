#!/usr/bin/env python3
"""Tests for core/graph_utils.py"""

import sqlite3
import numpy as np
import pytest
from datetime import datetime, timezone

from core.graph_utils import cosine_similarity, load_embeddings


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        a = np.array([1.0, 2.0])
        b = np.zeros(2)
        assert cosine_similarity(a, b) == 0.0

    def test_both_zero(self):
        a = np.zeros(3)
        b = np.zeros(3)
        assert cosine_similarity(a, b) == 0.0


class TestLoadEmbeddings:
    def test_loads_embeddings(self, temp_db_with_data):
        # Add embeddings for some nodes
        conn = sqlite3.connect(temp_db_with_data)
        c = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        for nid in ["node1", "node2", "node3"]:
            vec = np.random.randn(384).astype(np.float32)
            c.execute("INSERT INTO embeddings (node_id, vector, model, updated_at) VALUES (?,?,?,?)",
                      (nid, vec.tobytes(), "test-model", now))
        conn.commit()
        conn.close()

        node_ids, vectors, meta = load_embeddings(temp_db_with_data)
        assert len(node_ids) == 3
        assert vectors.shape == (3, 384)
        assert all(nid in meta for nid in node_ids)
        assert "content" in meta[node_ids[0]]

    def test_empty_db(self, temp_db):
        node_ids, vectors, meta = load_embeddings(temp_db)
        assert node_ids == []
        assert vectors.size == 0
        assert meta == {}

    def test_skips_decayed_nodes(self, temp_db_with_data):
        conn = sqlite3.connect(temp_db_with_data)
        c = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        # Mark node1 as decayed
        c.execute("UPDATE thought_nodes SET decayed = 1 WHERE id = 'node1'")
        # Add embeddings for node1 and node2
        for nid in ["node1", "node2"]:
            vec = np.random.randn(384).astype(np.float32)
            c.execute("INSERT INTO embeddings (node_id, vector, model, updated_at) VALUES (?,?,?,?)",
                      (nid, vec.tobytes(), "test-model", now))
        conn.commit()
        conn.close()

        node_ids, vectors, meta = load_embeddings(temp_db_with_data)
        assert "node1" not in node_ids
        assert "node2" in node_ids
        assert len(node_ids) == 1

    def test_skips_nan_vectors(self, temp_db_with_data):
        conn = sqlite3.connect(temp_db_with_data)
        c = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        # Insert a NaN vector for node1
        nan_vec = np.full(384, np.nan, dtype=np.float32)
        c.execute("INSERT INTO embeddings (node_id, vector, model, updated_at) VALUES (?,?,?,?)",
                  ("node1", nan_vec.tobytes(), "test-model", now))
        # Insert a good vector for node2
        good_vec = np.random.randn(384).astype(np.float32)
        c.execute("INSERT INTO embeddings (node_id, vector, model, updated_at) VALUES (?,?,?,?)",
                  ("node2", good_vec.tobytes(), "test-model", now))
        conn.commit()
        conn.close()

        node_ids, vectors, meta = load_embeddings(temp_db_with_data)
        assert "node1" not in node_ids
        assert "node2" in node_ids

    def test_skips_zero_vectors(self, temp_db_with_data):
        conn = sqlite3.connect(temp_db_with_data)
        c = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        zero_vec = np.zeros(384, dtype=np.float32)
        c.execute("INSERT INTO embeddings (node_id, vector, model, updated_at) VALUES (?,?,?,?)",
                  ("node1", zero_vec.tobytes(), "test-model", now))
        conn.commit()
        conn.close()

        node_ids, vectors, meta = load_embeddings(temp_db_with_data)
        assert "node1" not in node_ids
