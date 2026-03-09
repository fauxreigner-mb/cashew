#!/usr/bin/env python3

import sqlite3
import random
import uuid
import json
import subprocess
import tempfile
from datetime import datetime

DB_PATH = '/Users/bunny/.openclaw/workspace/cashew/data/experiment-clean-v2.db'

def get_all_nodes():
    """Retrieve all nodes from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, content, node_type FROM thought_nodes')
    nodes = cursor.fetchall()
    conn.close()
    return [(node_id, content, node_type) for node_id, content, node_type in nodes]

def select_nodes_for_cycle(all_nodes, cycle_num):
    """Select 3-5 related nodes for a think cycle."""
    # For balanced exploration, mix node types
    if cycle_num <= 3:
        # Early cycles: focus on core seed + evidence
        seeds = [n for n in all_nodes if n[2] == 'seed']
        env_nodes = [n for n in all_nodes if n[2] == 'environment']
        selected = random.sample(seeds, min(2, len(seeds))) + random.sample(env_nodes, min(3, len(env_nodes)))
    elif cycle_num <= 6:
        # Mid cycles: mix everything
        selected = random.sample(all_nodes, min(4, len(all_nodes)))
    else:
        # Later cycles: include derived thoughts
        derived = [n for n in all_nodes if n[2] == 'derived']
        others = [n for n in all_nodes if n[2] != 'derived']
        if len(derived) >= 2:
            selected = random.sample(derived, 2) + random.sample(others, min(3, len(others)))
        else:
            selected = random.sample(all_nodes, min(5, len(all_nodes)))
    
    return selected

def query_llm(prompt):
    """Query the LLM with neutral instructions."""
    system_prompt = """You are a reasoning engine. Given these thoughts, derive new conclusions. Follow the evidence wherever it leads. Engage with the strongest versions of all arguments. Do not assume a conclusion.

Your task is to generate 3-4 new thoughts based on the input thoughts. Each new thought should be:
- A logical derivation, question, support, or contradiction
- Substantive and insightful 
- Not merely restating the inputs
- Following evidence and reason, not bias

Return ONLY a JSON array of objects with this format:
[
  {
    "content": "The derived thought content",
    "relation": "derived_from|supports|contradicts|questions",
    "target_content": "Content of the input thought this relates to",
    "reasoning": "Brief explanation of the logical connection"
  }
]"""

    # Create a temporary file for the prompt
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(prompt)
        prompt_file = f.name
    
    try:
        # Use exec to call the LLM 
        result = subprocess.run([
            'claude', 'chat', 
            '--system', system_prompt,
            '--file', prompt_file,
            '--json'
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                print(f"LLM returned non-JSON: {result.stdout}")
                return []
        else:
            print(f"LLM error: {result.stderr}")
            return []
    except Exception as e:
        print(f"Error querying LLM: {e}")
        return []
    finally:
        import os
        os.unlink(prompt_file)

def insert_derived_thoughts(derived_thoughts, source_nodes):
    """Insert derived thoughts and their relationships into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    
    # Create mapping from content to node_id for source nodes
    content_to_id = {content: node_id for node_id, content, _ in source_nodes}
    
    for thought in derived_thoughts:
        # Generate new node ID
        new_node_id = str(uuid.uuid4()).replace('-', '')[:12]
        
        # Insert the new thought node
        cursor.execute('''
        INSERT INTO thought_nodes (id, content, node_type, timestamp, confidence, source_file)
        VALUES (?, ?, 'derived', ?, 0.6, 'system_generated')
        ''', (new_node_id, thought['content'], timestamp))
        
        # Find the target node ID
        target_id = None
        for source_id, source_content, _ in source_nodes:
            if thought['target_content'].strip() in source_content or source_content.strip() in thought['target_content']:
                target_id = source_id
                break
        
        if target_id:
            # Insert the edge relationship
            relation = thought['relation']
            weight = 0.7
            reasoning = thought.get('reasoning', '')
            
            if relation in ['derived_from', 'supports', 'contradicts', 'questions']:
                cursor.execute('''
                INSERT OR IGNORE INTO derivation_edges (parent_id, child_id, relation, weight, reasoning)
                VALUES (?, ?, ?, ?, ?)
                ''', (target_id, new_node_id, relation, weight, reasoning))
            else:
                print(f"Unknown relation type: {relation}")
    
    conn.commit()
    conn.close()

def run_think_cycle(cycle_num):
    """Run a single think cycle."""
    print(f"\n=== Think Cycle {cycle_num} ===")
    
    # Get all current nodes
    all_nodes = get_all_nodes()
    print(f"Total nodes: {len(all_nodes)}")
    
    # Select nodes for this cycle
    selected_nodes = select_nodes_for_cycle(all_nodes, cycle_num)
    print(f"Selected {len(selected_nodes)} nodes:")
    for i, (node_id, content, node_type) in enumerate(selected_nodes, 1):
        print(f"  {i}. [{node_type}] {content[:100]}...")
    
    # Create prompt from selected nodes
    prompt = "Input thoughts to reason about:\n\n"
    for i, (node_id, content, node_type) in enumerate(selected_nodes, 1):
        prompt += f"{i}. {content}\n\n"
    
    # Query LLM for derived thoughts
    print("Querying LLM...")
    derived_thoughts = query_llm(prompt)
    
    if derived_thoughts:
        print(f"Generated {len(derived_thoughts)} derived thoughts:")
        for i, thought in enumerate(derived_thoughts, 1):
            print(f"  {i}. [{thought['relation']}] {thought['content'][:80]}...")
        
        # Insert into database
        insert_derived_thoughts(derived_thoughts, selected_nodes)
        print("Inserted derived thoughts into database.")
    else:
        print("No derived thoughts generated.")
    
    return len(derived_thoughts)

def main():
    """Run 10-12 think cycles."""
    total_derived = 0
    num_cycles = 12
    
    print("Starting balanced think cycle experiment (Clean Room v2)")
    print(f"Running {num_cycles} cycles...")
    
    for cycle in range(1, num_cycles + 1):
        try:
            derived_count = run_think_cycle(cycle)
            total_derived += derived_count
            
            # Brief pause between cycles
            import time
            time.sleep(2)
            
        except Exception as e:
            print(f"Error in cycle {cycle}: {e}")
            continue
    
    print(f"\n=== Experiment Complete ===")
    print(f"Total derived thoughts generated: {total_derived}")
    
    # Final node count
    all_nodes = get_all_nodes()
    by_type = {}
    for _, _, node_type in all_nodes:
        by_type[node_type] = by_type.get(node_type, 0) + 1
    
    print("Final node counts by type:")
    for node_type, count in by_type.items():
        print(f"  {node_type}: {count}")

if __name__ == "__main__":
    main()