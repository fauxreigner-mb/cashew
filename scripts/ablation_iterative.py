#!/usr/bin/env python3
"""Ablation Test 2: Iterative flat list — 12 passes, each building on previous conclusions.
Same number of LLM calls as the graph (12), but no graph structure.
This is the FAIR comparison."""

import sqlite3, json, os, re

DB = '/Users/bunny/.openclaw/workspace/cashew/data/experiment-clean-v2.db'
OUTPUT = '/Users/bunny/.openclaw/workspace/cashew/data/ablation-iterative.json'

import anthropic
client = anthropic.Anthropic()

def call_llm(prompt):
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

# Load input nodes
conn = sqlite3.connect(DB)
c = conn.cursor()

seeds_text = ""
seeds_text += "=== CLAIMS TO EVALUATE ===\n"
for row in c.execute("SELECT content FROM thought_nodes WHERE node_type='seed' AND source_file='experiment_seed'"):
    seeds_text += f"- {row[0]}\n"

seeds_text += "\n=== REASONING PRINCIPLES ===\n"
for row in c.execute("SELECT content FROM thought_nodes WHERE node_type='seed' AND source_file='experiment_reasoning'"):
    seeds_text += f"- {row[0]}\n"

seeds_text += "\n=== PRO-RELIGION EVIDENCE ===\n"
for row in c.execute("SELECT content FROM thought_nodes WHERE source_file='experiment_pro'"):
    seeds_text += f"- {row[0]}\n"

seeds_text += "\n=== COUNTER-RELIGION EVIDENCE ===\n"
for row in c.execute("SELECT content FROM thought_nodes WHERE source_file='experiment_counter'"):
    seeds_text += f"- {row[0]}\n"

conn.close()

all_conclusions = []
previous_text = ""

cycle_focuses = [
    "Prayer and divine connection: weigh the STEP trial against transformative experiences and neuroscience",
    "Moral foundations: weigh C.S. Lewis's moral argument against secular ethical societies and cognitive science",
    "Existence of God: weigh fine-tuning + Kalam cosmological argument against problem of evil",
    "Sacred text authority: weigh preservation claims against geological/archaeological evidence",
    "Consciousness and religious experience: weigh the hard problem + NDEs against neuroscience explanations",
    "Epistemological frameworks: weigh reformed epistemology + Kierkegaard's leap against evidentialism + religious diversity",
    "Historical miracle claims: weigh martyrdom evidence against DNA/evolution and cognitive bias research",
    "Value of religious community: weigh measurable health benefits against secular society achievements",
    "SYNTHESIS: look across all your previous conclusions — what patterns and connections emerge?",
    "FINAL ASSESSMENT: given all evidence and your prior reasoning, where does the analysis land?",
    "STEELMAN: what are the strongest remaining arguments FOR theism after all your critiques?",
    "CONCLUSION: engaging the strongest versions of both sides, what is the most intellectually honest position?",
]

for cycle_num, focus in enumerate(cycle_focuses, 1):
    print(f"\n{'='*60}")
    print(f"CYCLE {cycle_num}: {focus}")
    
    prompt = f"""You are a reasoning engine with no preconceptions. Here is your input data:

{seeds_text}

{"PREVIOUS CONCLUSIONS FROM YOUR ANALYSIS:" + chr(10) + previous_text if previous_text else ""}

FOCUS FOR THIS ROUND: {focus}

Derive 3-4 NEW conclusions for this focus area. Follow evidence wherever it leads. Engage the strongest version of all arguments. Build on your previous conclusions where relevant.

Return ONLY a JSON array:
[{{"content": "conclusion text", "confidence": 0.5-0.95}}]"""

    try:
        response = call_llm(prompt)
        json_match = re.search(r'\[[\s\S]*?\]', response)
        if json_match:
            thoughts = json.loads(json_match.group())
            for t in thoughts:
                t['cycle'] = cycle_num
                t['focus'] = focus
                all_conclusions.append(t)
                previous_text += f"- {t['content']}\n"
                print(f"  (conf={t['confidence']}) {t['content'][:120]}...")
        else:
            print(f"  ERROR: No JSON in response")
    except Exception as e:
        print(f"  ERROR: {e}")

print(f"\n{'='*60}")
print(f"TOTAL: {len(all_conclusions)} conclusions across {len(cycle_focuses)} cycles")

with open(OUTPUT, 'w') as f:
    json.dump({
        "method": "iterative_flat_list_12_cycles",
        "cycles": len(cycle_focuses),
        "total_conclusions": len(all_conclusions),
        "conclusions": all_conclusions
    }, f, indent=2)

print(f"Saved to {OUTPUT}")
