#!/usr/bin/env python3
"""
Ablation test for cashew: Untyped edges experiment

This tests an architecture where edges have NO semantic labels (no supports/contradicts/etc).
All edges are just 'related' connections. The LLM discovers relationships from node content.
"""

import sqlite3
import json
import re
import random
from datetime import datetime, timezone
from collections import deque
import anthropic
import time

# API setup
API_KEY = "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"
client = anthropic.Anthropic(api_key=API_KEY)

# Database paths
SOURCE_DB = "/Users/bunny/.openclaw/workspace/cashew/data/experiment-clean-v2.db"
TARGET_DB = "/Users/bunny/.openclaw/workspace/cashew/data/ablation-untyped-edges.db"
RESULTS_PATH = "/Users/bunny/.openclaw/workspace/cashew/data/ablation-untyped-edges.json"

# Focus areas for each cycle
FOCUS_AREAS = [
    "prayer and spiritual practices",
    "morality and ethics", 
    "existence arguments and cosmology",
    "sacred texts and scripture",
    "consciousness and near-death experiences",
    "epistemology and ways of knowing",
    "historical claims and evidence",
    "community value and social benefits",
    "synthesis across previous conclusions",
    "final assessment",
    "steelman strongest theistic arguments", 
    "most intellectually honest position"
]

def create_database():
    """Create new database with same schema, copy input nodes and edges (all as 'related')"""
    print("Creating new database...")
    
    # Remove existing file if present
    import os
    if os.path.exists(TARGET_DB):
        os.remove(TARGET_DB)
    
    # Create new database with same schema
    target_conn = sqlite3.connect(TARGET_DB)
    target_conn.execute('''
        CREATE TABLE thought_nodes (
            id TEXT PRIMARY KEY, content TEXT NOT NULL, node_type TEXT NOT NULL,
            timestamp TEXT NOT NULL, confidence REAL NOT NULL, mood_state TEXT,
            metadata TEXT, source_file TEXT, decayed INTEGER DEFAULT 0, last_updated TEXT DEFAULT NULL
        )
    ''')
    target_conn.execute('''
        CREATE TABLE derivation_edges (
            parent_id TEXT NOT NULL, child_id TEXT NOT NULL, relation TEXT NOT NULL,
            weight REAL NOT NULL, reasoning TEXT,
            FOREIGN KEY (parent_id) REFERENCES thought_nodes(id),
            FOREIGN KEY (child_id) REFERENCES thought_nodes(id),
            PRIMARY KEY (parent_id, child_id, relation)
        )
    ''')
    
    # Copy input nodes from source
    source_conn = sqlite3.connect(SOURCE_DB)
    input_nodes = source_conn.execute('''
        SELECT id, content, node_type, timestamp, confidence, mood_state, 
               metadata, source_file, decayed, last_updated 
        FROM thought_nodes WHERE node_type IN ('seed','belief','environment')
    ''').fetchall()
    
    print(f"Copying {len(input_nodes)} input nodes...")
    for node in input_nodes:
        target_conn.execute('''
            INSERT INTO thought_nodes 
            (id, content, node_type, timestamp, confidence, mood_state, metadata, source_file, decayed, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', node)
    
    # Copy edges but set all relations to 'related'
    edges = source_conn.execute('SELECT parent_id, child_id, weight, reasoning FROM derivation_edges').fetchall()
    print(f"Copying {len(edges)} edges (all as 'related')...")
    for parent_id, child_id, weight, reasoning in edges:
        target_conn.execute('''
            INSERT INTO derivation_edges (parent_id, child_id, relation, weight, reasoning)
            VALUES (?, ?, 'related', ?, ?)
        ''', (parent_id, child_id, weight, reasoning))
    
    target_conn.commit()
    target_conn.close()
    source_conn.close()
    print("Database created successfully!")

def get_connected_cluster(conn, start_node_id, cluster_size=4):
    """Get a cluster of connected nodes using BFS from start node"""
    visited = set()
    queue = deque([start_node_id])
    cluster = []
    
    while queue and len(cluster) < cluster_size:
        current = queue.popleft()
        if current in visited:
            continue
            
        visited.add(current)
        
        # Get node info
        node = conn.execute('SELECT id, content FROM thought_nodes WHERE id = ?', (current,)).fetchone()
        if node:
            cluster.append(node)
        
        # Add neighbors to queue
        neighbors = conn.execute('''
            SELECT DISTINCT child_id FROM derivation_edges WHERE parent_id = ?
            UNION
            SELECT DISTINCT parent_id FROM derivation_edges WHERE child_id = ?
        ''', (current, current)).fetchall()
        
        for (neighbor_id,) in neighbors:
            if neighbor_id not in visited:
                queue.append(neighbor_id)
    
    return cluster

def extract_conclusions_from_response(response_text):
    """Extract conclusions from LLM response with robust parsing"""
    conclusions = []
    raw_response = response_text
    
    try:
        # Try to find JSON in response
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            parsed = json.loads(json_str)
            
            for item in parsed:
                if isinstance(item, dict) and 'content' in item:
                    conclusion = {
                        'content': item['content'],
                        'confidence': item.get('confidence', 0.7),
                        'relationships_discovered': item.get('relationships_discovered', [])
                    }
                    conclusions.append(conclusion)
            
            if conclusions:
                return conclusions, raw_response
    
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"JSON parsing failed: {e}")
    
    # Fallback: extract from text using regex
    print("Using fallback text extraction...")
    
    # Look for numbered conclusions or bullet points
    conclusion_patterns = [
        r'(\d+\.|•|-)\s*(.+?)(?=\n\d+\.|•|-|\n\n|$)',
        r'conclusion:?\s*(.+?)(?=\n|$)',
        r'therefore:?\s*(.+?)(?=\n|$)'
    ]
    
    for pattern in conclusion_patterns:
        matches = re.findall(pattern, response_text, re.IGNORECASE | re.MULTILINE)
        if matches:
            for match in matches:
                content = match[1] if isinstance(match, tuple) else match
                content = content.strip()
                if len(content) > 10:  # Filter out very short matches
                    conclusions.append({
                        'content': content,
                        'confidence': 0.6,  # Lower confidence for extracted text
                        'relationships_discovered': []
                    })
            break
    
    # If still no conclusions, create one from the whole response
    if not conclusions and len(response_text.strip()) > 20:
        conclusions.append({
            'content': response_text.strip()[:500] + "..." if len(response_text) > 500 else response_text.strip(),
            'confidence': 0.5,
            'relationships_discovered': []
        })
    
    return conclusions, raw_response

def run_think_cycle(conn, cycle_num, focus_area):
    """Run a single think cycle"""
    print(f"\n--- Cycle {cycle_num}: {focus_area} ---")
    
    # Get all input nodes to start from
    input_nodes = conn.execute('SELECT id FROM thought_nodes WHERE node_type IN ("seed","belief","environment")').fetchall()
    
    if not input_nodes:
        print("No input nodes found!")
        return []
    
    # Pick random starting node
    start_node = random.choice(input_nodes)[0]
    
    # Get connected cluster
    cluster = get_connected_cluster(conn, start_node, cluster_size=random.randint(3, 5))
    
    if len(cluster) < 2:
        print(f"Cluster too small ({len(cluster)} nodes), skipping...")
        return []
    
    print(f"Selected cluster of {len(cluster)} nodes starting from {start_node[:8]}...")
    
    # Build prompt
    node_list = "\n".join([f"{i+1}. {node[1]}" for i, node in enumerate(cluster)])
    
    prompt = f"""Here are several related thoughts:
{node_list}

These thoughts are connected but I haven't told you HOW they relate.

First, identify the relationships between these thoughts (do they support each other? contradict? raise questions about each other?).

Then, focusing on the theme of "{focus_area}", derive 2-4 new conclusions that follow from analyzing these thoughts together.

Return JSON array: [{{"content": "...", "confidence": 0.X, "relationships_discovered": ["A supports B because...", "B contradicts C because..."]}}]"""
    
    # Call Claude
    print("Calling Claude Sonnet...")
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",  # Using Claude Sonnet as required
            max_tokens=2000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.content[0].text
        
    except Exception as e:
        print(f"API call failed: {e}")
        return []
    
    # Parse response
    conclusions, raw_response = extract_conclusions_from_response(response_text)
    
    print(f"Extracted {len(conclusions)} conclusions")
    
    # Save conclusions to database
    timestamp = datetime.now(timezone.utc).isoformat()
    saved_conclusions = []
    
    for conclusion in conclusions:
        # Generate node ID
        node_id = f"cycle{cycle_num:02d}_{random.randint(1000, 9999)}"
        
        # Insert node
        conn.execute('''
            INSERT INTO thought_nodes 
            (id, content, node_type, timestamp, confidence, source_file)
            VALUES (?, ?, 'derived', ?, ?, 'system_generated')
        ''', (node_id, conclusion['content'], timestamp, conclusion['confidence']))
        
        # Add edges from cluster nodes to this conclusion (all as 'related')
        for cluster_node_id, _ in cluster:
            conn.execute('''
                INSERT OR IGNORE INTO derivation_edges 
                (parent_id, child_id, relation, weight, reasoning)
                VALUES (?, ?, 'related', 0.8, ?)
            ''', (cluster_node_id, node_id, f"Derived in cycle {cycle_num} focusing on {focus_area}"))
        
        # Store conclusion with metadata
        saved_conclusion = conclusion.copy()
        saved_conclusion['cycle'] = cycle_num
        saved_conclusion['node_id'] = node_id
        saved_conclusion['raw_response'] = raw_response
        saved_conclusions.append(saved_conclusion)
    
    conn.commit()
    return saved_conclusions

def main():
    """Main execution function"""
    print("Starting Ablation Test: Untyped Edges")
    print("=====================================")
    
    # Create database
    create_database()
    
    # Connect to target database
    conn = sqlite3.connect(TARGET_DB)
    
    # Run 12 think cycles
    all_conclusions = []
    
    for cycle in range(1, 13):
        focus_area = FOCUS_AREAS[cycle-1]
        cycle_conclusions = run_think_cycle(conn, cycle, focus_area)
        all_conclusions.extend(cycle_conclusions)
        
        # Brief pause to avoid rate limiting
        time.sleep(1)
    
    # Get final stats
    total_nodes = conn.execute('SELECT COUNT(*) FROM thought_nodes').fetchone()[0]
    total_edges = conn.execute('SELECT COUNT(*) FROM derivation_edges').fetchone()[0]
    
    conn.close()
    
    # Save results
    results = {
        "method": "untyped_edges",
        "total_conclusions": len(all_conclusions),
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "conclusions": [
            {
                "content": c["content"],
                "confidence": c["confidence"], 
                "cycle": c["cycle"],
                "relationships_discovered": c.get("relationships_discovered", [])
            } 
            for c in all_conclusions
        ],
        "raw_data": all_conclusions,  # Include full data with raw responses
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "focus_areas": FOCUS_AREAS
    }
    
    with open(RESULTS_PATH, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n🎉 Experiment Complete!")
    print(f"Total conclusions: {len(all_conclusions)}")
    print(f"Total nodes: {total_nodes}")
    print(f"Total edges: {total_edges}")
    print(f"Results saved to: {RESULTS_PATH}")
    print(f"Database saved to: {TARGET_DB}")

if __name__ == "__main__":
    main()