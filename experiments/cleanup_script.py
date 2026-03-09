#!/usr/bin/env python3
"""
Cashew Graph Database Cleanup Script
Cleans up the thought graph by removing noise, duplicates, and orphans.
"""

import sqlite3
import sys
from pathlib import Path

def connect_db(db_path="data/graph.db"):
    return sqlite3.connect(db_path)

def get_stats(conn):
    """Get current database stats"""
    cursor = conn.cursor()
    
    # Node count by type
    cursor.execute("SELECT node_type, COUNT(*) FROM thought_nodes GROUP BY node_type")
    node_types = dict(cursor.fetchall())
    
    # Total nodes and edges
    cursor.execute("SELECT COUNT(*) FROM thought_nodes")
    total_nodes = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM derivation_edges")
    total_edges = cursor.fetchone()[0]
    
    # Orphan count
    cursor.execute("""
        SELECT COUNT(*) FROM thought_nodes tn 
        WHERE NOT EXISTS (SELECT 1 FROM derivation_edges de 
                         WHERE de.parent_id = tn.id OR de.child_id = tn.id)
    """)
    orphans = cursor.fetchone()[0]
    
    return {
        'total_nodes': total_nodes,
        'total_edges': total_edges,
        'orphans': orphans,
        'node_types': node_types
    }

def print_stats(stats, label="Current"):
    print(f"\n{label} Stats:")
    print(f"  Total nodes: {stats['total_nodes']}")
    print(f"  Total edges: {stats['total_edges']}")
    print(f"  Orphan nodes: {stats['orphans']}")
    print(f"  Node types:")
    for node_type, count in sorted(stats['node_types'].items()):
        print(f"    {node_type}: {count}")

def cleanup_low_quality_core_memory(conn):
    """Remove low-quality core_memory nodes that are just metadata"""
    cursor = conn.cursor()
    
    print("\n1. Removing low-quality core_memory nodes...")
    
    # Delete core_memory nodes with confidence < 0.8 that are likely just metadata
    # Keep high-confidence ones that contain real insights
    cursor.execute("""
        DELETE FROM thought_nodes 
        WHERE node_type = 'core_memory' 
        AND confidence < 0.8
        AND (
            content LIKE '2026-__-___%'  -- Date entries
            OR content LIKE '- %'         -- List items
            OR content LIKE 'Manager "%'  -- Manager feedback
            OR content LIKE 'Connected via%' -- Connection metadata
            OR LENGTH(content) < 50       -- Very short entries
        )
    """)
    deleted = cursor.rowcount
    print(f"  Deleted {deleted} low-quality core_memory nodes")
    
    # Also remove orphaned core_memory nodes with low confidence
    cursor.execute("""
        DELETE FROM thought_nodes 
        WHERE node_type = 'core_memory' 
        AND confidence < 0.75
        AND id NOT IN (
            SELECT DISTINCT parent_id FROM derivation_edges 
            UNION 
            SELECT DISTINCT child_id FROM derivation_edges
        )
    """)
    deleted_orphans = cursor.rowcount
    print(f"  Deleted {deleted_orphans} orphaned low-confidence core_memory nodes")
    
    return deleted + deleted_orphans

def remove_duplicate_edges(conn):
    """Remove duplicate edges"""
    cursor = conn.cursor()
    
    print("\n2. Removing duplicate edges...")
    
    # Create a temporary table with unique edges
    cursor.execute("""
        CREATE TEMPORARY TABLE unique_edges AS
        SELECT MIN(rowid) as keep_rowid, parent_id, child_id, relation
        FROM derivation_edges
        GROUP BY parent_id, child_id, relation
    """)
    
    # Delete duplicates
    cursor.execute("""
        DELETE FROM derivation_edges 
        WHERE rowid NOT IN (SELECT keep_rowid FROM unique_edges)
    """)
    deleted = cursor.rowcount
    print(f"  Deleted {deleted} duplicate edges")
    
    cursor.execute("DROP TABLE unique_edges")
    return deleted

def remove_edges_to_deleted_nodes(conn):
    """Clean up edges pointing to nodes that no longer exist"""
    cursor = conn.cursor()
    
    print("\n3. Cleaning up orphaned edges...")
    
    # Remove edges where parent or child node was deleted
    cursor.execute("""
        DELETE FROM derivation_edges 
        WHERE parent_id NOT IN (SELECT id FROM thought_nodes)
        OR child_id NOT IN (SELECT id FROM thought_nodes)
    """)
    deleted = cursor.rowcount
    print(f"  Deleted {deleted} orphaned edges")
    
    return deleted

def remove_remaining_orphans(conn):
    """Remove remaining orphan nodes that add no value"""
    cursor = conn.cursor()
    
    print("\n4. Removing remaining low-value orphans...")
    
    # Remove orphaned core_memory nodes that are still disconnected and low-confidence
    cursor.execute("""
        DELETE FROM thought_nodes 
        WHERE node_type = 'core_memory'
        AND confidence < 0.85
        AND id NOT IN (
            SELECT DISTINCT parent_id FROM derivation_edges 
            UNION 
            SELECT DISTINCT child_id FROM derivation_edges
        )
    """)
    deleted = cursor.rowcount
    print(f"  Deleted {deleted} remaining orphaned core_memory nodes")
    
    return deleted

def main():
    print("Cashew Graph Cleanup Starting...")
    
    conn = connect_db()
    
    # Get initial stats
    initial_stats = get_stats(conn)
    print_stats(initial_stats, "Initial")
    
    # Perform cleanup steps
    total_deleted_nodes = 0
    total_deleted_edges = 0
    
    try:
        # Step 1: Remove low-quality core_memory nodes
        deleted_nodes = cleanup_low_quality_core_memory(conn)
        total_deleted_nodes += deleted_nodes
        
        # Step 2: Remove duplicate edges
        deleted_edges = remove_duplicate_edges(conn)
        total_deleted_edges += deleted_edges
        
        # Step 3: Clean orphaned edges
        deleted_edges = remove_edges_to_deleted_nodes(conn)
        total_deleted_edges += deleted_edges
        
        # Step 4: Remove remaining orphans
        deleted_nodes = remove_remaining_orphans(conn)
        total_deleted_nodes += deleted_nodes
        
        # Commit changes
        conn.commit()
        
        # Get final stats
        final_stats = get_stats(conn)
        print_stats(final_stats, "Final")
        
        print(f"\nCleanup Summary:")
        print(f"  Nodes deleted: {total_deleted_nodes}")
        print(f"  Edges deleted: {total_deleted_edges}")
        print(f"  Nodes remaining: {final_stats['total_nodes']} (was {initial_stats['total_nodes']})")
        print(f"  Edges remaining: {final_stats['total_edges']} (was {initial_stats['total_edges']})")
        print(f"  Orphans remaining: {final_stats['orphans']} (was {initial_stats['orphans']})")
        
        reduction_pct = (1 - final_stats['total_nodes'] / initial_stats['total_nodes']) * 100
        print(f"  Total reduction: {reduction_pct:.1f}%")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        conn.rollback()
        return 1
    
    finally:
        conn.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())