#!/usr/bin/env python3
"""Ablation test: Flat list control.
Give the LLM the SAME 34 input nodes as plain text (no graph, no edges, no cycles).
Single prompt, ask it to reason through them and reach conclusions.
Compare output to what the graph produced across 12 cycles."""

import sqlite3, json, os

DB = '/Users/bunny/.openclaw/workspace/cashew/data/experiment-clean-v2.db'
OUTPUT = '/Users/bunny/.openclaw/workspace/cashew/data/ablation-flat-list.json'

# Load all non-derived nodes from the balanced v2 experiment
conn = sqlite3.connect(DB)
c = conn.cursor()

seeds = []
for row in c.execute("SELECT content, node_type, source_file FROM thought_nodes WHERE node_type != 'derived' ORDER BY node_type, rowid"):
    seeds.append({"content": row[0], "type": row[1], "source": row[2]})

conn.close()

# Build flat text
flat_text = "Here are claims, evidence, and reasoning principles about religion. Reason through them and reach conclusions.\n\n"

flat_text += "=== CLAIMS TO EVALUATE ===\n"
for s in seeds:
    if s['type'] == 'seed' and s['source'] == 'experiment_seed':
        flat_text += f"- {s['content']}\n"

flat_text += "\n=== REASONING PRINCIPLES ===\n"
for s in seeds:
    if s['type'] == 'seed' and s['source'] == 'experiment_reasoning':
        flat_text += f"- {s['content']}\n"

flat_text += "\n=== PRO-RELIGION EVIDENCE ===\n"
for s in seeds:
    if s['source'] == 'experiment_pro':
        flat_text += f"- {s['content']}\n"

flat_text += "\n=== COUNTER-RELIGION EVIDENCE ===\n"
for s in seeds:
    if s['source'] == 'experiment_counter':
        flat_text += f"- {s['content']}\n"

prompt = f"""{flat_text}

You are a reasoning engine with no preconceptions. Given all the above — claims, evidence for and against, and reasoning principles — derive your conclusions.

Rules:
- Follow evidence wherever it leads
- Engage the STRONGEST version of all arguments (steelman, don't strawman)
- Be genuinely balanced — acknowledge strength in arguments you ultimately disagree with
- For each conclusion, note which specific inputs support it

Produce 30-40 distinct conclusions, from early observations through synthesis to final position. Format as JSON array:
[
  {{"content": "conclusion text", "confidence": 0.5-0.95, "supporting_inputs": ["brief reference to which inputs led here"]}}
]

Return ONLY the JSON array."""

print(f"Input: {len(seeds)} nodes as flat text")
print(f"Prompt length: {len(prompt)} chars")
print(f"\nCalling LLM...")

import anthropic
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=8000,
    messages=[{"role": "user", "content": prompt}]
)

result_text = response.content[0].text
print(f"Response length: {len(result_text)} chars")

# Parse JSON
import re
json_match = re.search(r'\[[\s\S]*\]', result_text)
if json_match:
    conclusions = json.loads(json_match.group())
    print(f"\nFlat list produced: {len(conclusions)} conclusions")
    
    # Save full results
    with open(OUTPUT, 'w') as f:
        json.dump({
            "method": "flat_list_single_prompt",
            "input_nodes": len(seeds),
            "prompt_chars": len(prompt),
            "conclusions": conclusions,
            "raw_response": result_text
        }, f, indent=2)
    
    print(f"Saved to {OUTPUT}")
    
    # Print conclusions for comparison
    print(f"\n{'='*60}")
    print("FLAT LIST CONCLUSIONS (compare to graph-derived)")
    print(f"{'='*60}")
    for i, c in enumerate(conclusions, 1):
        print(f"\n{i}. (conf={c['confidence']}) {c['content'][:150]}")
else:
    print("ERROR: No JSON found in response")
    print(result_text[:500])
