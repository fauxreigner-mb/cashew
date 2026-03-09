#!/usr/bin/env python3
"""
cashew brain migration script - Phase 1
Migrates graph.db to brain.db with new untyped edge architecture
"""

import sqlite3
import json
import re
import time
import subprocess
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
            'placeholder',  # Will be updated by LLM
            None,          # Will be updated by LLM
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

def call_claude_via_openclaw(prompt):
    """Use OpenClaw CLI to call Claude"""
    try:
        # Write prompt to temporary file
        prompt_file = "/tmp/migration_prompt.txt"
        with open(prompt_file, 'w') as f:
            f.write(prompt)
        
        # Call OpenClaw CLI
        result = subprocess.run([
            'openclaw', 'agent', 'call',
            '--model', 'anthropic/claude-sonnet-4-20250514',
            '--prompt-file', prompt_file,
            '--max-tokens', '4000'
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"OpenClaw CLI error: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error calling OpenClaw: {e}")
        return None

def batch_classify_nodes(nodes, batch_size=10):
    """Use Claude to classify nodes into new schema"""
    results = []
    total_batches = (len(nodes) + batch_size - 1) // batch_size
    
    for i in range(0, len(nodes), batch_size):
        batch = nodes[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} nodes)")
        
        # Prepare batch for LLM
        batch_data = []
        for node in batch:
            batch_data.append({
                'id': node[0],
                'content': node[1]
            })
        
        # LLM prompt
        prompt = f"""Classify these thought nodes for a brain knowledge graph.

For each node, assign:
1. node_type: observation, belief, decision, insight, or fact
2. domain: work, personal, fitness, engineering, philosophy, music, relationships, or meta

Guidelines:
- observation: External facts, events, data points
- belief: Values, opinions, worldview statements  
- decision: Choices made, commitments, resolutions
- insight: Realizations, patterns, understanding
- fact: Objective truths, established knowledge

- work: Job, career, professional development
- personal: Self-reflection, identity, emotions
- fitness: Health, exercise, physical well-being
- engineering: Technical skills, systems thinking
- philosophy: Belief systems, meaning, ethics
- music: Musical interests, "Electrons in a Box"
- relationships: Family, friends, romantic partners
- meta: About the knowledge system itself

Nodes to classify:
{json.dumps(batch_data, indent=2)}

Respond with ONLY a valid JSON array:
[
  {{"id": "node_id", "node_type": "belief", "domain": "philosophy"}},
  ...
]"""

        # Call Claude
        try:
            response_text = call_claude_via_openclaw(prompt)
            
            if response_text:
                # Parse JSON with fallback regex
                try:
                    classifications = json.loads(response_text)
                except json.JSONDecodeError:
                    # Regex fallback for malformed JSON
                    json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                    if json_match:
                        classifications = json.loads(json_match.group())
                    else:
                        print(f"Failed to parse response for batch {batch_num}, using defaults")
                        classifications = [{"id": node[0], "node_type": "insight", "domain": "meta"} for node in batch]
                
                # Validate and store results
                for item in classifications:
                    if item.get('node_type') not in VALID_NODE_TYPES:
                        item['node_type'] = 'insight'
                    if item.get('domain') not in VALID_DOMAINS:
                        item['domain'] = 'meta'
                
                results.extend(classifications)
            else:
                # Use defaults for failed batch
                for node in batch:
                    results.append({"id": node[0], "node_type": "insight", "domain": "meta"})
            
            # Rate limiting
            time.sleep(2)
            
        except Exception as e:
            print(f"Error processing batch {batch_num}: {e}")
            # Use default classifications for this batch
            for node in batch:
                results.append({"id": node[0], "node_type": "insight", "domain": "meta"})
    
    return results

def update_node_classifications(conn, classifications):
    """Update nodes with LLM classifications"""
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
    print("🧠 cashew brain migration - Phase 1")
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
    target_conn.commit()
    
    print("🤖 Initializing Claude for node classification...")
    
    # Get nodes for classification
    nodes = target_conn.execute('SELECT id, content FROM thought_nodes').fetchall()
    print(f"📝 Classifying {len(nodes)} nodes...")
    
    # Classify nodes with LLM
    classifications = batch_classify_nodes(nodes)
    
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
    source_conn.close()
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