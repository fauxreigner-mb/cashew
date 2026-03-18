#!/usr/bin/env python3
"""
Tests for decay functionality including cascading tree decay
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timezone, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.decay import auto_decay, get_decay_candidates, cascade_decay, simulate_cascade_decay


@pytest.fixture
def decay_test_db():
    """Create a test database with nodes in a tree structure for decay testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    # Create schema
    cursor.execute('''
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
            permanent INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE derivation_edges (
            parent_id TEXT,
            child_id TEXT,
            weight REAL,
            reasoning TEXT,
            confidence REAL,
            timestamp TEXT,
            PRIMARY KEY (parent_id, child_id),
            FOREIGN KEY (parent_id) REFERENCES thought_nodes(id),
            FOREIGN KEY (child_id) REFERENCES thought_nodes(id)
        )
    ''')
    
    # Create test nodes with tree structure
    old_time = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    recent_time = datetime.now(timezone.utc).isoformat()
    
    # Tree structure:
    # root (old, low conf, hotspot) -> child1 (medium conf) -> grandchild1 (low conf)
    #                               -> child2 (high conf)   -> grandchild2 (medium conf)
    # anchored_parent (high conf) -> grandchild1 (multi-parent anchoring)
    # isolated_old (old, low conf, no children)
    
    nodes = [
        ("root", "Root node", "hotspot", old_time, 0.5, 0),  # Should decay
        ("child1", "Child 1", "thought", old_time, 0.6, 0),
        ("child2", "Child 2", "thought", old_time, 0.9, 0),  # High confidence, shouldn't cascade decay
        ("grandchild1", "Grandchild 1", "thought", old_time, 0.4, 0),
        ("grandchild2", "Grandchild 2", "thought", old_time, 0.7, 0),
        ("anchored_parent", "Anchored parent", "thought", recent_time, 0.95, 1),  # Won't decay
        ("isolated_old", "Isolated old", "thought", old_time, 0.3, 0),  # Should decay, no children
        ("recent_node", "Recent node", "thought", recent_time, 0.4, 5)  # Recent, won't decay
    ]
    
    for node_id, content, node_type, timestamp, confidence, access_count in nodes:
        cursor.execute("""
            INSERT INTO thought_nodes 
            (id, content, node_type, timestamp, confidence, access_count, source_file, metadata)
            VALUES (?, ?, ?, ?, ?, ?, 'test', '{}')
        """, (node_id, content, node_type, timestamp, confidence, access_count))
    
    # Create edges for tree structure
    edges = [
        ("root", "child1", "parent_of"),
        ("root", "child2", "parent_of"),
        ("child1", "grandchild1", "parent_of"),
        ("child2", "grandchild2", "parent_of"),
        ("anchored_parent", "grandchild1", "supports")  # Multi-parent anchoring
    ]
    
    for parent_id, child_id, relation in edges:
        cursor.execute("""
            INSERT INTO derivation_edges 
            (parent_id, child_id, reasoning, confidence, timestamp)
            VALUES (?, ?, ?, 0.8, ?)
        """, (parent_id, child_id, relation, recent_time))
    
    conn.commit()
    conn.close()
    
    yield path
    os.unlink(path)


def test_hotspot_immunity_removed(decay_test_db):
    """Test that hotspots are no longer immune to decay"""
    # Get initial candidates - should include the hotspot
    candidates = get_decay_candidates(decay_test_db, min_age_days=10, max_confidence_for_decay=0.85)
    
    # Should find the root hotspot and isolated_old as candidates
    assert candidates['candidates'] >= 2
    assert candidates['hotspot_candidates'] == 1  # Only the root hotspot
    
    # Actually decay them
    result = auto_decay(decay_test_db, min_age_days=10, max_confidence_for_decay=0.85, enable_cascading=False)
    assert result['pruned'] >= 2  # Should include root hotspot and isolated_old


def test_cascade_propagation_basic(decay_test_db):
    """Test that cascade propagates down the tree with confidence penalties"""
    # First manually decay the root node
    conn = sqlite3.connect(decay_test_db)
    cursor = conn.cursor()
    cursor.execute("UPDATE thought_nodes SET decayed = 1 WHERE id = 'root'")
    conn.commit()
    conn.close()
    
    # Run cascade decay from root with higher min_confidence to trigger cascading
    cascade_result = cascade_decay(decay_test_db, "root", decay_factor=0.7, min_confidence=0.5)
    
    # Check that some nodes were cascaded (child1 confidence will be 0.6*0.7=0.42 < 0.5)
    assert cascade_result['cascaded'] > 0
    
    # Check confidence changes and decay status
    conn = sqlite3.connect(decay_test_db)
    cursor = conn.cursor()
    
    # child1 should be decayed: 0.6 * 0.7 = 0.42 < 0.5
    cursor.execute("SELECT confidence, decayed FROM thought_nodes WHERE id = 'child1'")
    child1_conf, child1_decayed = cursor.fetchone()
    assert child1_conf < 0.6  # Should be reduced
    assert child1_conf < 0.5  # Below threshold, so decayed
    assert child1_decayed == 1
    
    # child2 should have reduced confidence but not decayed: 0.9 * 0.7 = 0.63 > 0.5
    cursor.execute("SELECT confidence, decayed FROM thought_nodes WHERE id = 'child2'")
    child2_conf, child2_decayed = cursor.fetchone()
    assert child2_conf < 0.9  # Should be reduced
    assert child2_conf > 0.5  # Above threshold, not decayed
    assert child2_decayed == 0
    
    conn.close()


def test_depth_scaling(decay_test_db):
    """Test that deeper nodes get hit with decay_factor^depth"""
    # Manually decay root and trigger cascade
    conn = sqlite3.connect(decay_test_db)
    cursor = conn.cursor()
    cursor.execute("UPDATE thought_nodes SET decayed = 1 WHERE id = 'root'")
    conn.commit()
    conn.close()
    
    cascade_result = cascade_decay(decay_test_db, "root", decay_factor=0.5)  # Use 0.5 for easier math
    
    conn = sqlite3.connect(decay_test_db)
    cursor = conn.cursor()
    
    # child1: 0.6 * 0.5^1 = 0.3 (right at threshold)
    cursor.execute("SELECT confidence FROM thought_nodes WHERE id = 'child1'")
    child1_conf = cursor.fetchone()[0]
    assert abs(child1_conf - 0.3) < 0.01
    
    # If child1 didn't decay, grandchild1 should get: original * 0.5^2 = 0.4 * 0.25 = 0.1
    # But grandchild1 is anchored by anchored_parent, so it should be skipped
    
    conn.close()


def test_multi_parent_anchoring(decay_test_db):
    """Test that nodes with multiple parents are not penalized if they have a live parent"""
    # Manually decay root
    conn = sqlite3.connect(decay_test_db)
    cursor = conn.cursor()
    cursor.execute("UPDATE thought_nodes SET decayed = 1 WHERE id = 'root'")
    conn.commit()
    
    # Get grandchild1's original confidence
    cursor.execute("SELECT confidence FROM thought_nodes WHERE id = 'grandchild1'")
    original_conf = cursor.fetchone()[0]
    conn.close()
    
    # Run cascade from root
    cascade_decay(decay_test_db, "root", decay_factor=0.7)
    
    # grandchild1 should NOT have been affected because it has anchored_parent as a live parent
    conn = sqlite3.connect(decay_test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT confidence, decayed FROM thought_nodes WHERE id = 'grandchild1'")
    final_conf, is_decayed = cursor.fetchone()
    conn.close()
    
    assert final_conf == original_conf  # Should be unchanged
    assert is_decayed == 0  # Should not be decayed


def test_full_subtree_collapse(decay_test_db):
    """Test that a whole subtree can collapse when all nodes are low confidence"""
    # Create a vulnerable subtree by updating confidence values
    conn = sqlite3.connect(decay_test_db)
    cursor = conn.cursor()
    
    # Make child1 and grandchild1 very low confidence (but remove anchored_parent edge first)
    cursor.execute("DELETE FROM derivation_edges WHERE parent_id = 'anchored_parent'")
    cursor.execute("UPDATE thought_nodes SET confidence = 0.4 WHERE id = 'child1'")
    cursor.execute("UPDATE thought_nodes SET confidence = 0.35 WHERE id = 'grandchild1'")
    
    # Decay root
    cursor.execute("UPDATE thought_nodes SET decayed = 1 WHERE id = 'root'")
    conn.commit()
    conn.close()
    
    # Run cascade with low decay factor and high min_confidence threshold
    cascade_result = cascade_decay(decay_test_db, "root", decay_factor=0.8, min_confidence=0.35)
    
    # Should cascade at least child1
    assert cascade_result['cascaded'] >= 1
    
    # Check that child1 got decayed (0.4 * 0.8 = 0.32 < 0.35)
    conn = sqlite3.connect(decay_test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT decayed FROM thought_nodes WHERE id = 'child1'")
    child1_decayed = cursor.fetchone()[0]
    assert child1_decayed == 1
    conn.close()


def test_auto_decay_with_cascading_integration(decay_test_db):
    """Test the full auto_decay flow with cascading enabled"""
    result = auto_decay(decay_test_db, min_age_days=10, max_confidence_for_decay=0.85, 
                       enable_cascading=True, decay_factor=0.7)
    
    # Should have some direct and possibly some cascaded
    assert result['pruned'] >= 2  # root hotspot + isolated_old at minimum
    assert 'cascaded' in result
    assert 'total' in result
    assert result['total'] == result['pruned'] + result['cascaded']


def test_auto_decay_without_cascading(decay_test_db):
    """Test auto_decay with cascading disabled"""
    result = auto_decay(decay_test_db, min_age_days=10, max_confidence_for_decay=0.85, 
                       enable_cascading=False)
    
    # Should only have direct pruning
    assert result['pruned'] >= 2
    assert result.get('cascaded', 0) == 0
    assert result['total'] == result['pruned']


def test_dry_run_preview(decay_test_db):
    """Test that dry run shows what would be cascaded without modifying"""
    # Get original state
    conn = sqlite3.connect(decay_test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM thought_nodes WHERE decayed = 1")
    original_decayed_count = cursor.fetchone()[0]
    cursor.execute("SELECT confidence FROM thought_nodes WHERE id = 'child1'")
    original_child1_conf = cursor.fetchone()[0]
    conn.close()
    
    # Run dry run with cascade preview
    candidates = get_decay_candidates(decay_test_db, min_age_days=10, max_confidence_for_decay=0.85,
                                    show_cascade_preview=True, decay_factor=0.7)
    
    # Should have preview data
    assert 'cascade_preview' in candidates
    assert 'total_preview' in candidates
    assert candidates['total_preview'] >= candidates['candidates']
    
    # Verify nothing was actually changed
    conn = sqlite3.connect(decay_test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM thought_nodes WHERE decayed = 1")
    final_decayed_count = cursor.fetchone()[0]
    cursor.execute("SELECT confidence FROM thought_nodes WHERE id = 'child1'")
    final_child1_conf = cursor.fetchone()[0]
    conn.close()
    
    assert final_decayed_count == original_decayed_count
    assert final_child1_conf == original_child1_conf


def test_simulate_cascade_decay(decay_test_db):
    """Test the simulation function works correctly"""
    would_cascade = simulate_cascade_decay(decay_test_db, "root", decay_factor=0.7, min_confidence=0.3)
    
    # Should predict some cascading without modifying database
    # (Exact number depends on tree structure and confidence values)
    assert isinstance(would_cascade, int)
    assert would_cascade >= 0
    
    # Verify no actual changes
    conn = sqlite3.connect(decay_test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT confidence FROM thought_nodes WHERE id = 'child1'")
    child1_conf = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM thought_nodes WHERE decayed = 1")
    decayed_count = cursor.fetchone()[0]
    conn.close()
    
    # Original values should be unchanged
    assert child1_conf == 0.6  # Original value
    assert decayed_count == 0  # No nodes should be decayed yet


def test_empty_database_edge_cases(temp_db):
    """Test decay functions handle empty database gracefully"""
    # Test with empty database
    result = auto_decay(temp_db)
    assert result['pruned'] == 0
    assert result.get('cascaded', 0) == 0
    
    candidates = get_decay_candidates(temp_db)
    assert candidates['candidates'] == 0
    assert candidates['hotspot_candidates'] == 0
    
    # Test cascade on non-existent node
    cascade_result = cascade_decay(temp_db, "nonexistent")
    assert cascade_result['cascaded'] == 0


def test_circular_references_handling(decay_test_db):
    """Test that circular references don't cause infinite loops"""
    # Add circular reference
    conn = sqlite3.connect(decay_test_db)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO derivation_edges (parent_id, child_id, weight, reasoning, confidence, timestamp)
        VALUES ('child1', 'root', 0.8, 'circular reference', 0.8, ?)
    """, (datetime.now(timezone.utc).isoformat(),))
    conn.commit()
    conn.close()
    
    # This should not hang or crash
    cascade_result = cascade_decay(decay_test_db, "root", decay_factor=0.7)
    assert isinstance(cascade_result['cascaded'], int)
    assert cascade_result['cascaded'] >= 0