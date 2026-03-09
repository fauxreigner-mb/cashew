#!/usr/bin/env python3
"""Ablation Test 3: Random graph — same nodes, randomly wired edges, same 12 cycles.
Tests whether the SPECIFIC graph structure matters, or any structure works."""

import sqlite3, json, os, re, random, hashlib
from datetime import datetime

DB_SOURCE = '/Users/bunny/.openclaw/workspace/cashew/data/experiment-clean-v2.db'
DB_RANDOM = '/Users/bunny/.openclaw/workspace/cashew/data/ablation-random-graph.db'
OUTPUT = '/Users/bunny/.openclaw/workspace/cashew/data/ablation-random-graph.json'

import anthropic
client = anthropic.Anthropic()

def call_llm(prompt):
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

def nid(content):
    return hashlib.sha256(content.encode()).hexdigest()[:12]

# Copy non-derived nodes from clean v2
source = sqlite3.connect(DB_SOURCE)
sc = source.cursor()

input_nodes = []
for row in sc.execute("SELECT id, content, node_type, confidence, source_file FROM thought_nodes WHERE node_type != 'derived'"):
    input_nodes.append({"id": row[0], "content": row[1], "type": row[2], "confidence": row[3], "source": row[4]})

source.close()

# Create random graph DB
if os.path.exists(DB_RANDOM):
    os.remove(DB_RANDOM)

conn = sqlite3.connect(DB_RANDOM)
conn.execute("PRAGMA journal_mode=WAL")
c = conn.cursor()

c.executescript("""
CREATE TABLE thought_nodes (
    id TEXT PRIMARY KEY, content TEXT NOT NULL, node_type TEXT NOT NULL,
    timestamp TEXT NOT NULL, confidence REAL NOT NULL, mood_state TEXT,
    metadata TEXT, source_file TEXT, decayed INTEGER DEFAULT 0, last_updated TEXT DEFAULT NULL
);
CREATE TABLE derivation_edges (
    parent_id TEXT NOT NULL, child_id TEXT NOT NULL, relation TEXT NOT NULL,
    weight REAL NOT NULL, reasoning TEXT,
    FOREIGN KEY (parent_id) REFERENCES thought_nodes(id),
    FOREIGN KEY (child_id) REFERENCES thought_nodes(id),
    PRIMARY KEY (parent_id, child_id, relation)
);
""")

# Insert all input nodes
for n in input_nodes:
    c.execute("INSERT INTO thought_nodes (id,content,node_type,timestamp,confidence,source_file) VALUES (?,?,?,?,?,?)",
              (n['id'], n['content'], n['type'], datetime.utcnow().isoformat(), n['confidence'], n['source']))

# Create RANDOM edges — same count as clean v2 (27 seed edges), but random connections
node_ids = [n['id'] for n in input_nodes]
relations = ['supports', 'contradicts', 'questions', 'derived_from']
random.seed(42)  # Reproducible
for _ in range(27):
    a, b = random.sample(node_ids, 2)
    rel = random.choice(relations)
    c.execute("INSERT OR IGNORE INTO derivation_edges VALUES (?,?,?,?,?)",
              (a, b, rel, round(random.uniform(0.5, 0.95), 2), "random connection"))

conn.commit()

# Now run 12 think cycles with the RANDOM graph — same approach as clean v2
# but the node clusters are randomly selected
all_conclusions = []

for cycle_num in range(1, 13):
    # Pick 5-7 random nodes for this cycle's focus
    focus_size = random.randint(5, 7)
    focus_nodes = random.sample(input_nodes, min(focus_size, len(input_nodes)))
    
    # Also include any derived nodes from previous cycles
    prev_derived = [row for row in c.execute("SELECT id, content, confidence FROM thought_nodes WHERE node_type='derived'").fetchall()]
    if prev_derived and cycle_num > 6:
        # Later cycles include some previous derived nodes
        extra = random.sample(prev_derived, min(2, len(prev_derived)))
        for e in extra:
            focus_nodes.append({"id": e[0], "content": e[1], "type": "derived", "confidence": e[2]})
    
    node_list = "\n".join([f"  [{n['id']}] ({n.get('type','derived')}, conf={n.get('confidence',0.8)}): {n['content']}" for n in focus_nodes])
    
    # Check what edges exist between these nodes
    focus_ids = [n['id'] for n in focus_nodes]
    edge_info = ""
    for row in c.execute("SELECT parent_id, child_id, relation FROM derivation_edges"):
        if row[0] in focus_ids and row[1] in focus_ids:
            edge_info += f"  {row[0][:8]} --{row[2]}--> {row[1][:8]}\n"
    
    prompt = f"""You are a reasoning engine. Given these thoughts from a reasoning graph, derive 3-4 NEW conclusions.

NODES:
{node_list}

{"CONNECTIONS:" + chr(10) + edge_info if edge_info else "No connections between these nodes."}

Rules:
- Follow evidence wherever it leads — do not assume a conclusion
- Engage the STRONGEST version of all arguments
- Each derived thought MUST reference specific parent nodes by ID
- Use relation types: derived_from, supports, contradicts, questions

Return ONLY a JSON array:
[{{"content": "conclusion", "confidence": 0.5-0.95, "edges": [{{"parent_id": "abc123", "relation": "derived_from|supports|contradicts|questions", "weight": 0.7, "reasoning": "why"}}]}}]"""

    print(f"\n{'='*60}")
    print(f"CYCLE {cycle_num}: {len(focus_nodes)} random nodes")
    
    try:
        response = call_llm(prompt)
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            raw = json_match.group()
            # Fix common JSON issues
            raw = re.sub(r',\s*]', ']', raw)  # trailing commas
            raw = re.sub(r',\s*}', '}', raw)  # trailing commas in objects
            thoughts = json.loads(raw)
            for t in thoughts:
                tid = nid(t['content'])
                c.execute("INSERT OR IGNORE INTO thought_nodes (id,content,node_type,timestamp,confidence,source_file) VALUES (?,?,?,?,?,?)",
                          (tid, t['content'], 'derived', datetime.utcnow().isoformat(), t['confidence'], 'system_generated'))
                for edge in t.get('edges', []):
                    pid = edge['parent_id']
                    exists = c.execute("SELECT 1 FROM thought_nodes WHERE id=?", (pid,)).fetchone()
                    if exists:
                        c.execute("INSERT OR IGNORE INTO derivation_edges VALUES (?,?,?,?,?)",
                                  (pid, tid, edge['relation'], edge['weight'], edge.get('reasoning', '')))
                t['cycle'] = cycle_num
                all_conclusions.append(t)
                print(f"  (conf={t['confidence']}) {t['content'][:120]}...")
            conn.commit()
        else:
            print(f"  ERROR: No JSON in response")
    except Exception as e:
        print(f"  ERROR: {e}")

total_nodes = c.execute("SELECT COUNT(*) FROM thought_nodes").fetchone()[0]
total_edges = c.execute("SELECT COUNT(*) FROM derivation_edges").fetchone()[0]

print(f"\n{'='*60}")
print(f"TOTAL: {len(all_conclusions)} conclusions, {total_nodes} nodes, {total_edges} edges")

with open(OUTPUT, 'w') as f:
    json.dump({
        "method": "random_graph_12_cycles",
        "total_conclusions": len(all_conclusions),
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "conclusions": all_conclusions
    }, f, indent=2)

print(f"Saved to {OUTPUT}")
conn.close()
