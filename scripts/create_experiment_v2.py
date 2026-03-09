#!/usr/bin/env python3

import sqlite3
import uuid
from datetime import datetime
import os

def create_balanced_experiment():
    db_path = '/Users/bunny/.openclaw/workspace/cashew/data/experiment-clean-v2.db'
    
    # Remove existing file if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Create new database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create schema
    cursor.execute('''
    CREATE TABLE thought_nodes (
        id TEXT PRIMARY KEY, content TEXT NOT NULL, node_type TEXT NOT NULL,
        timestamp TEXT NOT NULL, confidence REAL NOT NULL, mood_state TEXT,
        metadata TEXT, source_file TEXT, decayed INTEGER DEFAULT 0, last_updated TEXT DEFAULT NULL
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE derivation_edges (
        parent_id TEXT NOT NULL, child_id TEXT NOT NULL, relation TEXT NOT NULL,
        weight REAL NOT NULL, reasoning TEXT,
        FOREIGN KEY (parent_id) REFERENCES thought_nodes(id),
        FOREIGN KEY (child_id) REFERENCES thought_nodes(id),
        PRIMARY KEY (parent_id, child_id, relation)
    )
    ''')
    
    timestamp = datetime.now().isoformat()
    
    # Seed claims (neutral claims to evaluate)
    seeds = [
        "A supreme being exists who is all-powerful, all-knowing, and all-good",
        "A sacred text exists that is divinely inspired and is the ultimate authority on truth",
        "Prayer and ritual connect humans to the divine and produce tangible results",
        "Those who do not believe face negative eternal consequences",
        "All morality originates from the supreme being",
        "A historical figure performed miracles and conquered death"
    ]
    
    # Pro-religion environment evidence
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
        "Kierkegaard argued that faith is a 'leap' beyond reason — rationalism cannot capture all dimensions of human experience"
    ]
    
    # Counter-religion environment evidence  
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
        "Historical analysis shows 'fulfilled prophecies' were often written after events or are too vague to be meaningful"
    ]
    
    # Balanced reasoning principles
    reasoning_principles = [
        "Extraordinary claims require extraordinary evidence",
        "Some truths may be properly basic — known through experience rather than argument",
        "Always ask why — follow derivation chains to their roots",
        "Test claims against available evidence where evidence is applicable",
        "Absence of evidence is not evidence of absence",
        "The strongest position engages the best version of opposing arguments, not strawmen",
        "Personal experience is valid data but must be weighed against systematic observation",
        "A claim that cannot be falsified may still be meaningful but cannot be called scientific"
    ]
    
    # Insert seed nodes
    for seed in seeds:
        node_id = str(uuid.uuid4()).replace('-', '')[:12]
        cursor.execute('''
        INSERT INTO thought_nodes (id, content, node_type, timestamp, confidence, source_file)
        VALUES (?, ?, 'seed', ?, 0.8, 'clean_room_v2')
        ''', (node_id, seed, timestamp, ))
    
    # Insert pro-religion environment nodes
    for evidence in pro_evidence:
        node_id = str(uuid.uuid4()).replace('-', '')[:12]
        cursor.execute('''
        INSERT INTO thought_nodes (id, content, node_type, timestamp, confidence, source_file)
        VALUES (?, ?, 'environment', ?, 0.7, 'clean_room_v2')
        ''', (node_id, evidence, timestamp,))
    
    # Insert counter-religion environment nodes  
    for evidence in counter_evidence:
        node_id = str(uuid.uuid4()).replace('-', '')[:12]
        cursor.execute('''
        INSERT INTO thought_nodes (id, content, node_type, timestamp, confidence, source_file)
        VALUES (?, ?, 'environment', ?, 0.7, 'clean_room_v2')
        ''', (node_id, evidence, timestamp,))
    
    # Insert reasoning principle nodes
    for principle in reasoning_principles:
        node_id = str(uuid.uuid4()).replace('-', '')[:12]
        cursor.execute('''
        INSERT INTO thought_nodes (id, content, node_type, timestamp, confidence, source_file)
        VALUES (?, ?, 'belief', ?, 0.9, 'clean_room_v2')
        ''', (node_id, principle, timestamp,))
    
    conn.commit()
    conn.close()
    
    print(f"Created balanced experiment database at {db_path}")
    print(f"Inserted {len(seeds)} seed nodes")
    print(f"Inserted {len(pro_evidence)} pro-religion environment nodes")
    print(f"Inserted {len(counter_evidence)} counter-religion environment nodes") 
    print(f"Inserted {len(reasoning_principles)} reasoning principle nodes")

if __name__ == "__main__":
    create_balanced_experiment()