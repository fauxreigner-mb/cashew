#!/usr/bin/env python3
"""
Periodic declassification of vault:private nodes.

Nodes extracted from sessions are tagged vault:private by default.
This script reviews aged nodes and declassifies ones that are safe
to surface in group channels.

Usage:
    python3 scripts/declassify.py                    # dry run
    python3 scripts/declassify.py --execute           # actually declassify
    python3 scripts/declassify.py --min-age-days 14   # custom age threshold
    python3 scripts/declassify.py --stats             # show classification stats
"""

import os
import sys
import sqlite3
import argparse
import json
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "graph.db")

# Content patterns that should NEVER be declassified
PERMANENT_PRIVATE_PATTERNS = [
    # Financial
    "salary", "compensation", "bank", "account number", "credit card",
    "net worth", "debt", "loan", "mortgage", "investment portfolio",
    # Personal relationships - specifics
    "narcissistic", "divorce", "affair", "therapy session",
    # IP / trade secrets
    "provisional patent", "pre-launch IP", "competitive advantage",
    "proprietary", "trade secret",
    # Credentials
    "password", "api key", "token", "secret key", "credential",
    # Health specifics  
    "diagnosis", "medication", "prescription",
]

# Node types that are generally safe to declassify
SAFE_TYPES = {"fact", "observation", "insight", "decision", "belief", "meta"}

# Node types that need extra scrutiny
SENSITIVE_TYPES = {"core_memory", "derived", "cross_link"}


def get_candidates(db_path: str, min_age_days: int = 7) -> list:
    """Find vault:private nodes older than min_age_days."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, content, node_type, domain, tags, timestamp
        FROM thought_nodes
        WHERE tags LIKE '%vault:private%'
        AND (decayed IS NULL OR decayed = 0)
        AND timestamp < datetime('now', ?)
        ORDER BY timestamp ASC
    """, (f"-{min_age_days} days",))
    
    candidates = []
    for row in cursor.fetchall():
        candidates.append({
            "id": row[0],
            "content": row[1],
            "node_type": row[2],
            "domain": row[3],
            "tags": row[4],
            "timestamp": row[5],
        })
    
    conn.close()
    return candidates


def is_permanently_private(content: str) -> bool:
    """Check if content matches patterns that should never be declassified."""
    content_lower = content.lower()
    return any(pattern in content_lower for pattern in PERMANENT_PRIVATE_PATTERNS)


def classify_node(node: dict) -> str:
    """
    Hard-rule classification only. Returns:
    - 'permanent_private' for content that must NEVER be declassified
    - 'needs_review' for everything else (requires LLM reasoning)
    
    The actual declassify/keep_private decision is made by the LLM caller,
    not by this script. This function only filters out the obvious stuff.
    """
    content = node["content"]
    
    if is_permanently_private(content):
        return "permanent_private"
    
    return "needs_review"


def declassify_nodes(db_path: str, node_ids: list) -> int:
    """Remove vault:private tag from specified nodes."""
    if not node_ids:
        return 0
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    count = 0
    for node_id in node_ids:
        cursor.execute("SELECT tags FROM thought_nodes WHERE id = ?", (node_id,))
        row = cursor.fetchone()
        if not row:
            continue
        
        tags = row[0] or ""
        # Remove vault:private tag
        new_tags = ",".join(t.strip() for t in tags.split(",") if t.strip() != "vault:private")
        
        cursor.execute("UPDATE thought_nodes SET tags = ? WHERE id = ?", (new_tags, node_id))
        count += 1
    
    conn.commit()
    conn.close()
    return count


def get_stats(db_path: str) -> dict:
    """Get classification statistics."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM thought_nodes WHERE tags LIKE '%vault:private%' AND (decayed IS NULL OR decayed = 0)")
    total_private = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM thought_nodes WHERE (tags IS NULL OR tags NOT LIKE '%vault:private%') AND (decayed IS NULL OR decayed = 0)")
    total_public = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM thought_nodes WHERE (decayed IS NULL OR decayed = 0)")
    total_active = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_active": total_active,
        "private": total_private,
        "public": total_public,
        "private_pct": round(total_private / max(1, total_active) * 100, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="Declassify aged vault:private nodes")
    parser.add_argument("--db", default=DB_PATH, help="Database path")
    parser.add_argument("--min-age-days", type=int, default=7, help="Minimum age in days before considering declassification (default: 7)")
    parser.add_argument("--stats", action="store_true", help="Show classification stats and exit")
    parser.add_argument("--candidates", action="store_true", help="Output candidates for LLM review as JSON")
    parser.add_argument("--declassify-ids", nargs="+", metavar="NODE_ID", help="Declassify specific node IDs (after LLM review)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    if args.stats:
        stats = get_stats(args.db)
        if args.json:
            print(json.dumps(stats))
        else:
            print(f"📊 Classification Stats:")
            print(f"   Total active nodes: {stats['total_active']}")
            print(f"   Private (vault:private): {stats['private']} ({stats['private_pct']}%)")
            print(f"   Public: {stats['public']}")
        return 0
    
    if args.declassify_ids:
        count = declassify_nodes(args.db, args.declassify_ids)
        if args.json:
            print(json.dumps({"declassified": count}))
        else:
            print(f"🔓 Declassified {count} nodes.")
        return 0
    
    candidates = get_candidates(args.db, args.min_age_days)
    
    if not candidates:
        if args.json or args.candidates:
            print(json.dumps({"candidates": [], "permanent_private": 0}))
        else:
            print(f"No vault:private nodes older than {args.min_age_days} days found.")
        return 0
    
    # Split: hard-rule permanent vs needs LLM review
    needs_review = []
    permanent = []
    
    for node in candidates:
        classification = classify_node(node)
        if classification == "permanent_private":
            permanent.append(node)
        else:
            needs_review.append(node)
    
    if args.candidates:
        # Output for LLM consumption — just the reviewable nodes
        output = {
            "candidates": [
                {
                    "id": n["id"],
                    "content": n["content"][:200],
                    "node_type": n["node_type"],
                    "domain": n["domain"],
                    "timestamp": n["timestamp"],
                }
                for n in needs_review
            ],
            "permanent_private": len(permanent),
            "total_reviewed": len(candidates),
        }
        print(json.dumps(output, indent=2))
        return 0
    
    if args.json:
        print(json.dumps({
            "candidates": len(candidates),
            "needs_review": len(needs_review),
            "permanent_private": len(permanent),
        }))
        return 0
    
    print(f"📋 Declassification Review (nodes older than {args.min_age_days} days)")
    print(f"   Candidates: {len(candidates)}")
    print(f"   🔍 Need LLM review: {len(needs_review)}")
    print(f"   🚫 Permanently private: {len(permanent)}")
    print()
    print("Run with --candidates to get reviewable nodes as JSON.")
    print("After LLM review, run with --declassify-ids <id1> <id2> ... to apply.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
