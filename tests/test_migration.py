#!/usr/bin/env python3
"""
Test suite for cashew brain migration
Validates Phase 1 migration from graph.db to brain.db
"""

import sqlite3
import json
import pytest
from pathlib import Path

# Test configuration
BASE_DIR = Path(__file__).parent.parent
SOURCE_DB = BASE_DIR / "data" / "graph.db"
TARGET_DB = BASE_DIR / "data" / "brain.db"
REPORT_PATH = BASE_DIR / "migration_report.json"

VALID_NODE_TYPES = {'observation', 'belief', 'decision', 'insight', 'fact'}
VALID_DOMAINS = {'work', 'personal', 'fitness', 'engineering', 'philosophy', 'music', 'relationships', 'meta'}

def test_databases_exist():
    """Verify both source and target databases exist"""
    assert SOURCE_DB.exists(), f"Source database missing: {SOURCE_DB}"
    assert TARGET_DB.exists(), f"Target database missing: {TARGET_DB}"

def test_original_db_untouched():
    """Verify source database was not modified"""
    # Check that original tables still exist with original schema
    source_conn = sqlite3.connect(SOURCE_DB)
    cursor = source_conn.cursor()
    
    # Check thought_nodes table exists with original columns
    cursor.execute("PRAGMA table_info(thought_nodes)")
    columns = [row[1] for row in cursor.fetchall()]
    expected_columns = ['id', 'content', 'node_type', 'timestamp', 'confidence', 
                       'mood_state', 'metadata', 'source_file', 'decayed', 'last_updated']
    
    for col in expected_columns:
        assert col in columns, f"Original column {col} missing from source database"
    
    # Check derivation_edges table exists with relation column
    cursor.execute("PRAGMA table_info(derivation_edges)")
    edge_columns = [row[1] for row in cursor.fetchall()]
    assert 'relation' in edge_columns, "Original relation column missing from source database"
    
    source_conn.close()

def test_new_columns_exist():
    """Verify new brain.db schema has correct columns"""
    target_conn = sqlite3.connect(TARGET_DB)
    cursor = target_conn.cursor()
    
    # Check thought_nodes table
    cursor.execute("PRAGMA table_info(thought_nodes)")
    columns = [row[1] for row in cursor.fetchall()]
    expected_new_columns = ['domain', 'created_at', 'last_accessed', 'access_count', 'source', 'session_id']
    
    for col in expected_new_columns:
        assert col in columns, f"New column {col} missing from target database"
    
    # Check edges table (no relation column)
    cursor.execute("PRAGMA table_info(edges)")
    edge_columns = [row[1] for row in cursor.fetchall()]
    expected_edge_columns = ['source_id', 'target_id', 'weight', 'created_at']
    
    for col in expected_edge_columns:
        assert col in edge_columns, f"Expected edge column {col} missing"
    
    assert 'relation' not in edge_columns, "Old relation column should be removed from edges"
    
    target_conn.close()

def test_all_nodes_preserved():
    """Verify all nodes from source are in target"""
    source_conn = sqlite3.connect(SOURCE_DB)
    target_conn = sqlite3.connect(TARGET_DB)
    
    source_count = source_conn.execute('SELECT COUNT(*) FROM thought_nodes').fetchone()[0]
    target_count = target_conn.execute('SELECT COUNT(*) FROM thought_nodes').fetchone()[0]
    
    assert source_count == target_count, f"Node count mismatch: source={source_count}, target={target_count}"
    
    # Check that all node IDs are preserved
    source_ids = set(row[0] for row in source_conn.execute('SELECT id FROM thought_nodes'))
    target_ids = set(row[0] for row in target_conn.execute('SELECT id FROM thought_nodes'))
    
    assert source_ids == target_ids, "Node IDs don't match between source and target"
    
    source_conn.close()
    target_conn.close()

def test_edge_count_preserved():
    """Verify edge count is preserved (accounting for deduplication)"""
    source_conn = sqlite3.connect(SOURCE_DB)
    target_conn = sqlite3.connect(TARGET_DB)
    
    # Count unique edges in source (parent_id, child_id pairs)
    source_edges = source_conn.execute('SELECT DISTINCT parent_id, child_id FROM derivation_edges').fetchall()
    source_unique_count = len(source_edges)
    
    target_count = target_conn.execute('SELECT COUNT(*) FROM edges').fetchone()[0]
    
    assert target_count <= len(source_conn.execute('SELECT * FROM derivation_edges').fetchall()), \
           "Target has more edges than source total"
    assert target_count >= source_unique_count * 0.9, \
           f"Too many edges lost: source_unique={source_unique_count}, target={target_count}"
    
    source_conn.close()
    target_conn.close()

def test_edges_untyped():
    """Verify edges have no relation column"""
    target_conn = sqlite3.connect(TARGET_DB)
    cursor = target_conn.cursor()
    
    cursor.execute("PRAGMA table_info(edges)")
    columns = [row[1] for row in cursor.fetchall()]
    
    assert 'relation' not in columns, "Edges should not have relation column"
    assert 'source_id' in columns, "Edges should have source_id column"
    assert 'target_id' in columns, "Edges should have target_id column"
    
    target_conn.close()

def test_no_data_loss():
    """Verify content integrity"""
    source_conn = sqlite3.connect(SOURCE_DB)
    target_conn = sqlite3.connect(TARGET_DB)
    
    # Check that content is preserved
    source_contents = source_conn.execute('SELECT id, content FROM thought_nodes ORDER BY id').fetchall()
    target_contents = target_conn.execute('SELECT id, content FROM thought_nodes ORDER BY id').fetchall()
    
    assert len(source_contents) == len(target_contents), "Content count mismatch"
    
    for i, (source_row, target_row) in enumerate(zip(source_contents, target_contents)):
        assert source_row[0] == target_row[0], f"ID mismatch at row {i}"
        assert source_row[1] == target_row[1], f"Content mismatch at row {i} for ID {source_row[0]}"
    
    source_conn.close()
    target_conn.close()

def test_every_node_has_domain():
    """Verify all nodes have a valid domain"""
    target_conn = sqlite3.connect(TARGET_DB)
    
    # Check no NULL domains
    null_domains = target_conn.execute('SELECT COUNT(*) FROM thought_nodes WHERE domain IS NULL').fetchone()[0]
    assert null_domains == 0, f"{null_domains} nodes have NULL domain"
    
    # Check all domains are valid
    invalid_domains = target_conn.execute('''
        SELECT COUNT(*) FROM thought_nodes 
        WHERE domain NOT IN ('work', 'personal', 'fitness', 'engineering', 'philosophy', 'music', 'relationships', 'meta')
    ''').fetchone()[0]
    assert invalid_domains == 0, f"{invalid_domains} nodes have invalid domain"
    
    target_conn.close()

def test_every_node_has_valid_type():
    """Verify all nodes have valid node_type"""
    target_conn = sqlite3.connect(TARGET_DB)
    
    # Check no NULL node_types
    null_types = target_conn.execute('SELECT COUNT(*) FROM thought_nodes WHERE node_type IS NULL').fetchone()[0]
    assert null_types == 0, f"{null_types} nodes have NULL node_type"
    
    # Check all node_types are valid
    invalid_types = target_conn.execute('''
        SELECT COUNT(*) FROM thought_nodes 
        WHERE node_type NOT IN ('observation', 'belief', 'decision', 'insight', 'fact')
    ''').fetchone()[0]
    assert invalid_types == 0, f"{invalid_types} nodes have invalid node_type"
    
    target_conn.close()

def test_node_type_distribution_reasonable():
    """Verify node types are reasonably distributed (not all one type)"""
    target_conn = sqlite3.connect(TARGET_DB)
    
    # Get distribution
    types = target_conn.execute('SELECT node_type, COUNT(*) FROM thought_nodes GROUP BY node_type').fetchall()
    type_counts = {node_type: count for node_type, count in types}
    
    # Should have at least 2 different types
    assert len(type_counts) >= 2, "All nodes classified as same type"
    
    # No single type should dominate more than 80%
    total_nodes = sum(type_counts.values())
    for node_type, count in type_counts.items():
        ratio = count / total_nodes
        assert ratio < 0.8, f"Node type '{node_type}' dominates with {ratio:.1%} of nodes"
    
    target_conn.close()

def test_migration_metadata_correct():
    """Verify migration metadata fields"""
    target_conn = sqlite3.connect(TARGET_DB)
    
    # Check all nodes have source='migration'
    non_migration = target_conn.execute("SELECT COUNT(*) FROM thought_nodes WHERE source != 'migration'").fetchone()[0]
    assert non_migration == 0, f"{non_migration} nodes don't have source='migration'"
    
    # Check all nodes have access_count=0
    non_zero_access = target_conn.execute("SELECT COUNT(*) FROM thought_nodes WHERE access_count != 0").fetchone()[0]
    assert non_zero_access == 0, f"{non_zero_access} nodes have access_count != 0"
    
    # Check created_at and last_accessed are set
    null_created = target_conn.execute("SELECT COUNT(*) FROM thought_nodes WHERE created_at IS NULL").fetchone()[0]
    null_accessed = target_conn.execute("SELECT COUNT(*) FROM thought_nodes WHERE last_accessed IS NULL").fetchone()[0]
    
    assert null_created == 0, f"{null_created} nodes have NULL created_at"
    assert null_accessed == 0, f"{null_accessed} nodes have NULL last_accessed"
    
    target_conn.close()

def test_migration_report_exists():
    """Verify migration report was generated"""
    assert REPORT_PATH.exists(), f"Migration report missing: {REPORT_PATH}"
    
    with open(REPORT_PATH) as f:
        report = json.load(f)
    
    # Check required fields
    required_fields = ['timestamp', 'node_count', 'edge_count', 'node_type_distribution', 'domain_distribution']
    for field in required_fields:
        assert field in report, f"Migration report missing field: {field}"
    
    # Check distributions have data
    assert len(report['node_type_distribution']) > 0, "Empty node type distribution"
    assert len(report['domain_distribution']) > 0, "Empty domain distribution"

def run_all_tests():
    """Run all tests and return summary"""
    test_functions = [
        test_databases_exist,
        test_original_db_untouched,
        test_new_columns_exist,
        test_all_nodes_preserved,
        test_edge_count_preserved,
        test_edges_untyped,
        test_no_data_loss,
        test_every_node_has_domain,
        test_every_node_has_valid_type,
        test_node_type_distribution_reasonable,
        test_migration_metadata_correct,
        test_migration_report_exists
    ]
    
    results = []
    for test_func in test_functions:
        try:
            test_func()
            results.append((test_func.__name__, "PASS", None))
            print(f"✅ {test_func.__name__}")
        except AssertionError as e:
            results.append((test_func.__name__, "FAIL", str(e)))
            print(f"❌ {test_func.__name__}: {e}")
        except Exception as e:
            results.append((test_func.__name__, "ERROR", str(e)))
            print(f"💥 {test_func.__name__}: {e}")
    
    # Summary
    passed = sum(1 for _, status, _ in results if status == "PASS")
    total = len(results)
    
    print(f"\n📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! Migration successful.")
        return True
    else:
        print("⚠️  Some tests failed. Review migration.")
        return False

if __name__ == "__main__":
    run_all_tests()