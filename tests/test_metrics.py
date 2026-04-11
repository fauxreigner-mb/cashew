#!/usr/bin/env python3
"""Tests for core/metrics.py"""

import os
import json
import sqlite3
import tempfile
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

from core.metrics import (
    is_metrics_enabled,
    ensure_metrics_table,
    record_metric,
    timing_decorator,
    get_metrics_summary,
    get_metrics_timeseries,
    get_recent_metrics,
    get_retrieval_stats,
    clear_metrics,
    export_metrics,
)


@pytest.fixture
def metrics_db(temp_db):
    """temp_db with metrics table and some sample metrics."""
    ensure_metrics_table(temp_db)
    conn = sqlite3.connect(temp_db)
    c = conn.cursor()
    now = datetime.now()

    rows = [
        ((now - timedelta(hours=2)).isoformat(), "retrieval", 150.0,
         json.dumps({"embed_time_ms": 5, "search_time_ms": 100, "bfs_time_ms": 45,
                      "seeds_found": 5, "bfs_explored": 20, "results_returned": 10,
                      "overlap_ratio": 0.4})),
        ((now - timedelta(hours=1)).isoformat(), "retrieval", 200.0,
         json.dumps({"embed_time_ms": 6, "search_time_ms": 130, "bfs_time_ms": 64,
                      "seeds_found": 5, "bfs_explored": 30, "results_returned": 10,
                      "overlap_ratio": 0.6})),
        ((now - timedelta(minutes=30)).isoformat(), "search", 12.0,
         json.dumps({"used_sqlite_vec": True, "result_count": 10})),
        ((now - timedelta(minutes=10)).isoformat(), "extraction", 5000.0,
         json.dumps({"nodes_created": 3, "edges_created": 2})),
    ]
    for ts, mt, dur, meta in rows:
        c.execute("INSERT INTO metrics (timestamp, metric_type, duration_ms, metadata) VALUES (?,?,?,?)",
                  (ts, mt, dur, meta))
    conn.commit()
    conn.close()
    return temp_db


class TestIsMetricsEnabled:
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CASHEW_METRICS", None)
            assert is_metrics_enabled() is False

    def test_enabled(self):
        with patch.dict(os.environ, {"CASHEW_METRICS": "1"}):
            assert is_metrics_enabled() is True

    def test_disabled_explicit(self):
        with patch.dict(os.environ, {"CASHEW_METRICS": "0"}):
            assert is_metrics_enabled() is False


class TestEnsureMetricsTable:
    def test_creates_table(self, temp_db):
        ensure_metrics_table(temp_db)
        conn = sqlite3.connect(temp_db)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'")
        assert c.fetchone() is not None
        conn.close()

    def test_idempotent(self, temp_db):
        ensure_metrics_table(temp_db)
        ensure_metrics_table(temp_db)  # should not raise


class TestRecordMetric:
    def test_records_when_enabled(self, temp_db):
        with patch.dict(os.environ, {"CASHEW_METRICS": "1"}):
            record_metric(temp_db, "test_type", 42.0, foo="bar")

        conn = sqlite3.connect(temp_db)
        c = conn.cursor()
        c.execute("SELECT metric_type, duration_ms, metadata FROM metrics")
        row = c.fetchone()
        conn.close()
        assert row[0] == "test_type"
        assert row[1] == 42.0
        assert json.loads(row[2])["foo"] == "bar"

    def test_skips_when_disabled(self, temp_db):
        with patch.dict(os.environ, {"CASHEW_METRICS": "0"}):
            record_metric(temp_db, "test_type", 42.0)

        conn = sqlite3.connect(temp_db)
        c = conn.cursor()
        # table might not even exist
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'")
        if c.fetchone():
            c.execute("SELECT COUNT(*) FROM metrics")
            assert c.fetchone()[0] == 0
        conn.close()

    def test_no_metadata(self, temp_db):
        with patch.dict(os.environ, {"CASHEW_METRICS": "1"}):
            record_metric(temp_db, "simple", 10.0)

        conn = sqlite3.connect(temp_db)
        c = conn.cursor()
        c.execute("SELECT metadata FROM metrics")
        row = c.fetchone()
        conn.close()
        assert row[0] is None


class TestTimingDecorator:
    def test_records_timing(self, temp_db):
        @timing_decorator("test_op")
        def dummy_fn(db_path):
            return [1, 2, 3]

        with patch.dict(os.environ, {"CASHEW_METRICS": "1"}):
            result = dummy_fn(temp_db)

        assert result == [1, 2, 3]
        conn = sqlite3.connect(temp_db)
        c = conn.cursor()
        c.execute("SELECT metric_type, metadata FROM metrics")
        row = c.fetchone()
        conn.close()
        assert row[0] == "test_op"
        assert json.loads(row[1])["result_count"] == 3

    def test_passthrough_when_disabled(self, temp_db):
        @timing_decorator("test_op")
        def dummy_fn(db_path):
            return "ok"

        with patch.dict(os.environ, {"CASHEW_METRICS": "0"}):
            assert dummy_fn(temp_db) == "ok"


class TestGetMetricsSummary:
    def test_returns_summary(self, metrics_db):
        summary = get_metrics_summary(metrics_db, hours=24)
        assert summary["total_queries"] == 4
        assert "retrieval" in summary["by_type"]
        assert "search" in summary["by_type"]
        assert summary["system_health"]["node_count"] >= 0

    def test_empty_db(self, temp_db):
        summary = get_metrics_summary(temp_db, hours=24)
        assert summary["total_queries"] == 0

    def test_narrow_window(self, metrics_db):
        # Only metrics from last 5 minutes
        summary = get_metrics_summary(metrics_db, hours=0)
        assert summary["total_queries"] == 0


class TestGetMetricsTimeseries:
    def test_retrieval_timeseries(self, metrics_db):
        ts = get_metrics_timeseries(metrics_db, "retrieval", hours=24)
        assert len(ts) == 2
        assert all("duration_ms" in p for p in ts)
        assert all("metadata" in p for p in ts)

    def test_no_data(self, metrics_db):
        ts = get_metrics_timeseries(metrics_db, "nonexistent", hours=24)
        assert ts == []


class TestGetRecentMetrics:
    def test_returns_recent(self, metrics_db):
        recent = get_recent_metrics(metrics_db, limit=10)
        assert len(recent) == 4
        # Most recent first
        assert recent[0]["metric_type"] == "extraction"

    def test_limit(self, metrics_db):
        recent = get_recent_metrics(metrics_db, limit=2)
        assert len(recent) == 2


class TestGetRetrievalStats:
    def test_returns_stats(self, metrics_db):
        stats = get_retrieval_stats(metrics_db, hours=24)
        assert stats["timing_breakdown"]["avg_embed_time"] == 5.5
        assert stats["bfs_value"]["avg_overlap_ratio"] == 0.5
        assert stats["exploration_stats"]["avg_seeds_found"] == 5.0

    def test_empty(self, temp_db):
        stats = get_retrieval_stats(temp_db, hours=24)
        assert stats["timing_breakdown"]["avg_embed_time"] == 0


class TestClearMetrics:
    def test_clears_all(self, metrics_db):
        clear_metrics(metrics_db)
        recent = get_recent_metrics(metrics_db)
        assert len(recent) == 0


class TestExportMetrics:
    def test_exports_all(self, metrics_db):
        export = export_metrics(metrics_db, hours=24)
        assert "summary" in export
        assert "retrieval_stats" in export
        assert "recent_metrics" in export
        assert "timeseries" in export
        assert "retrieval" in export["timeseries"]
