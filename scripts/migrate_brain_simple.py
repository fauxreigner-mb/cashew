#!/usr/bin/env python3
"""
cashew brain migration script - Phase 1 (Simple version)
Migrates graph.db to brain.db with rule-based classification
"""

import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
SOURCE_DB = BASE_DIR / "data" / "graph.db"
TARGET_DB = BASE_DIR / "data" / "brain.db"

# Valid classifications
VALID_NODE_TYPES = {'observation', 'belief', 'decision', 'insight', 'fact'}
VALID_DOMAINS = {'work', 'personal', 'fitness', 'engineering', 'philosophy', 'music', 'relationships', 'meta'}

def create_target_schema(conn):
    """Create the new brain.db schema"""
    conn.execute('''
        CREATE TABLE thought_nodes (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            node_type TEXT NOT NULL,       -- 'observation', 'belief', 'decision', 'insight', 'fact'
            domain TEXT,                   -- 'work', 'personal', 'fitness', 'engineering', 'philosophy', 'music', 'relationships', 'meta'
            confidence REAL DEFAULT 0.5,
            created_at TEXT,
            last_accessed TEXT,
            access_count INTEGER DEFAULT 0,
            source TEXT,                   -- 'conversation', 'think_cycle', 'migration', 'heartbeat'
            session_id TEXT,
            decayed INTEGER DEFAULT 0
        )
    ''')
    
    conn.execute('''
        CREATE TABLE edges (
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            created_at TEXT,
            UNIQUE(source_id, target_id)
        )
    ''')

def copy_base_data(source_conn, target_conn):
    """Copy and transform data from source to target"""
    # Get all nodes
    source_conn.row_factory = sqlite3.Row
    nodes = source_conn.execute('SELECT * FROM thought_nodes').fetchall()
    
    # Copy nodes with schema transformation
    for node in nodes:
        target_conn.execute('''
            INSERT INTO thought_nodes 
            (id, content, node_type, domain, confidence, created_at, last_accessed, 
             access_count, source, session_id, decayed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            node['id'],
            node['content'],
            'placeholder',  # Will be updated by classification
            None,          # Will be updated by classification
            node['confidence'],
            node['timestamp'],  # Use original timestamp as created_at
            node['timestamp'],  # Set last_accessed = created_at initially
            0,             # access_count = 0
            'migration',   # source = 'migration'
            None,          # session_id = NULL
            node['decayed']
        ))
    
    # Get all edges and strip relation types
    edges = source_conn.execute('SELECT parent_id, child_id, weight FROM derivation_edges').fetchall()
    
    # Copy edges without relation column, handling duplicates
    edge_pairs = set()
    for edge in edges:
        pair = (edge['parent_id'], edge['child_id'])
        if pair not in edge_pairs:
            edge_pairs.add(pair)
            # Use the first timestamp we can find for created_at
            first_node = source_conn.execute('SELECT timestamp FROM thought_nodes WHERE id = ?', (edge['parent_id'],)).fetchone()
            created_at = first_node['timestamp'] if first_node else datetime.now().isoformat()
            
            target_conn.execute('''
                INSERT INTO edges (source_id, target_id, weight, created_at)
                VALUES (?, ?, ?, ?)
            ''', (
                edge['parent_id'],  # parent_id becomes source_id
                edge['child_id'],   # child_id becomes target_id
                edge['weight'],
                created_at
            ))

def rule_based_classify(content, original_type, source_file):
    """Simple rule-based classification"""
    content_lower = content.lower()
    
    # Domain classification
    domain = 'meta'  # default
    
    if any(word in content_lower for word in ['work', 'manager', 'promotion', 'e5', 'team', 'code', 'engineering']):
        domain = 'work'
    elif any(word in content_lower for word in ['partner', 'family', 'mom', 'dad', 'relationship', 'marriage']):
        domain = 'relationships'
    elif any(word in content_lower for word in ['god', 'prayer', 'christianity', 'bible', 'belief', 'atheist', 'religion']):
        domain = 'philosophy'
    elif any(word in content_lower for word in ['systems', 'technical', 'dagger', 'architecture', 'infrastructure']):
        domain = 'engineering'
    elif any(word in content_lower for word in ['electrons', 'music', 'nag', 'friend-s']):
        domain = 'music'
    elif any(word in content_lower for word in ['happy', 'happiness', 'self', 'personal', 'identity', 'feel']):
        domain = 'personal'
    elif any(word in content_lower for word in ['gym', 'fitness', 'weight', 'health']):
        domain = 'fitness'
    
    # Node type classification
    node_type = 'insight'  # default
    
    # Map original types roughly to new types
    if original_type in ['belief', 'core_memory']:
        node_type = 'belief'
    elif original_type in ['seed', 'prediction']:
        node_type = 'fact'
    elif original_type in ['derived', 'implication']:
        node_type = 'insight'
    elif original_type in ['question', 'tension']:
        node_type = 'observation'
    
    # Content-based overrides
    if any(phrase in content_lower for phrase in ['i decided', 'i will', 'i choose', 'i committed']):
        node_type = 'decision'
    elif any(phrase in content_lower for phrase in ['i believe', 'i think', 'my opinion', 'i feel that']):
        node_type = 'belief'
    elif any(phrase in content_lower for phrase in ['i noticed', 'i observed', 'i saw', 'data shows']):
        node_type = 'observation'
    elif content.endswith('?'):
        node_type = 'observation'
    
    return node_type, domain

def classify_all_nodes(conn):
    """Classify all nodes using rule-based approach"""
    # Get nodes with original metadata
    nodes = conn.execute('SELECT id, content FROM thought_nodes').fetchall()
    source_conn = sqlite3.connect(SOURCE_DB)
    source_conn.row_factory = sqlite3.Row
    
    classifications = []
    
    print(f"📝 Classifying {len(nodes)} nodes using rule-based approach...")
    
    for node_id, content in nodes:
        # Get original metadata
        original = source_conn.execute('SELECT node_type, source_file FROM thought_nodes WHERE id = ?', (node_id,)).fetchone()
        
        if original:
            node_type, domain = rule_based_classify(content, original['node_type'], original['source_file'])
        else:
            node_type, domain = 'insight', 'meta'
        
        classifications.append({
            'id': node_id,
            'node_type': node_type,
            'domain': domain
        })
    
    source_conn.close()
    return classifications

def update_node_classifications(conn, classifications):
    """Update nodes with classifications"""
    for item in classifications:
        conn.execute('''
            UPDATE thought_nodes 
            SET node_type = ?, domain = ?
            WHERE id = ?
        ''', (item['node_type'], item['domain'], item['id']))

def generate_migration_report(conn):
    """Generate migration summary report"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'node_count': conn.execute('SELECT COUNT(*) FROM thought_nodes').fetchone()[0],
        'edge_count': conn.execute('SELECT COUNT(*) FROM edges').fetchone()[0],
        'node_type_distribution': {},
        'domain_distribution': {}
    }
    
    # Node type distribution
    types = conn.execute('SELECT node_type, COUNT(*) FROM thought_nodes GROUP BY node_type').fetchall()
    for node_type, count in types:
        report['node_type_distribution'][node_type] = count
    
    # Domain distribution
    domains = conn.execute('SELECT domain, COUNT(*) FROM thought_nodes GROUP BY domain').fetchall()
    for domain, count in domains:
        report['domain_distribution'][domain] = count
    
    return report

def main():
    """Main migration process"""
    print("🧠 cashew brain migration - Phase 1 (Rule-based)")
    print(f"Source: {SOURCE_DB}")
    print(f"Target: {TARGET_DB}")
    
    # Verify source exists
    if not SOURCE_DB.exists():
        print(f"❌ Source database not found: {SOURCE_DB}")
        return False
    
    # Remove target if it exists (fresh migration)
    if TARGET_DB.exists():
        TARGET_DB.unlink()
        print(f"🗑️  Removed existing {TARGET_DB}")
    
    # Create target database
    print("📋 Creating target schema...")
    target_conn = sqlite3.connect(TARGET_DB)
    create_target_schema(target_conn)
    
    # Copy base data
    print("📊 Copying base data...")
    source_conn = sqlite3.connect(SOURCE_DB)
    copy_base_data(source_conn, target_conn)
    source_conn.close()
    target_conn.commit()
    
    # Classify nodes with rules
    classifications = classify_all_nodes(target_conn)
    
    # Update database with classifications
    print("💾 Updating node classifications...")
    update_node_classifications(target_conn, classifications)
    target_conn.commit()
    
    # Generate migration report
    print("📈 Generating migration report...")
    report = generate_migration_report(target_conn)
    
    # Save report
    report_path = BASE_DIR / "migration_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Cleanup
    target_conn.close()
    
    print("\n✅ Migration completed successfully!")
    print(f"📊 Nodes: {report['node_count']}")
    print(f"🔗 Edges: {report['edge_count']}")
    print(f"📝 Node types: {report['node_type_distribution']}")
    print(f"🏷️  Domains: {report['domain_distribution']}")
    print(f"📋 Full report: {report_path}")
    
    return True

if __name__ == "__main__":
    main()