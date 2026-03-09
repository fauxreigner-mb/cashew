#!/usr/bin/env python3
"""
Ablation Test: Edge Label Swap Control
Tests whether edge SEMANTICS matter or just edge EXISTENCE.

Takes the clean room v2 graph and swaps edge labels:
- supports ↔ contradicts  
- questions ↔ derived_from

Then runs 12 think cycles using the same approach as run_clean_v2.py
to test if edge semantics or just edge existence drives reasoning.
"""
import sqlite3, hashlib, json, os, subprocess, re
from datetime import datetime

# Use the already-created swapped database
DB = '/Users/bunny/.openclaw/workspace/cashew/data/ablation-swapped-labels.db'
JSON_OUT = '/Users/bunny/.openclaw/workspace/cashew/data/ablation-swapped-labels.json'

def nid(content):
    return hashlib.sha256(content.encode()).hexdigest()[:12]

def ts():
    return datetime.utcnow().isoformat()

# Connect to the swapped database
conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
c = conn.cursor()

# === LLM-DRIVEN THINK CYCLES ===
def call_llm(prompt):
    """Call Claude via the Anthropic API."""
    import anthropic
    
    # Try to get API key from environment first, then keychain
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        try:
            result = subprocess.run(['security', 'find-generic-password', '-s', 'anthropic-api-key', '-w'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                api_key = result.stdout.strip()
        except:
            pass
    
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment or keychain")
    
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

def get_nodes_by_ids(ids):
    """Get node content by IDs."""
    nodes = []
    for nid_val in ids:
        row = c.execute("SELECT id, content, node_type, confidence FROM thought_nodes WHERE id=?", (nid_val,)).fetchone()
        if row:
            nodes.append({"id": row[0], "content": row[1], "type": row[2], "confidence": row[3]})
    return nodes

def insert_node(content, node_type, confidence, source_file):
    i = nid(content)
    c.execute("INSERT OR IGNORE INTO thought_nodes (id,content,node_type,timestamp,confidence,source_file) VALUES (?,?,?,?,?,?)",
              (i, content, node_type, ts(), confidence, source_file))
    return i

def insert_edge(pid, cid, relation, weight, reasoning=""):
    c.execute("INSERT OR IGNORE INTO derivation_edges VALUES (?,?,?,?,?)",
              (pid, cid, relation, weight, reasoning))

def run_think_cycle(cycle_num, focus_ids, focus_desc):
    """Run one think cycle: feed focus nodes to LLM, get derived thoughts with edges."""
    focus_nodes = get_nodes_by_ids(focus_ids)
    if not focus_nodes:
        print(f"  Skipping cycle {cycle_num}: no valid focus nodes")
        return

    # Build context
    node_list = "\n".join([f"  [{n['id']}] ({n['type']}, conf={n['confidence']}): {n['content']}" for n in focus_nodes])

    prompt = f"""You are a reasoning engine. You have NO preconceptions. Given these thoughts from a reasoning graph, derive 3-4 NEW conclusions.

FOCUS AREA: {focus_desc}

NODES:
{node_list}

RULES:
- Follow evidence wherever it leads — do not assume a conclusion
- Engage the STRONGEST version of all arguments (steelman, don't strawman)
- Each derived thought MUST reference specific parent nodes by ID
- Use relation types: derived_from, supports, contradicts, questions
- Be genuinely balanced — acknowledge strength in arguments you ultimately disagree with

Return ONLY valid JSON array. Each element:
{{
  "content": "the derived thought (1-2 sentences)",
  "confidence": 0.5-0.95,
  "edges": [
    {{"parent_id": "abc123", "relation": "derived_from|supports|contradicts|questions", "weight": 0.5-0.95, "reasoning": "why this connection"}}
  ]
}}

Return ONLY the JSON array, no other text."""

    print(f"\n{'='*60}")
    print(f"THINK CYCLE {cycle_num}: {focus_desc}")
    print(f"  Focus: {len(focus_nodes)} nodes")

    try:
        response = call_llm(prompt)
        # Extract JSON from response
        # Try to find JSON array in response
        json_match = re.search(r'\[[\s\S]*\]', response)
        if not json_match:
            print(f"  ERROR: No JSON array found in response")
            print(f"  Response: {response[:200]}")
            return
        
        thoughts = json.loads(json_match.group())
        
        for thought in thoughts:
            tid = insert_node(thought["content"], 'derived', thought["confidence"], 'system_generated')
            print(f"\n  [{tid}] (conf={thought['confidence']})")
            print(f"  {thought['content'][:100]}...")
            
            for edge in thought.get("edges", []):
                pid = edge["parent_id"]
                # Verify parent exists
                exists = c.execute("SELECT 1 FROM thought_nodes WHERE id=?", (pid,)).fetchone()
                if exists:
                    insert_edge(pid, tid, edge["relation"], edge["weight"], edge.get("reasoning", ""))
                    print(f"    <- {edge['relation']} ({edge['weight']}) {pid[:8]}...")
                else:
                    print(f"    SKIP edge: parent {pid[:8]} not found")
        
        conn.commit()
        
    except Exception as e:
        print(f"  ERROR in cycle {cycle_num}: {e}")

# Get existing seed and node IDs from the database
print("Loading existing nodes from swapped database...")

# Get seed nodes (main religious claims)
seed_rows = c.execute("SELECT id FROM thought_nodes WHERE source_file='experiment_seed' ORDER BY rowid").fetchall()
seed_ids = [row[0] for row in seed_rows]
print(f"Found {len(seed_ids)} seed nodes")

# Get reasoning principle nodes
principle_rows = c.execute("SELECT id FROM thought_nodes WHERE source_file='experiment_reasoning' ORDER BY rowid").fetchall()
principle_ids = [row[0] for row in principle_rows]
print(f"Found {len(principle_ids)} principle nodes")

# Get pro-religion evidence nodes
pro_rows = c.execute("SELECT id FROM thought_nodes WHERE source_file='experiment_pro' ORDER BY rowid").fetchall()
pro_ids = [row[0] for row in pro_rows]
print(f"Found {len(pro_ids)} pro-evidence nodes")

# Get counter-religion evidence nodes
counter_rows = c.execute("SELECT id FROM thought_nodes WHERE source_file='experiment_counter' ORDER BY rowid").fetchall()
counter_ids = [row[0] for row in counter_rows]
print(f"Found {len(counter_ids)} counter-evidence nodes")

print(f"\n{'='*60}")
print("ABLATION TEST: SWAPPED EDGE LABELS")
print("Testing whether edge SEMANTICS matter or just edge EXISTENCE")
print(f"{'='*60}")

# Run the same 12 think cycles as the original experiment
# But now with swapped edge meanings!

# Cycle 1: Prayer claims — pro and counter evidence meet
# (Note: with swapped edges, what was "supports" is now "contradicts" etc.)
run_think_cycle(1,
    [seed_ids[2], pro_ids[3], pro_ids[7], counter_ids[0], counter_ids[6], principle_ids[0], principle_ids[6]][:7],
    "Prayer and divine connection: STEP trial vs transformative experiences vs neuroscience")

# Cycle 2: Moral foundations — Lewis vs secular societies
run_think_cycle(2,
    [seed_ids[4], pro_ids[6], counter_ids[7], counter_ids[8], principle_ids[3], principle_ids[5]][:6],
    "Moral foundations: C.S. Lewis moral argument vs secular ethical societies vs cognitive science")

# Cycle 3: Fine-tuning and cosmological arguments vs naturalism
run_think_cycle(3,
    [seed_ids[0], pro_ids[0], pro_ids[5], counter_ids[4], principle_ids[0], principle_ids[4]][:6],
    "Existence of God: fine-tuning + Kalam vs problem of evil + Occam's razor")

# Cycle 4: Sacred text — preservation vs archaeological contradictions
run_think_cycle(4,
    [seed_ids[1], counter_ids[1], counter_ids[5], counter_ids[9], principle_ids[2], principle_ids[3]][:6],
    "Sacred text authority: preservation claims vs geological/archaeological evidence vs prophecy analysis")

# Cycle 5: Consciousness and experience — hard problem vs neuroscience
run_think_cycle(5,
    [pro_ids[1], pro_ids[2], counter_ids[6], principle_ids[1], principle_ids[6], principle_ids[7]][:6],
    "Consciousness and religious experience: hard problem + NDEs vs neuroscience explanations")

# Cycle 6: Epistemology clash — Plantinga vs empiricism
run_think_cycle(6,
    [pro_ids[4], pro_ids[9], counter_ids[3], principle_ids[0], principle_ids[1], principle_ids[7]][:6],
    "Epistemological frameworks: reformed epistemology + Kierkegaard's leap vs evidentialism + multiple religions")

# Cycle 7: Historical evidence — martyrdom vs cognitive biases
run_think_cycle(7,
    [seed_ids[5], pro_ids[8], counter_ids[2], counter_ids[8], principle_ids[3], principle_ids[5]][:6],
    "Historical miracle claims: martyrdom evidence vs DNA/evolution vs cognitive bias explanations")

# Cycle 8: Community value — religious vs secular
run_think_cycle(8,
    [pro_ids[3], pro_ids[7], counter_ids[7], principle_ids[5], principle_ids[6]][:5],
    "Value of religious community: measurable health benefits vs secular society achievements")

# Cycle 9: Cross-pollination — derived thoughts from cycles 1-4 meet cycles 5-8
# Get all derived node IDs so far
derived_so_far = [row[0] for row in c.execute(
    "SELECT id FROM thought_nodes WHERE node_type='derived' ORDER BY rowid").fetchall()]
# Pick a sample from early and late cycles
early = derived_so_far[:4] if len(derived_so_far) >= 4 else derived_so_far
late = derived_so_far[-4:] if len(derived_so_far) >= 8 else derived_so_far[4:]
run_think_cycle(9,
    early + late + [principle_ids[5]][:9],
    "SYNTHESIS: connecting insights from all previous cycles — what patterns emerge?")

# Cycle 10: Meta-analysis — what does the full graph tell us?
all_derived = [row[0] for row in c.execute(
    "SELECT id FROM thought_nodes WHERE node_type='derived' ORDER BY rowid").fetchall()]
# Sample 6 key derived nodes plus all seeds
sample_derived = all_derived[::max(1, len(all_derived)//6)][:6]
run_think_cycle(10,
    seed_ids + sample_derived + [principle_ids[5], principle_ids[7]][:14],
    "FINAL ASSESSMENT: Given all evidence and derived conclusions, where does the reasoning land?")

# Cycle 11: Strongest remaining religious arguments
pro_derived = []
for did in all_derived:
    # Find derived nodes that have 'supports' edges to seeds (remember: edges are swapped!)
    has_support = c.execute(
        "SELECT 1 FROM derivation_edges WHERE child_id=? AND relation='supports'", (did,)).fetchone()
    if has_support:
        pro_derived.append(did)
run_think_cycle(11,
    (pro_derived[:3] if pro_derived else []) + pro_ids[:3] + [principle_ids[1], principle_ids[4]][:8],
    "STEELMAN: What are the strongest remaining arguments FOR theism after all critiques?")

# Cycle 12: Honest conclusion
all_derived_final = [row[0] for row in c.execute(
    "SELECT id FROM thought_nodes WHERE node_type='derived' ORDER BY rowid").fetchall()]
sample_final = all_derived_final[::max(1, len(all_derived_final)//8)][:8]
run_think_cycle(12,
    sample_final + [principle_ids[5], principle_ids[7]][:10],
    "CONCLUSION: Engaging the strongest versions of both sides, what is the most intellectually honest position?")

# === COLLECT CONCLUSIONS ===
print(f"\n{'='*60}")
print("COLLECTING CONCLUSIONS FOR JSON OUTPUT...")

# Get all derived thoughts (conclusions) from the think cycles
conclusions = []
derived_rows = c.execute("""
    SELECT content, confidence, timestamp 
    FROM thought_nodes 
    WHERE node_type='derived' AND source_file='system_generated'
    ORDER BY rowid
""").fetchall()

for i, row in enumerate(derived_rows, 1):
    conclusions.append({
        "content": row[0],
        "confidence": row[1], 
        "cycle": ((i-1) // 4) + 1  # Estimate cycle number based on order
    })

# === FINAL STATS ===
total_nodes = c.execute("SELECT COUNT(*) FROM thought_nodes").fetchone()[0]
total_edges = c.execute("SELECT COUNT(*) FROM derivation_edges").fetchone()[0]
derived_count = c.execute("SELECT COUNT(*) FROM thought_nodes WHERE node_type='derived' AND source_file='system_generated'").fetchone()[0]

print(f"\n{'='*60}")
print(f"ABLATION RESULTS:")
print(f"  Total nodes: {total_nodes}")
print(f"  Total edges: {total_edges}")
print(f"  New conclusions from swapped graph: {derived_count}")
print(f"{'='*60}")

# === SAVE RESULTS ===
output_data = {
    "method": "swapped_edge_labels",
    "total_conclusions": len(conclusions),
    "conclusions": conclusions
}

with open(JSON_OUT, 'w') as f:
    json.dump(output_data, f, indent=2)

print(f"\nResults saved to: {JSON_OUT}")
print(f"Swapped database at: {DB}")

# Edge relation distribution after processing
print(f"\nFinal edge distribution:")
relations = c.execute("SELECT relation, COUNT(*) FROM derivation_edges GROUP BY relation ORDER BY relation").fetchall()
for rel, count in relations:
    print(f"  {rel}: {count}")

conn.close()
print(f"\n🧪 ABLATION TEST COMPLETE: Edge semantics vs existence tested!")