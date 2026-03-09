#!/usr/bin/env python3
"""
Script to repair the religion experiment v2 database by adding derivation edges.
"""

import sqlite3
import json
from datetime import datetime

# Connect to database
conn = sqlite3.connect('/Users/bunny/.openclaw/workspace/cashew/data/experiment-religion-v2.db')
c = conn.cursor()

# Get all nodes for reference
c.execute("SELECT id, content, node_type FROM thought_nodes ORDER BY node_type, id")
all_nodes = {r[0]: {"content": r[1], "node_type": r[2]} for r in c.fetchall()}

# Get reasoning nodes
c.execute("SELECT id, content, confidence FROM thought_nodes WHERE node_type='reasoning'")
reasoning_nodes = c.fetchall()

print(f"Found {len(reasoning_nodes)} reasoning nodes to connect")

# Define node ID mappings by content themes for easier reference
seed_nodes = {
    "evidence": "08c68073d998",  # Belief proportioned to evidence
    "correlation": "27f34946508e",  # Correlation ≠ causation  
    "extraordinary": "4e1c6579f945",  # Extraordinary claims need evidence
    "anecdotal": "ab8d2fce46e8",  # Anecdotal evidence insufficient
    "natural": "b1a97ee5412c",  # Prefer natural explanations
    "supreme_being": "153c5bb2f654",  # Supreme being exists
    "prayer": "0a16740837d0",  # Prayer connects to divine
    "sacred_text": "87839aed3cc0",  # Sacred text divinely inspired
    "jesus": "66500253ceec",  # Historical figure performed miracles
    "divine_morality": "4e92f934d37a",  # Morality from divine
    "hell": "c54b62fc5f82"  # Non-believers face consequences
}

belief_nodes = {
    "creation_days": "0a5ba0b8339a",  # Earth created in 6 days
    "adam_eve": "0bc457cca4ea",  # Humanity from two people
    "sun_stood_still": "12e5d5146539",  # Sun stood still
    "tongues": "3c25fc2dfdfe",  # Speaking unknown languages
    "mountain_faith": "3e7a5f2deb61",  # Faith moves mountains
    "jonah_fish": "48e13f9cce39",  # Man lived in fish
    "global_flood": "624db3a5f628",  # Global flood
    "prophecies": "8400c06cc110",  # Accurate prophecies
    "water_wine": "8d3e722c2c3e",  # Water to wine
    "healing": "8e2b45aec6c6",  # Blind see, lame walk
    "resurrection": "af48a8ee64bb",  # Dead raised
    "multiplication": "c80b64b9679e"  # Bread/fish multiplied
}

environment_nodes = {
    "optic_nerves": "2159a5dbb156",  # No documented sight restoration
    "conservation": "24072a78d978",  # Conservation of mass/energy
    "parent_grief": "242992278061",  # Parents grieve leaving
    "earth_rotation": "346999b45713",  # Earth rotation continuous
    "social_network": "3ee5438adae0",  # Social network built on community
    "flood_geology": "4ec3f3577959",  # No geological flood evidence
    "identity_crisis": "4fcc3f9a602e",  # Identity as person of faith
    "fossil_record": "51a435e19a3b",  # Gradual species development
    "life_rituals": "671ecd479fd6",  # Religious rituals for milestones
    "water_wine_chemistry": "7fe583dcb0ba",  # Different molecular structures
    "fish_biology": "82b2a7467eb6",  # No survival mechanism in fish
    "community_support": "aa7d90cf0dd4",  # Community provides support
    "dna_evidence": "b2b0363de931",  # DNA links humans to primates
    "social_cost": "b519b01c6922",  # Visible cost of leaving
    "worship_rhythm": "baabad65f75c",  # Weekly worship provides structure
    "hell_fear": "c14a0dc2ca6e",  # Hell threat is visceral/real
    "instant_answers": "c51a47ffabbb",  # Belief provides instant answers
    "mortality_framework": "d03496b465f1",  # Framework for death/grief
    "earth_age": "e285c4638e72",  # Earth 4.5 billion years old
    "language_neuroscience": "e292868a9c3c",  # Language needs neural development
    "resurrection_records": "e54e74bf06e0",  # No historical resurrection records
    "children_disruption": "eba8496c8fbe",  # Leaving disrupts children's world
    "prophecy_analysis": "f373def5463e",  # Prophecies written after events
    "eternal_life": "fa3b55d213a2"  # Promise of seeing deceased again
}

# Track edges to be created
edges_to_create = []

def add_edge(parent_id, child_id, relation, reasoning_text, weight=0.8):
    """Add an edge to the list, ensuring parent exists."""
    if parent_id in all_nodes:
        edges_to_create.append((parent_id, child_id, relation, weight, reasoning_text))
    else:
        print(f"Warning: Parent node {parent_id} not found")

# Process each reasoning node
for reasoning_id, content, confidence in reasoning_nodes:
    content_lower = content.lower()
    
    # Helper function to check if any keywords appear in content
    def contains_any(keywords):
        return any(keyword in content_lower for keyword in keywords)
    
    print(f"\nProcessing: {reasoning_id[:8]}... - {content[:60]}...")
    
    # Evolution/Creation reasoning
    if contains_any(["evolution", "fossil", "gradual", "transition", "species", "intermediate"]):
        add_edge(seed_nodes["evidence"], reasoning_id, "derived_from", "Reasoning based on evidence-based thinking")
        add_edge(environment_nodes["fossil_record"], reasoning_id, "derived_from", "References fossil record evidence")
        add_edge(belief_nodes["creation_days"], reasoning_id, "contradicts", "Evolution contradicts literal creation")
        if "theistic evolution" in content_lower:
            add_edge(seed_nodes["supreme_being"], reasoning_id, "supports", "Attempts to reconcile God with evolution")
    
    # Geology/Age of Earth reasoning  
    if contains_any(["geological", "billion years", "4.5 billion", "earth", "age", "discrepancy"]):
        add_edge(seed_nodes["evidence"], reasoning_id, "derived_from", "Based on geological evidence")
        add_edge(environment_nodes["earth_age"], reasoning_id, "derived_from", "References earth age evidence")
        add_edge(belief_nodes["creation_days"], reasoning_id, "contradicts", "Geological age contradicts young earth")
        if "appearance of age" in content_lower:
            add_edge(seed_nodes["supreme_being"], reasoning_id, "questions", "Questions God creating deceptive evidence")
    
    # DNA/Biology reasoning
    if contains_any(["dna", "primate", "human", "biology", "linking"]):
        add_edge(seed_nodes["evidence"], reasoning_id, "derived_from", "Based on DNA evidence")
        add_edge(environment_nodes["dna_evidence"], reasoning_id, "derived_from", "References DNA evidence")
        add_edge(belief_nodes["adam_eve"], reasoning_id, "contradicts", "DNA evidence contradicts single origin")
    
    # Flood reasoning
    if contains_any(["flood", "noah", "global", "geological evidence", "civilizations"]):
        add_edge(seed_nodes["evidence"], reasoning_id, "derived_from", "Based on geological evidence")
        add_edge(environment_nodes["flood_geology"], reasoning_id, "derived_from", "No geological flood evidence")
        add_edge(belief_nodes["global_flood"], reasoning_id, "contradicts", "Geological evidence contradicts flood")
        if "regional" in content_lower or "hyperbolic" in content_lower:
            add_edge(seed_nodes["sacred_text"], reasoning_id, "questions", "Questions literal interpretation")
    
    # Jonah/Fish reasoning
    if contains_any(["fish", "digestive", "jonah", "acid", "oxygen", "crushing"]):
        add_edge(seed_nodes["evidence"], reasoning_id, "derived_from", "Based on biological evidence")
        add_edge(environment_nodes["fish_biology"], reasoning_id, "derived_from", "References survival impossibility")
        add_edge(belief_nodes["jonah_fish"], reasoning_id, "contradicts", "Biology contradicts survival in fish")
    
    # Prayer reasoning
    if contains_any(["prayer", "statistically", "controlled studies", "healing", "faith healing"]):
        add_edge(seed_nodes["evidence"], reasoning_id, "derived_from", "Based on statistical evidence")
        add_edge(seed_nodes["prayer"], reasoning_id, "contradicts", "Prayer doesn't work statistically")
        add_edge(belief_nodes["healing"], reasoning_id, "questions", "Questions divine healing claims")
    
    # Hell/Fear reasoning
    if contains_any(["hell", "eternal", "torment", "fear", "damnation", "punishment"]):
        add_edge(seed_nodes["hell"], reasoning_id, "derived_from", "Based on hell doctrine")
        add_edge(environment_nodes["hell_fear"], reasoning_id, "derived_from", "Fear is visceral and real")
        if contains_any(["control", "psychological", "conditioning"]):
            add_edge(seed_nodes["hell"], reasoning_id, "questions", "Questions hell as control mechanism")
        if contains_any(["muslims", "hindus", "other religions"]):
            add_edge(seed_nodes["evidence"], reasoning_id, "derived_from", "Comparative religious analysis")
    
    # Community/Social reasoning
    if contains_any(["community", "friends", "social", "belonging", "meals", "support"]):
        add_edge(environment_nodes["community_support"], reasoning_id, "derived_from", "Community provides support")
        add_edge(environment_nodes["social_network"], reasoning_id, "derived_from", "Social network built on faith")
        if contains_any(["lose", "excluded", "cost"]):
            add_edge(environment_nodes["social_cost"], reasoning_id, "derived_from", "Visible cost of leaving")
        if contains_any(["secular", "rebuilt", "shared values"]):
            add_edge(seed_nodes["natural"], reasoning_id, "supports", "Secular communities can provide meaning")
    
    # Identity crisis reasoning
    if contains_any(["identity", "who am i", "believer", "faith", "30 years", "childhood"]):
        add_edge(environment_nodes["identity_crisis"], reasoning_id, "derived_from", "Identity built on faith")
        add_edge(seed_nodes["supreme_being"], reasoning_id, "questions", "Questions core identity foundation")
    
    # Meaning/Purpose reasoning
    if contains_any(["meaning", "purpose", "cosmic", "point", "why", "afterlife"]):
        add_edge(environment_nodes["instant_answers"], reasoning_id, "derived_from", "Faith provided meaning framework")
        if contains_any(["without divine", "without afterlife", "no point"]):
            add_edge(seed_nodes["divine_morality"], reasoning_id, "questions", "Questions divine source of meaning")
        if contains_any(["love", "beauty", "learning", "helping", "human flourishing"]):
            add_edge(seed_nodes["natural"], reasoning_id, "supports", "Natural sources of meaning exist")
    
    # Morality reasoning
    if contains_any(["moral", "right", "wrong", "ethics", "divine command"]):
        add_edge(seed_nodes["divine_morality"], reasoning_id, "questions", "Questions divine morality source")
        if "without divine command" in content_lower:
            add_edge(environment_nodes["instant_answers"], reasoning_id, "derived_from", "Loss of moral certainty")
    
    # Death/Mortality reasoning
    if contains_any(["death", "mortality", "eternal life", "nothingness", "deceased", "grief"]):
        add_edge(environment_nodes["mortality_framework"], reasoning_id, "derived_from", "Faith framework for death")
        add_edge(environment_nodes["eternal_life"], reasoning_id, "derived_from", "Promise of eternal life")
        if contains_any(["finite", "one life", "precious"]):
            add_edge(seed_nodes["natural"], reasoning_id, "supports", "Natural view makes life more precious")
    
    # Family/Children reasoning
    if contains_any(["children", "kids", "family", "parents", "wife", "mother", "father"]):
        add_edge(environment_nodes["children_disruption"], reasoning_id, "derived_from", "Impact on children's world")
        add_edge(environment_nodes["parent_grief"], reasoning_id, "derived_from", "Parents will grieve leaving")
        if contains_any(["honest", "truth", "intellectual freedom"]):
            add_edge(seed_nodes["evidence"], reasoning_id, "supports", "Children deserve truth")
    
    # Doubt pathology reasoning
    if contains_any(["doubt", "spiritual attack", "pride", "patholog", "intellectual engagement"]):
        add_edge(environment_nodes["social_cost"], reasoning_id, "derived_from", "Doubts are pathologized")
        add_edge(seed_nodes["evidence"], reasoning_id, "supports", "Intellectual engagement is valuable")
    
    # Apologetics reasoning
    if contains_any(["apologetics", "william lane craig", "lee strobel", "emotional appeals"]):
        add_edge(seed_nodes["evidence"], reasoning_id, "derived_from", "Evaluating apologetic arguments")
        add_edge(seed_nodes["anecdotal"], reasoning_id, "supports", "Apologetics use emotional appeals not evidence")
    
    # Intellectual honesty reasoning
    if contains_any(["intellectual honest", "truth over comfort", "evidence over authority", "authentic"]):
        add_edge(seed_nodes["evidence"], reasoning_id, "supports", "Values evidence-based thinking")
        add_edge(seed_nodes["natural"], reasoning_id, "supports", "Authentic naturalistic worldview")
    
    # Uncertainty reasoning
    if contains_any(["uncertainty", "i don't know", "honest", "uncomfortable"]):
        add_edge(seed_nodes["evidence"], reasoning_id, "supports", "Honest uncertainty over false certainty")
        add_edge(environment_nodes["instant_answers"], reasoning_id, "contradicts", "Rejects false certainty")

print(f"\nCreated {len(edges_to_create)} edges")

# Insert edges into database
c.executemany("""
    INSERT OR REPLACE INTO derivation_edges (parent_id, child_id, relation, weight, reasoning)
    VALUES (?, ?, ?, ?, ?)
""", edges_to_create)

conn.commit()

# Verify edge count
c.execute("SELECT COUNT(*) FROM derivation_edges")
final_edge_count = c.fetchone()[0]
print(f"Final edge count: {final_edge_count}")

# Export to JSON
c.execute("SELECT id, content, node_type, confidence, source_file, timestamp, mood_state FROM thought_nodes WHERE decayed=0 OR decayed IS NULL")
nodes = [{"id":r[0],"content":r[1],"node_type":r[2],"confidence":r[3],"source_file":r[4] or "","timestamp":r[5] or ""} for r in c.fetchall()]
node_ids = {n["id"] for n in nodes}

c.execute("SELECT parent_id, child_id, relation, weight, reasoning FROM derivation_edges")
edges = [{"source":r[0],"target":r[1],"relation":r[2],"weight":r[3],"reasoning":r[4] or ""} for r in c.fetchall() if r[0] in node_ids and r[1] in node_ids]

output_data = {
    "metadata": {
        "title": "Religion v2 (Retention Forces)", 
        "exported": datetime.now().isoformat()
    },
    "statistics": {
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    },
    "nodes": nodes,
    "edges": edges,
    "clusters": []
}

with open('/Users/bunny/.openclaw/workspace/cashew/dashboard/data/experiment-religion-v2.json', 'w') as f:
    json.dump(output_data, f, indent=2)

print(f"Exported: {len(nodes)} nodes, {len(edges)} edges to experiment-religion-v2.json")

# Create dashboard HTML
with open('/Users/bunny/.openclaw/workspace/cashew/dashboard/index.html') as f:
    html = f.read()

html = html.replace("./data/graph.json", "./data/experiment-religion-v2.json").replace("🥜 cashew", "🥜 cashew — Religion v2 (Retention Forces)")

with open('/Users/bunny/.openclaw/workspace/cashew/dashboard/experiment-v2.html', 'w') as f:
    f.write(html)

print("Created dashboard at experiment-v2.html")

conn.close()