#!/usr/bin/env python3
"""
Permanence system for cashew thought-graph engine.
Handles marking nodes as permanent based on proven value,
with fractal propagation through the hotspot hierarchy.
"""

import sqlite3
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Set, Tuple, Optional
import logging

logger = logging.getLogger("cashew.permanence")


def evaluate_node_permanence(cursor: sqlite3.Cursor, node_id: str) -> bool:
    """
    Evaluate if a single node should be permanent based on criteria.
    
    Args:
        cursor: Database cursor
        node_id: Node ID to evaluate
        
    Returns:
        True if the node meets permanence criteria
    """
    cursor.execute("""
        SELECT access_count, confidence, timestamp, permanent
        FROM thought_nodes 
        WHERE id = ?
    """, (node_id,))
    
    result = cursor.fetchone()
    if not result:
        return False
    
    access_count, confidence, timestamp, current_permanent = result
    
    # If already manually pinned, keep it permanent
    if current_permanent and current_permanent > 1:  # 2 = manually pinned
        return True
    
    # Criteria for permanence:
    # 1. Frequently retrieved (access_count >= 10)
    if access_count >= 10:
        return True
    
    # 2. Very high confidence knowledge
    if confidence >= 0.95:
        return True
    
    # 3. Stood the test of time (older than 30 days AND access_count >= 5)
    if timestamp:
        try:
            node_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            age = datetime.now(timezone.utc) - node_date
            if age.days >= 30 and access_count >= 5:
                return True
        except (ValueError, TypeError):
            pass
    
    return False


def calculate_hotspot_permanence_ratio(cursor: sqlite3.Cursor, hotspot_id: str) -> float:
    """
    Calculate the ratio of permanent nodes in a hotspot.
    
    Args:
        cursor: Database cursor
        hotspot_id: Hotspot node ID
        
    Returns:
        Ratio of permanent nodes (0.0 to 1.0)
    """
    # Get member nodes via summarizes edges
    cursor.execute("""
        SELECT child_id FROM derivation_edges 
        WHERE parent_id = ? AND relation = 'summarizes'
    """, (hotspot_id,))
    
    cluster_node_ids = [row[0] for row in cursor.fetchall()]
    
    if not cluster_node_ids:
        return 0.0
    
    # Count how many of these nodes are permanent
    permanent_count = 0
    for node_id in cluster_node_ids:
        cursor.execute("""
            SELECT permanent FROM thought_nodes WHERE id = ?
        """, (node_id,))
        
        node_result = cursor.fetchone()
        if node_result and node_result[0]:
            permanent_count += 1
    
    return permanent_count / len(cluster_node_ids)


def evaluate_all_permanence(db_path: str, min_permanent_ratio: float = 0.6, 
                           min_retain_ratio: float = 0.4) -> Dict:
    """
    Evaluate and update permanence for all nodes in the graph.
    
    Args:
        db_path: Path to the database
        min_permanent_ratio: Minimum ratio for hotspot to become permanent (default 60%)
        min_retain_ratio: Minimum ratio for hotspot to retain permanence (default 40%)
        
    Returns:
        Dict with evaluation statistics
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {
        'nodes_evaluated': 0,
        'nodes_made_permanent': 0,
        'nodes_lost_permanence': 0,
        'hotspots_made_permanent': 0,
        'hotspots_lost_permanence': 0
    }
    
    try:
        # First pass: Evaluate leaf nodes (non-hotspots)
        cursor.execute("""
            SELECT id FROM thought_nodes 
            WHERE node_type != 'hotspot' 
            AND (decayed IS NULL OR decayed = 0)
        """)
        
        leaf_nodes = [row[0] for row in cursor.fetchall()]
        
        for node_id in leaf_nodes:
            stats['nodes_evaluated'] += 1
            should_be_permanent = evaluate_node_permanence(cursor, node_id)
            
            # Check current state
            cursor.execute("""
                SELECT permanent FROM thought_nodes WHERE id = ?
            """, (node_id,))
            current_state = cursor.fetchone()
            currently_permanent = current_state[0] if current_state and current_state[0] else 0
            
            if should_be_permanent and not currently_permanent:
                # Make permanent (value 1 = auto-permanent)
                cursor.execute("""
                    UPDATE thought_nodes 
                    SET permanent = 1, last_updated = ?
                    WHERE id = ?
                """, (datetime.now(timezone.utc).isoformat(), node_id))
                stats['nodes_made_permanent'] += 1
                logger.debug(f"Node {node_id} made permanent")
            
            elif not should_be_permanent and currently_permanent == 1:  # Only auto-permanent, not manually pinned
                # Remove auto-permanence
                cursor.execute("""
                    UPDATE thought_nodes 
                    SET permanent = 0, last_updated = ?
                    WHERE id = ?
                """, (datetime.now(timezone.utc).isoformat(), node_id))
                stats['nodes_lost_permanence'] += 1
                logger.debug(f"Node {node_id} lost permanence")
        
        # Second pass: Evaluate hotspots with fractal propagation
        cursor.execute("""
            SELECT id FROM thought_nodes 
            WHERE node_type = 'hotspot' 
            AND (decayed IS NULL OR decayed = 0)
            ORDER BY id  -- Process in consistent order for reproducibility
        """)
        
        hotspots = [row[0] for row in cursor.fetchall()]
        
        for hotspot_id in hotspots:
            ratio = calculate_hotspot_permanence_ratio(cursor, hotspot_id)
            
            # Check current state
            cursor.execute("""
                SELECT permanent FROM thought_nodes WHERE id = ?
            """, (hotspot_id,))
            current_state = cursor.fetchone()
            currently_permanent = current_state[0] if current_state and current_state[0] else 0
            
            # Fractal propagation logic
            if ratio >= min_permanent_ratio and not currently_permanent:
                # Hotspot becomes permanent
                cursor.execute("""
                    UPDATE thought_nodes 
                    SET permanent = 1, last_updated = ?
                    WHERE id = ?
                """, (datetime.now(timezone.utc).isoformat(), hotspot_id))
                stats['hotspots_made_permanent'] += 1
                logger.debug(f"Hotspot {hotspot_id} made permanent (ratio: {ratio:.2f})")
            
            elif ratio < min_retain_ratio and currently_permanent == 1:  # Only auto-permanent
                # Hotspot loses permanence
                cursor.execute("""
                    UPDATE thought_nodes 
                    SET permanent = 0, last_updated = ?
                    WHERE id = ?
                """, (datetime.now(timezone.utc).isoformat(), hotspot_id))
                stats['hotspots_lost_permanence'] += 1
                logger.debug(f"Hotspot {hotspot_id} lost permanence (ratio: {ratio:.2f})")
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during permanence evaluation: {e}")
        raise
    finally:
        conn.close()
    
    return stats


def pin_node(db_path: str, node_id: str) -> bool:
    """
    Manually pin a node as permanent.
    
    Args:
        db_path: Path to the database
        node_id: Node ID to pin
        
    Returns:
        True if successful, False if node doesn't exist
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if node exists
        cursor.execute("""
            SELECT id FROM thought_nodes WHERE id = ?
        """, (node_id,))
        
        if not cursor.fetchone():
            return False
        
        # Pin as manually permanent (value 2)
        cursor.execute("""
            UPDATE thought_nodes 
            SET permanent = 2, last_updated = ?
            WHERE id = ?
        """, (datetime.now(timezone.utc).isoformat(), node_id))
        
        conn.commit()
        logger.info(f"Node {node_id} manually pinned as permanent")
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error pinning node {node_id}: {e}")
        raise
    finally:
        conn.close()


def unpin_node(db_path: str, node_id: str) -> bool:
    """
    Remove manual pin from a node. Node may still be auto-permanent.
    
    Args:
        db_path: Path to the database
        node_id: Node ID to unpin
        
    Returns:
        True if successful, False if node doesn't exist
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if node exists
        cursor.execute("""
            SELECT id FROM thought_nodes WHERE id = ?
        """, (node_id,))
        
        if not cursor.fetchone():
            return False
        
        # Remove manual pin, but re-evaluate for auto-permanence
        should_be_auto_permanent = evaluate_node_permanence(cursor, node_id)
        new_value = 1 if should_be_auto_permanent else 0
        
        cursor.execute("""
            UPDATE thought_nodes 
            SET permanent = ?, last_updated = ?
            WHERE id = ?
        """, (new_value, datetime.now(timezone.utc).isoformat(), node_id))
        
        conn.commit()
        logger.info(f"Node {node_id} unpinned (auto-permanent: {should_be_auto_permanent})")
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error unpinning node {node_id}: {e}")
        raise
    finally:
        conn.close()


def get_permanence_stats(db_path: str) -> Dict:
    """
    Get comprehensive permanence statistics for the graph.
    
    Args:
        db_path: Path to the database
        
    Returns:
        Dict with permanence statistics
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Total node counts
        cursor.execute("""
            SELECT COUNT(*) FROM thought_nodes 
            WHERE (decayed IS NULL OR decayed = 0)
        """)
        total_active = cursor.fetchone()[0]
        
        # Permanent node counts
        cursor.execute("""
            SELECT COUNT(*) FROM thought_nodes 
            WHERE (decayed IS NULL OR decayed = 0) AND permanent > 0
        """)
        total_permanent = cursor.fetchone()[0]
        
        # Auto-permanent vs manually pinned
        cursor.execute("""
            SELECT permanent, COUNT(*) 
            FROM thought_nodes 
            WHERE (decayed IS NULL OR decayed = 0) AND permanent > 0
            GROUP BY permanent
        """)
        permanence_breakdown = dict(cursor.fetchall())
        
        # Hotspot permanence
        cursor.execute("""
            SELECT COUNT(*) FROM thought_nodes 
            WHERE node_type = 'hotspot' 
            AND (decayed IS NULL OR decayed = 0) 
            AND permanent > 0
        """)
        permanent_hotspots = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM thought_nodes 
            WHERE node_type = 'hotspot' 
            AND (decayed IS NULL OR decayed = 0)
        """)
        total_hotspots = cursor.fetchone()[0]
        
        # Domain breakdown
        cursor.execute("""
            SELECT COALESCE(domain, 'unknown'), COUNT(*) 
            FROM thought_nodes 
            WHERE (decayed IS NULL OR decayed = 0) AND permanent > 0
            GROUP BY domain
        """)
        permanent_by_domain = dict(cursor.fetchall())
        
        return {
            'total_active_nodes': total_active,
            'total_permanent_nodes': total_permanent,
            'permanent_ratio': round(total_permanent / max(1, total_active), 4),
            'auto_permanent': permanence_breakdown.get(1, 0),
            'manually_pinned': permanence_breakdown.get(2, 0),
            'permanent_hotspots': permanent_hotspots,
            'total_hotspots': total_hotspots,
            'hotspot_permanent_ratio': round(permanent_hotspots / max(1, total_hotspots), 4),
            'permanent_by_domain': permanent_by_domain
        }
        
    finally:
        conn.close()


def is_node_permanent(cursor: sqlite3.Cursor, node_id: str) -> bool:
    """
    Check if a node is currently permanent.
    
    Args:
        cursor: Database cursor
        node_id: Node ID to check
        
    Returns:
        True if the node is permanent
    """
    cursor.execute("""
        SELECT permanent FROM thought_nodes WHERE id = ?
    """, (node_id,))
    
    result = cursor.fetchone()
    return bool(result and result[0])


def get_permanent_nodes(db_path: str, include_manually_pinned: bool = True) -> List[Dict]:
    """
    Get a list of all permanent nodes with their details.
    
    Args:
        db_path: Path to the database
        include_manually_pinned: Whether to include manually pinned nodes
        
    Returns:
        List of dicts with node details
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        query = """
            SELECT id, content, node_type, domain, confidence, 
                   access_count, timestamp, permanent, source_file
            FROM thought_nodes 
            WHERE (decayed IS NULL OR decayed = 0) 
            AND permanent > 0
        """
        
        if not include_manually_pinned:
            query += " AND permanent = 1"
        
        query += " ORDER BY permanent DESC, access_count DESC"
        
        cursor.execute(query)
        
        nodes = []
        for row in cursor.fetchall():
            nodes.append({
                'id': row[0],
                'content': row[1][:100] + ('...' if len(row[1]) > 100 else ''),
                'node_type': row[2],
                'domain': row[3],
                'confidence': row[4],
                'access_count': row[5],
                'timestamp': row[6],
                'permanent_type': 'manually_pinned' if row[7] == 2 else 'auto_permanent',
                'source_file': row[8]
            })
        
        return nodes
        
    finally:
        conn.close()