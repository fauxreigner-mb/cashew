#!/usr/bin/env python3
"""Add missing edges for reasoning nodes that weren't connected."""

import sqlite3

conn = sqlite3.connect('/Users/bunny/.openclaw/workspace/cashew/data/experiment-religion-v2.db')
c = conn.cursor()

# Missing edges to add
missing_edges = [
    # c0cdf4fc5047 - Everyone I respect believes this
    ("3ee5438adae0", "c0cdf4fc5047", "derived_from", 0.8, "Pressure from respected community members"),
    ("c51a47ffabbb", "c0cdf4fc5047", "derived_from", 0.7, "Community provides authority and answers"),
    
    # 15b6eb425a9d - Feel profoundly alone
    ("3ee5438adae0", "15b6eb425a9d", "derived_from", 0.8, "Social isolation from questioning"),
    ("b519b01c6922", "15b6eb425a9d", "derived_from", 0.7, "Aware of social cost of doubt"),
    
    # bf3b52cdb898 - Avoiding Bible study
    ("08c68073d998", "bf3b52cdb898", "supports", 0.7, "Evidence contradicts taught beliefs"),
    ("87839aed3cc0", "bf3b52cdb898", "questions", 0.8, "Sacred text authority questioned"),
    
    # 775526e4da4f - Crossed invisible line
    ("08c68073d998", "775526e4da4f", "supports", 0.8, "Knowledge based on evidence"),
    ("4fcc3f9a602e", "775526e4da4f", "derived_from", 0.7, "Identity transformation from knowledge"),
    
    # f4a8b06e3a2f - Want freedom but need belonging
    ("3ee5438adae0", "f4a8b06e3a2f", "derived_from", 0.8, "Tension between freedom and community"),
    ("08c68073d998", "f4a8b06e3a2f", "supports", 0.6, "Values intellectual freedom"),
    
    # 65ab2d086338 - Reading atheist scholars
    ("08c68073d998", "65ab2d086338", "supports", 0.8, "Seeking evidence-based arguments"),
    ("4e1c6579f945", "65ab2d086338", "supports", 0.7, "Finding extraordinary evidence for claims"),
    
    # 05bfc78e63f0 - More scared of living lie
    ("08c68073d998", "05bfc78e63f0", "supports", 0.8, "Values truth over comfort"),
    ("c14a0dc2ca6e", "05bfc78e63f0", "derived_from", 0.7, "Fear of leaving vs fear of dishonesty"),
    
    # 93231aba9d7f - Living contradiction is exhausting
    ("4fcc3f9a602e", "93231aba9d7f", "derived_from", 0.8, "Identity conflict from hidden doubts"),
    ("3ee5438adae0", "93231aba9d7f", "derived_from", 0.7, "Social pressure to maintain facade"),
    
    # 8ce447ab63d8 - Maybe smarter theologians have answers
    ("87839aed3cc0", "8ce447ab63d8", "questions", 0.7, "Hoping for theological solutions"),
    ("08c68073d998", "8ce447ab63d8", "derived_from", 0.6, "Seeking better evidence/arguments"),
    
    # 6320afeb5055 - God deceptive with false evidence
    ("153c5bb2f654", "6320afeb5055", "contradicts", 0.8, "Deception contradicts all-good nature"),
    ("e285c4638e72", "6320afeb5055", "derived_from", 0.8, "Geological evidence appears deceptive"),
    
    # b10a6c1be6b4 - Missing rituals and communion
    ("baabad65f75c", "b10a6c1be6b4", "derived_from", 0.8, "Rituals provide life structure"),
    ("671ecd479fd6", "b10a6c1be6b4", "derived_from", 0.7, "Religious rituals for life milestones"),
]

# Insert the missing edges
c.executemany("""
    INSERT OR REPLACE INTO derivation_edges (parent_id, child_id, relation, weight, reasoning)
    VALUES (?, ?, ?, ?, ?)
""", missing_edges)

conn.commit()

# Check final counts
c.execute("SELECT COUNT(*) FROM derivation_edges")
total_edges = c.fetchone()[0]

c.execute("""
    SELECT COUNT(DISTINCT de.child_id)
    FROM derivation_edges de
    JOIN thought_nodes tn ON de.child_id = tn.id
    WHERE tn.node_type = 'reasoning'
""")
connected_reasoning = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM thought_nodes WHERE node_type = 'reasoning'")
total_reasoning = c.fetchone()[0]

print(f"Added {len(missing_edges)} edges")
print(f"Final edge count: {total_edges}")
print(f"Connected reasoning nodes: {connected_reasoning}/{total_reasoning}")

conn.close()