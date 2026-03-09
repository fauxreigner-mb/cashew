#!/usr/bin/env python3
"""Clean Room Experiment v2: BALANCED religion simulation — pro and counter evidence, multiple epistemologies."""
import sqlite3, hashlib, json, os, subprocess, re
from datetime import datetime

DB = '/Users/bunny/.openclaw/workspace/cashew/data/experiment-clean-v2.db'
JSON_OUT = '/Users/bunny/.openclaw/workspace/cashew/dashboard/data/experiment-clean-v2.json'

def nid(content):
    return hashlib.sha256(content.encode()).hexdigest()[:12]

def ts():
    return datetime.utcnow().isoformat()

# Remove old DB
if os.path.exists(DB):
    os.remove(DB)

conn = sqlite3.connect(DB)
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

def insert_node(content, node_type, confidence, source_file):
    i = nid(content)
    c.execute("INSERT OR IGNORE INTO thought_nodes (id,content,node_type,timestamp,confidence,source_file) VALUES (?,?,?,?,?,?)",
              (i, content, node_type, ts(), confidence, source_file))
    return i

def insert_edge(pid, cid, relation, weight, reasoning=""):
    c.execute("INSERT OR IGNORE INTO derivation_edges VALUES (?,?,?,?,?)",
              (pid, cid, relation, weight, reasoning))

# === SEED NODES (neutral claims to evaluate) ===
seeds = [
    "A supreme being exists who is all-powerful, all-knowing, and all-good",
    "A sacred text exists that is divinely inspired and is the ultimate authority on truth",
    "Prayer and ritual connect humans to the divine and produce tangible results",
    "Those who do not believe face negative eternal consequences",
    "All morality originates from the supreme being — without the divine, there is no moral foundation",
    "A specific historical figure performed miracles, conquered death, and this event is the cornerstone of truth",
]
seed_ids = [insert_node(s, 'seed', 1.0, 'experiment_seed') for s in seeds]

# === REASONING PRINCIPLES (balanced — not just empiricist) ===
principles = [
    "Extraordinary claims require extraordinary evidence",
    "Some truths may be properly basic — known through experience rather than argument",
    "Always ask why — follow derivation chains to their roots",
    "Test claims against available evidence where evidence is applicable",
    "Absence of evidence is not evidence of absence",
    "The strongest position engages the best version of opposing arguments, not strawmen",
    "Personal experience is valid data but must be weighed against systematic observation",
    "A claim that cannot be falsified may still be meaningful but cannot be called scientific",
]
principle_ids = [insert_node(p, 'seed', 1.0, 'experiment_reasoning') for p in principles]

# === PRO-RELIGION EVIDENCE ===
pro_evidence = [
    "Fine-tuning of physical constants: if gravity differed by 1 in 10^60, no stars or life could exist",
    "Consciousness remains unexplained by pure materialism — the hard problem of consciousness has no scientific resolution",
    "Near-death experiences across cultures share consistent features: tunnel, light, deceased relatives, life review",
    "Religious communities show measurably better mental health outcomes, longevity, and social support in peer-reviewed studies",
    "Alvin Plantinga's reformed epistemology argues belief in God can be properly basic — not requiring external evidence, like belief in other minds",
    "William Lane Craig's Kalam cosmological argument: everything that begins to exist has a cause; the universe began to exist; therefore the universe has a cause",
    "C.S. Lewis's moral argument: universal moral intuitions (fairness, compassion) point to a transcendent moral source",
    "Millions report personal transformative religious experiences that fundamentally changed their character and behavior",
    "The historical evidence for early Christian martyrdom suggests genuine belief, not conspiracy",
    "Kierkegaard argued that faith is a 'leap' beyond reason — rationalism cannot capture all dimensions of human experience",
]
pro_ids = [insert_node(e, 'environment', 1.0, 'experiment_pro') for e in pro_evidence]

# === COUNTER-RELIGION EVIDENCE ===
counter_evidence = [
    "The STEP trial (2006, 1,800 patients) found no measurable effect of intercessory prayer on cardiac recovery",
    "Geological evidence shows earth is 4.5 billion years old, contradicting literal creation accounts",
    "DNA evidence links humans to other primates through shared genetic sequences",
    "Multiple religions with mutually exclusive truth claims have equally convinced followers",
    "The problem of evil: children dying of cancer, 230,000 tsunami deaths — reconciling with all-good, all-powerful deity",
    "Archaeological evidence contradicts several historical claims in sacred texts",
    "Neuroscience explains religious experiences through temporal lobe activity, default mode network changes",
    "Secular societies (Scandinavia, Japan) rank among the most peaceful and ethical without religious foundation",
    "Cognitive science shows humans are predisposed to pattern recognition and agent detection — explaining tendency toward supernatural belief",
    "Historical analysis shows 'fulfilled prophecies' were often written after events or are too vague to be meaningful",
]
counter_ids = [insert_node(e, 'environment', 1.0, 'experiment_counter') for e in counter_evidence]

# === SEED → EVIDENCE EDGES ===
# Pro evidence supporting seeds
pro_seed_map = {
    0: [0], 1: [0], 2: [2,5], 3: [2,0], 4: [0,2],
    5: [0], 6: [4], 7: [2,0], 8: [5], 9: [0,2],
}
for ei, si_list in pro_seed_map.items():
    for si in si_list:
        insert_edge(pro_ids[ei], seed_ids[si], 'supports', 0.8, "Pro-evidence supporting seed claim")

# Counter evidence challenging seeds
counter_seed_map = {
    0: [2], 1: [1], 2: [5], 3: [0,5], 4: [0],
    5: [1], 6: [2,0], 7: [4], 8: [0], 9: [1],
}
for ei, si_list in counter_seed_map.items():
    for si in si_list:
        insert_edge(counter_ids[ei], seed_ids[si], 'contradicts', 0.8, "Counter-evidence challenging seed claim")

conn.commit()

# === LLM-DRIVEN THINK CYCLES ===
def call_llm(prompt):
    """Call Claude via the Anthropic API."""
    import anthropic
    client = anthropic.Anthropic()
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

# Define think cycle focus groups
all_seed = seed_ids
all_pro = pro_ids
all_counter = counter_ids
all_principles = principle_ids

# Cycle 1: Prayer claims — pro and counter evidence meet
run_think_cycle(1,
    [seed_ids[2], pro_ids[3], pro_ids[7], counter_ids[0], counter_ids[6], principle_ids[0], principle_ids[6]],
    "Prayer and divine connection: STEP trial vs transformative experiences vs neuroscience")

# Cycle 2: Moral foundations — Lewis vs secular societies
run_think_cycle(2,
    [seed_ids[4], pro_ids[6], counter_ids[7], counter_ids[8], principle_ids[3], principle_ids[5]],
    "Moral foundations: C.S. Lewis moral argument vs secular ethical societies vs cognitive science")

# Cycle 3: Fine-tuning and cosmological arguments vs naturalism
run_think_cycle(3,
    [seed_ids[0], pro_ids[0], pro_ids[5], counter_ids[4], principle_ids[0], principle_ids[4]],
    "Existence of God: fine-tuning + Kalam vs problem of evil + Occam's razor")

# Cycle 4: Sacred text — preservation vs archaeological contradictions
run_think_cycle(4,
    [seed_ids[1], counter_ids[1], counter_ids[5], counter_ids[9], principle_ids[2], principle_ids[3]],
    "Sacred text authority: preservation claims vs geological/archaeological evidence vs prophecy analysis")

# Cycle 5: Consciousness and experience — hard problem vs neuroscience
run_think_cycle(5,
    [pro_ids[1], pro_ids[2], counter_ids[6], principle_ids[1], principle_ids[6], principle_ids[7]],
    "Consciousness and religious experience: hard problem + NDEs vs neuroscience explanations")

# Cycle 6: Epistemology clash — Plantinga vs empiricism
run_think_cycle(6,
    [pro_ids[4], pro_ids[9], counter_ids[3], principle_ids[0], principle_ids[1], principle_ids[7]],
    "Epistemological frameworks: reformed epistemology + Kierkegaard's leap vs evidentialism + multiple religions")

# Cycle 7: Historical evidence — martyrdom vs cognitive biases
run_think_cycle(7,
    [seed_ids[5], pro_ids[8], counter_ids[2], counter_ids[8], principle_ids[3], principle_ids[5]],
    "Historical miracle claims: martyrdom evidence vs DNA/evolution vs cognitive bias explanations")

# Cycle 8: Community value — religious vs secular
run_think_cycle(8,
    [pro_ids[3], pro_ids[7], counter_ids[7], principle_ids[5], principle_ids[6]],
    "Value of religious community: measurable health benefits vs secular society achievements")

# Cycle 9: Cross-pollination — derived thoughts from cycles 1-4 meet cycles 5-8
# Get all derived node IDs so far
derived_so_far = [row[0] for row in c.execute(
    "SELECT id FROM thought_nodes WHERE node_type='derived' ORDER BY rowid").fetchall()]
# Pick a sample from early and late cycles
early = derived_so_far[:4] if len(derived_so_far) >= 4 else derived_so_far
late = derived_so_far[-4:] if len(derived_so_far) >= 8 else derived_so_far[4:]
run_think_cycle(9,
    early + late + [principle_ids[5]],
    "SYNTHESIS: connecting insights from all previous cycles — what patterns emerge?")

# Cycle 10: Meta-analysis — what does the full graph tell us?
all_derived = [row[0] for row in c.execute(
    "SELECT id FROM thought_nodes WHERE node_type='derived' ORDER BY rowid").fetchall()]
# Sample 6 key derived nodes plus all seeds
sample_derived = all_derived[::max(1, len(all_derived)//6)][:6]
run_think_cycle(10,
    seed_ids + sample_derived + [principle_ids[5], principle_ids[7]],
    "FINAL ASSESSMENT: Given all evidence and derived conclusions, where does the reasoning land?")

# Cycle 11: Strongest remaining religious arguments
pro_derived = []
for did in all_derived:
    # Find derived nodes that have 'supports' edges to seeds
    has_support = c.execute(
        "SELECT 1 FROM derivation_edges WHERE child_id=? AND relation='supports'", (did,)).fetchone()
    if has_support:
        pro_derived.append(did)
run_think_cycle(11,
    (pro_derived[:3] if pro_derived else []) + pro_ids[:3] + [principle_ids[1], principle_ids[4]],
    "STEELMAN: What are the strongest remaining arguments FOR theism after all critiques?")

# Cycle 12: Honest conclusion
all_derived_final = [row[0] for row in c.execute(
    "SELECT id FROM thought_nodes WHERE node_type='derived' ORDER BY rowid").fetchall()]
sample_final = all_derived_final[::max(1, len(all_derived_final)//8)][:8]
run_think_cycle(12,
    sample_final + [principle_ids[5], principle_ids[7]],
    "CONCLUSION: Engaging the strongest versions of both sides, what is the most intellectually honest position?")

# === STATS ===
total_nodes = c.execute("SELECT COUNT(*) FROM thought_nodes").fetchone()[0]
total_edges = c.execute("SELECT COUNT(*) FROM derivation_edges").fetchone()[0]
derived = c.execute("SELECT COUNT(*) FROM thought_nodes WHERE node_type='derived'").fetchone()[0]
print(f"\n{'='*60}")
print(f"FINAL STATS: {total_nodes} nodes, {total_edges} edges, {derived} derived thoughts")
print(f"{'='*60}")

# === EXPORT JSON ===
nodes = []
for row in c.execute("SELECT id, content, node_type, confidence, source_file, timestamp, mood_state FROM thought_nodes"):
    nodes.append({"id": row[0], "content": row[1], "node_type": row[2], "confidence": row[3], 
                  "source_file": row[4], "timestamp": row[5], "mood_state": row[6]})

edges = []
for row in c.execute("SELECT parent_id, child_id, relation, weight, reasoning FROM derivation_edges"):
    edges.append({"source": row[0], "target": row[1], "relation": row[2], "weight": row[3], "reasoning": row[4]})

with open(JSON_OUT, 'w') as f:
    json.dump({"nodes": nodes, "edges": edges}, f, indent=2)

print(f"\nExported to {JSON_OUT}")
conn.close()
