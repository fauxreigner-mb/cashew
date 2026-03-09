#!/usr/bin/env python3
"""Ablation Test: "Relational prompt" control — Testing Friend-C's critique that 
typed edges might just be "better prompting."

Same 34 input nodes, 12 iterative cycles, BUT with explicit relational framing:
"first identify which inputs support, contradict, or question each other, then
derive new conclusions from those relationships."

This gives the flat list the same relational FRAMING without any graph structure.
"""

import sqlite3, json, os, re, sys

DB = '/Users/bunny/.openclaw/workspace/cashew/data/experiment-clean-v2.db'
OUTPUT = '/Users/bunny/.openclaw/workspace/cashew/data/ablation-relational-prompt.json'

import anthropic

# Initialize client - will use ANTHROPIC_API_KEY env var or fail gracefully
try:
    client = anthropic.Anthropic()
except Exception as e:
    print(f"ERROR: Could not initialize Anthropic client: {e}")
    print("Make sure ANTHROPIC_API_KEY environment variable is set")
    exit(1)

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
    print("Preparing prompt...")
    sys.stdout.flush()
    
    prompt = f"""You are a reasoning engine with no preconceptions. Here is your input data:

{seeds_text}

{"PREVIOUS CONCLUSIONS FROM YOUR ANALYSIS:" + chr(10) + previous_text if previous_text else ""}

FOCUS FOR THIS ROUND: {focus}

CRITICAL INSTRUCTION: First, identify which inputs support, contradict, or question each other, then derive new conclusions from those relationships.

Specifically:
1. Look through the evidence and identify direct relationships: Which pieces support each other? Which contradict? Which raise questions about others?
2. Map out these relational patterns explicitly 
3. From these relationships, derive 3-4 NEW conclusions for this focus area

Follow evidence wherever it leads. Engage the strongest version of all arguments. Build on your previous conclusions where relevant.

Return ONLY a valid JSON array (no other text) with this exact format:
[
  {{
    "content": "your conclusion text here", 
    "confidence": 0.85, 
    "relations_identified": ["Evidence X supports Evidence Y because...", "Evidence A contradicts Evidence B because..."]
  }}
]

Do not include any markdown formatting, explanations, or text outside the JSON array."""

    try:
        print("Calling LLM...")
        sys.stdout.flush()
        response = call_llm(prompt)
        print("LLM response received")
        sys.stdout.flush()
        
        # Try to extract JSON, handle malformed responses better
        json_match = re.search(r'\[[\s\S]*?\]', response)
        if json_match:
            json_text = json_match.group()
            print(f"  Found JSON block: {len(json_text)} chars")
            try:
                thoughts = json.loads(json_text)
                print(f"  Successfully parsed {len(thoughts)} thoughts")
                for t in thoughts:
                    t['cycle'] = cycle_num
                    t['focus'] = focus
                    if 'relations_identified' not in t:
                        t['relations_identified'] = []
                    all_conclusions.append(t)
                    previous_text += f"- {t['content']}\n"
                    print(f"  (conf={t.get('confidence', 'N/A')}) {t['content'][:120]}...")
                    if t['relations_identified']:
                        print(f"    Relations: {len(t['relations_identified'])} identified")
            except json.JSONDecodeError as je:
                print(f"  JSON parse error: {je}")
                print(f"  Raw JSON: {json_text[:200]}...")
                # Try to manually parse if possible
                if 'content' in json_text and 'confidence' in json_text:
                    print("  Attempting manual extraction...")
                    # Create a fallback entry
                    fallback_conclusion = {
                        'content': f"Cycle {cycle_num} analysis incomplete due to JSON format issue",
                        'confidence': 0.5,
                        'cycle': cycle_num,
                        'focus': focus,
                        'relations_identified': [],
                        'raw_response': json_text[:500]
                    }
                    all_conclusions.append(fallback_conclusion)
                    previous_text += f"- {fallback_conclusion['content']}\n"
        else:
            print(f"  ERROR: No JSON array found in response")
            print(f"  Response preview: {response[:300]}...")
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.stdout.flush()

print(f"\n{'='*60}")
print(f"TOTAL: {len(all_conclusions)} conclusions across {len(cycle_focuses)} cycles")

# Count total relations identified
total_relations = sum(len(c.get('relations_identified', [])) for c in all_conclusions)
print(f"TOTAL RELATIONS IDENTIFIED: {total_relations}")

with open(OUTPUT, 'w') as f:
    json.dump({
        "method": "relational_prompt_iterative", 
        "cycles": len(cycle_focuses),
        "total_conclusions": len(all_conclusions),
        "total_relations_identified": total_relations,
        "conclusions": all_conclusions
    }, f, indent=2)

print(f"Saved to {OUTPUT}")