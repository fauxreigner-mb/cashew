#!/usr/bin/env python3
"""
Backfill tags on existing nodes using LLM inference.
Processes nodes in batches, asks the LLM to assign tags based on content + type.
"""

import sqlite3
import json
import sys
import os
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def ensure_tags_column(db_path: str):
    """Add tags column if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(thought_nodes)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'tags' not in columns:
        cursor.execute("ALTER TABLE thought_nodes ADD COLUMN tags TEXT DEFAULT NULL")
        conn.commit()
        logger.info("✅ Added tags column")
    conn.close()


def get_untagged_nodes(db_path: str, limit: int = 50) -> list:
    """Get nodes without tags."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, content, node_type, domain
        FROM thought_nodes
        WHERE (tags IS NULL OR tags = '')
        AND (decayed IS NULL OR decayed = 0)
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "content": r[1], "type": r[2], "domain": r[3]} for r in rows]


def build_tagging_prompt(nodes: list) -> str:
    """Build LLM prompt for batch tagging."""
    node_list = "\n".join(
        f'{i+1}. [{n["type"]}] (domain: {n["domain"]}) {n["content"][:200]}'
        for i, n in enumerate(nodes)
    )
    return f"""You are tagging nodes in a personal knowledge graph. For each node, assign 1-5 short, lowercase tags that describe its topic/category.

Good tags: career, family, engineering, philosophy, health, finance, identity, religion, relationships, project:cashew, meta, communication, habits, decision-making, self-awareness
Tags should be specific and reusable across nodes. Use project:name for project-specific knowledge.

Nodes to tag:
{node_list}

Respond with ONLY a JSON array of objects, one per node, in order:
[{{"id": 1, "tags": ["tag1", "tag2"]}}, ...]

Use the node number (1-indexed) as the id field."""


def apply_tags(db_path: str, nodes: list, tag_results: list):
    """Write tags to the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    applied = 0
    for result in tag_results:
        idx = result.get("id", 0) - 1
        if 0 <= idx < len(nodes):
            tags = result.get("tags", [])
            if tags and isinstance(tags, list):
                tags_str = ",".join(t.strip().lower() for t in tags if t.strip())
                cursor.execute("UPDATE thought_nodes SET tags = ? WHERE id = ?",
                             (tags_str, nodes[idx]["id"]))
                applied += 1
    conn.commit()
    conn.close()
    return applied


def backfill(db_path: str, model_fn, batch_size: int = 30, max_batches: int = 100):
    """Run the full backfill."""
    ensure_tags_column(db_path)
    
    total_applied = 0
    for batch_num in range(max_batches):
        nodes = get_untagged_nodes(db_path, limit=batch_size)
        if not nodes:
            logger.info(f"✅ All nodes tagged! Total: {total_applied}")
            return total_applied
        
        prompt = build_tagging_prompt(nodes)
        try:
            response = model_fn(prompt)
            # Parse JSON from response
            cleaned = response.strip()
            if '```' in cleaned:
                cleaned = cleaned.split('```')[1]
                if cleaned.startswith('json'):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            
            start = cleaned.find('[')
            end = cleaned.rfind(']')
            if start >= 0 and end > start:
                json_str = cleaned[start:end+1]
                # Fix common LLM JSON issues: trailing commas
                import re
                json_str = re.sub(r',\s*]', ']', json_str)
                json_str = re.sub(r',\s*}', '}', json_str)
                tag_results = json.loads(json_str)
                applied = apply_tags(db_path, nodes, tag_results)
                total_applied += applied
                logger.info(f"  Batch {batch_num+1}: tagged {applied}/{len(nodes)} nodes (total: {total_applied})")
            else:
                logger.warning(f"  Batch {batch_num+1}: no JSON found in response")
        except Exception as e:
            logger.warning(f"  Batch {batch_num+1}: error: {e}")
    
    logger.info(f"✅ Backfill complete. Tagged {total_applied} nodes across {max_batches} batches.")
    return total_applied


def main():
    parser = argparse.ArgumentParser(description="Backfill tags on existing nodes")
    parser.add_argument("--db", default="data/graph.db", help="Path to graph database")
    parser.add_argument("--batch-size", type=int, default=30, help="Nodes per LLM call")
    parser.add_argument("--max-batches", type=int, default=100, help="Maximum batches to run")
    parser.add_argument("--dry-run", action="store_true", help="Show untagged count only")
    args = parser.parse_args()
    
    db_path = args.db
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)
    
    ensure_tags_column(db_path)
    
    if args.dry_run:
        nodes = get_untagged_nodes(db_path, limit=1000000)
        logger.info(f"Untagged nodes: {len(nodes)}")
        return
    
    # Get model_fn from OpenClaw integration
    try:
        from integration.openclaw import get_model_fn
        model_fn = get_model_fn()
    except ImportError:
        # Fallback: try claude CLI
        import subprocess
        def model_fn(prompt):
            result = subprocess.run(
                ["claude", "-p", prompt, "--no-input"],
                capture_output=True, text=True, timeout=120
            )
            return result.stdout
    
    backfill(db_path, model_fn, args.batch_size, args.max_batches)


if __name__ == "__main__":
    main()
