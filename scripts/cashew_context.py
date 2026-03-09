#!/usr/bin/env python3
"""
Cashew Context CLI - Manual testing interface for OpenClaw integration
"""

import sys
import argparse
import json
import os
import time
import logging
from pathlib import Path

logger = logging.getLogger("cashew")

# Add the parent directory to the path so we can import cashew modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.openclaw import generate_session_context, extract_from_conversation, run_think_cycle, run_tension_detection
from integration.complete_integration import (
    generate_complete_session_context, extract_from_conversation_complete,
    run_complete_think_cycle, run_complete_sleep_cycle, migrate_to_complete_coverage,
    explain_complete_system, get_complete_system_stats
)
from core.hotspots import create_hotspot, update_hotspot, list_hotspots, get_hotspot


def cmd_context(args):
    """Generate context for current session"""
    hints = args.hints if args.hints else None
    print(f"🔍 Generating context with hints: {hints}")
    print()
    
    t0 = time.time()
    context = generate_session_context(args.db, hints)
    elapsed = time.time() - t0
    
    if context:
        print(context)
        print()
        print("✅ Context generated successfully")
        if args.debug:
            print(f"⏱  Elapsed: {elapsed:.2f}s", file=sys.stderr)
            print(f"📏 Context length: {len(context)} chars", file=sys.stderr)
    else:
        print("❌ No context generated (empty result)")


def cmd_extract(args):
    """Extract from a conversation file"""
    if not args.input:
        print("❌ Error: --input file required for extract command")
        return 1
    
    if not os.path.exists(args.input):
        print(f"❌ Error: File not found: {args.input}")
        return 1
    
    print(f"📖 Reading conversation from: {args.input}")
    
    with open(args.input, 'r') as f:
        conversation_text = f.read()
    
    if not conversation_text.strip():
        print("❌ Error: Empty conversation file")
        return 1
    
    print(f"📝 Conversation length: {len(conversation_text)} characters")
    print("🧠 Extracting insights...")
    print()
    
    t0 = time.time()
    result = extract_from_conversation(args.db, conversation_text, args.session_id)
    elapsed = time.time() - t0
    
    print(json.dumps(result, indent=2))
    
    if result.get("success"):
        print()
        print("✅ Extraction completed successfully")
        print(f"   New nodes: {result['new_nodes']}")
        print(f"   New edges: {result['new_edges']}")
        if args.debug:
            print(f"⏱  Elapsed: {elapsed:.2f}s", file=sys.stderr)
    else:
        print()
        print(f"❌ Extraction failed")
        if args.debug:
            print(f"⏱  Elapsed: {elapsed:.2f}s", file=sys.stderr)
            print(f"🔍 Result: {json.dumps(result, indent=2)}", file=sys.stderr)
        return 1


def cmd_think(args):
    """Run a think cycle"""
    domain = args.domain if args.domain else None
    mode = getattr(args, 'mode', 'general')
    
    if mode == "tension":
        print("⚡ Running tension detection...")
        if domain:
            print(f"   Focused on domain: {domain}")
        print()
        t0 = time.time()
        result = run_tension_detection(args.db, domain)
        elapsed = time.time() - t0
    else:
        if domain:
            print(f"🤔 Running think cycle focused on domain: {domain}")
        else:
            print("🤔 Running general think cycle...")
        print()
        t0 = time.time()
        result = run_think_cycle(args.db, domain)
        elapsed = time.time() - t0
    
    print(json.dumps(result, indent=2))
    
    if result.get("success"):
        print()
        print("✅ Think cycle completed successfully")
        print(f"   Cluster: {result['cluster_topic']}")
        print(f"   New insights: {result['new_nodes']}")
        print(f"   New connections: {result['new_edges']}")
        if args.debug:
            print(f"⏱  Elapsed: {elapsed:.2f}s", file=sys.stderr)
    else:
        print()
        print("❌ Think cycle failed")
        if args.debug:
            print(f"⏱  Elapsed: {elapsed:.2f}s", file=sys.stderr)
        return 1


def cmd_stats(args):
    """Show graph statistics"""
    try:
        import sqlite3
        
        conn = sqlite3.connect(args.db)
        cursor = conn.cursor()
        
        # Count nodes by type
        cursor.execute("""
            SELECT node_type, COUNT(*) 
            FROM thought_nodes 
            WHERE decayed IS NULL OR decayed = 0
            GROUP BY node_type 
            ORDER BY COUNT(*) DESC
        """)
        node_types = cursor.fetchall()
        
        # Count total nodes
        cursor.execute("SELECT COUNT(*) FROM thought_nodes WHERE decayed IS NULL OR decayed = 0")
        total_nodes = cursor.fetchone()[0]
        
        # Count edges
        cursor.execute("SELECT COUNT(*) FROM derivation_edges")
        total_edges = cursor.fetchone()[0]
        
        # Count embeddings
        cursor.execute("""
            SELECT COUNT(*) FROM embeddings e
            JOIN thought_nodes tn ON e.node_id = tn.id
            WHERE tn.decayed IS NULL OR tn.decayed = 0
        """)
        embedded_nodes = cursor.fetchone()[0]
        
        # Recent activity
        cursor.execute("""
            SELECT COUNT(*) FROM thought_nodes 
            WHERE (decayed IS NULL OR decayed = 0)
            AND timestamp > datetime('now', '-7 days')
        """)
        recent_nodes = cursor.fetchone()[0]
        
        conn.close()
        
        print("📊 Cashew Graph Statistics")
        print("=" * 40)
        print(f"Total nodes: {total_nodes}")
        print(f"Total edges: {total_edges}")
        print(f"Embedded nodes: {embedded_nodes}")
        print(f"Recent nodes (7 days): {recent_nodes}")
        print(f"Embedding coverage: {embedded_nodes/total_nodes*100:.1f}%" if total_nodes > 0 else "Embedding coverage: 0%")
        print()
        print("Node types:")
        for node_type, count in node_types:
            print(f"  {node_type}: {count}")
        
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        return 1


def cmd_sleep(args):
    """Run the sleep/consolidation protocol."""
    import time as _time
    start = _time.time()
    print("😴 Running sleep protocol...")
    
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
        from core.sleep import SleepProtocol
        
        protocol = SleepProtocol(args.db)
        result = protocol.run_sleep_cycle()
        elapsed = _time.time() - start
        
        print(f"\n✅ Sleep protocol completed in {elapsed:.1f}s")
        if isinstance(result, dict):
            for k, v in result.items():
                print(f"  {k}: {v}")
        else:
            print(f"  Result: {result}")
        
    except Exception as e:
        print(f"❌ Sleep protocol error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def cmd_complete_context(args):
    """Generate context with complete coverage retrieval"""
    hints = args.hints if args.hints else None
    method = getattr(args, 'method', 'dfs')
    print(f"🔍 Generating complete context with method: {method}")
    if hints:
        print(f"   Hints: {hints}")
    print()
    
    t0 = time.time()
    try:
        context = generate_complete_session_context(
            args.db, hints, args.domain, method, args.top_k
        )
        elapsed = time.time() - t0
        
        if context:
            print(context)
            print()
            print("✅ Complete context generated successfully")
            if args.debug:
                print(f"⏱  Elapsed: {elapsed:.2f}s", file=sys.stderr)
                print(f"📏 Context length: {len(context)} chars", file=sys.stderr)
        else:
            print("❌ No context generated (empty result)")
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def cmd_complete_extract(args):
    """Extract with placement-aware assignment"""
    if not args.input:
        print("❌ Error: --input file required for extract command")
        return 1
    
    if not os.path.exists(args.input):
        print(f"❌ Error: File not found: {args.input}")
        return 1
    
    print(f"📖 Reading conversation from: {args.input}")
    
    with open(args.input, 'r') as f:
        conversation_text = f.read()
    
    if not conversation_text.strip():
        print("❌ Error: Empty conversation file")
        return 1
    
    print(f"📝 Conversation length: {len(conversation_text)} characters")
    print("🧠 Extracting with placement-aware assignment...")
    print()
    
    t0 = time.time()
    try:
        result = extract_from_conversation_complete(
            args.db, conversation_text, args.session_id or "complete_session"
        )
        elapsed = time.time() - t0
        
        print(json.dumps(result, indent=2))
        
        if result.get("success"):
            print()
            print("✅ Placement-aware extraction completed successfully")
            print(f"   New nodes: {len(result.get('new_nodes', []))}")
            print(f"   Placements: {len(result.get('placements', []))}")
            if args.debug:
                print(f"⏱  Elapsed: {elapsed:.2f}s", file=sys.stderr)
        else:
            print()
            print(f"❌ Extraction failed: {result.get('error', 'Unknown error')}")
            return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def cmd_complete_think(args):
    """Run think cycle with placement-aware assignment"""
    domain = args.domain if args.domain else None
    
    print("⚡ Running complete think cycle with placement...")
    if domain:
        print(f"   Focused on domain: {domain}")
    print()
    
    t0 = time.time()
    try:
        result = run_complete_think_cycle(args.db, domain)
        elapsed = time.time() - t0
        
        print(json.dumps(result, indent=2))
        
        if result.get("success"):
            print()
            print("✅ Complete think cycle completed successfully")
            print(f"   New nodes: {len(result.get('new_nodes', []))}")
            if args.debug:
                print(f"⏱  Elapsed: {elapsed:.2f}s", file=sys.stderr)
        else:
            print()
            print(f"❌ Think cycle failed: {result.get('error', 'Unknown error')}")
            return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def cmd_complete_sleep(args):
    """Run complete sleep cycle with hierarchy evolution"""
    enable_evolution = not getattr(args, 'no_evolution', False)
    
    print("😴 Running complete sleep cycle...")
    print(f"   Hierarchy evolution: {'enabled' if enable_evolution else 'disabled'}")
    print()
    
    t0 = time.time()
    try:
        result = run_complete_sleep_cycle(args.db, enable_evolution)
        elapsed = time.time() - t0
        
        print(json.dumps(result, indent=2))
        
        print()
        print(f"✅ Complete sleep cycle completed in {elapsed:.1f}s")
        print(f"   Total actions: {result.get('total_actions', 0)}")
        print(f"   Coverage: {result.get('coverage_verification', {}).get('coverage_percentage', 'Unknown')}%")
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def cmd_migrate(args):
    """Migrate to complete coverage system"""
    dry_run = getattr(args, 'dry_run', False)
    
    print(f"🔄 Migrating to complete coverage system (dry_run={dry_run})...")
    print()
    
    t0 = time.time()
    try:
        result = migrate_to_complete_coverage(args.db, dry_run)
        elapsed = time.time() - t0
        
        print(json.dumps(result, indent=2))
        
        print()
        if result.get("migration_needed"):
            print(f"✅ Migration completed in {elapsed:.1f}s")
            print(f"   Final coverage: {result.get('final_coverage', {}).get('coverage_percentage', 'Unknown')}%")
        else:
            print("✅ No migration needed - system already has complete coverage")
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def cmd_explain(args):
    """Explain the complete coverage system"""
    query = getattr(args, 'query', 'test query for explanation')
    
    print("📊 Explaining complete coverage system...")
    print()
    
    t0 = time.time()
    try:
        result = explain_complete_system(args.db, query)
        elapsed = time.time() - t0
        
        print(json.dumps(result, indent=2))
        
        print()
        print(f"✅ System explanation completed in {elapsed:.1f}s")
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def cmd_system_stats(args):
    """Show complete system statistics"""
    print("📈 Gathering complete system statistics...")
    print()
    
    t0 = time.time()
    try:
        result = get_complete_system_stats(args.db)
        elapsed = time.time() - t0
        
        print(json.dumps(result, indent=2))
        
        print()
        print(f"✅ Statistics gathered in {elapsed:.1f}s")
        
        # Show summary
        coverage = result.get("coverage", {})
        hierarchy = result.get("hierarchy_statistics", {})
        health = result.get("system_health", {})
        
        print("\n📊 SUMMARY:")
        print(f"   Coverage: {coverage.get('coverage_percentage', 'Unknown')}%")
        print(f"   Total nodes: {result.get('node_statistics', {}).get('total_nodes', 'Unknown')}")
        print(f"   Total hotspots: {hierarchy.get('total_hotspots', 'Unknown')}")
        print(f"   Hierarchy depth: {hierarchy.get('hierarchy_depth', 'Unknown')}")
        print(f"   Complete coverage: {health.get('has_complete_coverage', 'Unknown')}")
        print(f"   Emergent domains: {health.get('emergent_domains', 'Unknown')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def cmd_hotspot(args):
    """Manage hotspot nodes"""
    action = args.hotspot_action
    
    if action == "create":
        if not args.content:
            print("❌ --content required for create")
            return 1
        
        # Parse file pointers from --files "label:path,label:path"
        file_pointers = {}
        if args.files:
            for pair in args.files.split(","):
                if ":" in pair:
                    label, path = pair.split(":", 1)
                    file_pointers[label.strip()] = path.strip()
        
        # Parse cluster IDs
        cluster_ids = args.cluster.split(",") if args.cluster else []
        tags = args.tags.split(",") if args.tags else []
        
        hotspot_id = create_hotspot(
            db_path=args.db,
            content=args.content,
            status=args.status or "active",
            file_pointers=file_pointers,
            cluster_node_ids=cluster_ids,
            domain=args.domain or "bunny",
            tags=tags
        )
        print(f"✅ Created hotspot: {hotspot_id}")
        print(f"   Content: {args.content[:80]}...")
        print(f"   Status: {args.status or 'active'}")
        print(f"   Files: {file_pointers}")
        print(f"   Cluster: {len(cluster_ids)} nodes")
    
    elif action == "update":
        if not args.id:
            print("❌ --id required for update")
            return 1
        
        file_pointers = None
        if args.files:
            file_pointers = {}
            for pair in args.files.split(","):
                if ":" in pair:
                    label, path = pair.split(":", 1)
                    file_pointers[label.strip()] = path.strip()
        
        add_ids = args.cluster.split(",") if args.cluster else None
        
        success = update_hotspot(
            db_path=args.db,
            hotspot_id=args.id,
            content=args.content,
            status=args.status,
            file_pointers=file_pointers,
            add_cluster_ids=add_ids
        )
        if success:
            print(f"✅ Updated hotspot: {args.id}")
        else:
            print(f"❌ Failed to update hotspot: {args.id}")
            return 1
    
    elif action == "list":
        hotspots = list_hotspots(args.db, args.domain)
        if not hotspots:
            print("No hotspots found.")
            return
        
        print(f"📍 {len(hotspots)} Hotspot(s)")
        print("=" * 60)
        for h in hotspots:
            print(f"\n🔵 [{h['id']}] {h['content'][:80]}")
            print(f"   Status: {h['status']} | Domain: {h['domain']} | Cluster: {h['cluster_size']} nodes")
            if h['file_pointers']:
                for label, path in h['file_pointers'].items():
                    print(f"   📄 {label}: {path}")
            if h['tags']:
                print(f"   🏷  Tags: {', '.join(h['tags'])}")
            print(f"   Updated: {h['last_updated']}")
    
    elif action == "show":
        if not args.id:
            print("❌ --id required for show")
            return 1
        
        h = get_hotspot(args.db, args.id)
        if not h:
            print(f"❌ Hotspot not found: {args.id}")
            return 1
        
        print(f"📍 Hotspot: {h['id']}")
        print(f"   Content: {h['content']}")
        print(f"   Status: {h['status']}")
        print(f"   Domain: {h['domain']}")
        print(f"   Updated: {h['last_updated']}")
        if h['file_pointers']:
            print(f"   Files:")
            for label, path in h['file_pointers'].items():
                print(f"     📄 {label}: {path}")
        if h['tags']:
            print(f"   Tags: {', '.join(h['tags'])}")
        if h['cluster']:
            print(f"   Cluster ({len(h['cluster'])} nodes):")
            for node in h['cluster']:
                print(f"     - [{node['type']}] {node['content'][:60]}...")


def main():
    parser = argparse.ArgumentParser(description="Cashew Context CLI")
    parser.add_argument("--db", default="/Users/bunny/.openclaw/workspace/cashew/data/graph.db", 
                       help="Database path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--debug", action="store_true", help="Debug output (timing, diagnostics to stderr)")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Context command
    context_parser = subparsers.add_parser("context", help="Generate context for current session")
    context_parser.add_argument("--hints", nargs="*", 
                                help="Topic hints (e.g., 'work promotion manager')")
    context_parser.set_defaults(func=cmd_context)
    
    # Extract command  
    extract_parser = subparsers.add_parser("extract", help="Extract from a conversation file")
    extract_parser.add_argument("--input", required=True, help="Input conversation file")
    extract_parser.add_argument("--session-id", help="Optional session ID")
    extract_parser.set_defaults(func=cmd_extract)
    
    # Think command
    think_parser = subparsers.add_parser("think", help="Run a think cycle")
    think_parser.add_argument("--domain", help="Focus domain (e.g., 'career')")
    think_parser.add_argument("--mode", choices=["general", "tension"], default="general",
                             help="Think mode: general (default) or tension (find contradictions)")
    think_parser.set_defaults(func=cmd_think)
    
    # Sleep command
    sleep_parser = subparsers.add_parser("sleep", help="Run the sleep/consolidation protocol")
    sleep_parser.set_defaults(func=cmd_sleep)
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show graph stats")
    stats_parser.set_defaults(func=cmd_stats)
    
    # Hotspot command
    hotspot_parser = subparsers.add_parser("hotspot", help="Manage hotspot nodes")
    hotspot_parser.add_argument("hotspot_action", choices=["create", "update", "list", "show"],
                                help="Hotspot action")
    hotspot_parser.add_argument("--content", help="Hotspot summary content")
    hotspot_parser.add_argument("--status", help="Status string")
    hotspot_parser.add_argument("--files", help="File pointers as 'label:path,label:path'")
    hotspot_parser.add_argument("--cluster", help="Comma-separated cluster node IDs")
    hotspot_parser.add_argument("--tags", help="Comma-separated search tags")
    hotspot_parser.add_argument("--domain", help="Domain (raj/bunny)")
    hotspot_parser.add_argument("--id", help="Hotspot ID (for update/show)")
    hotspot_parser.set_defaults(func=cmd_hotspot)
    
    # === COMPLETE COVERAGE SYSTEM COMMANDS ===
    
    # Complete context command
    complete_context_parser = subparsers.add_parser("complete-context", help="Generate context with complete coverage retrieval")
    complete_context_parser.add_argument("hints", nargs="*", help="Topic hints for context generation")
    complete_context_parser.add_argument("--method", choices=["dfs", "hierarchical", "breadth_first"], 
                                        default="dfs", help="Retrieval method")
    complete_context_parser.add_argument("--top-k", type=int, default=5, help="Number of context items")
    complete_context_parser.add_argument("--domain", help="Optional domain filter")
    complete_context_parser.set_defaults(func=cmd_complete_context)
    
    # Complete extract command
    complete_extract_parser = subparsers.add_parser("complete-extract", help="Extract with placement-aware assignment")
    complete_extract_parser.add_argument("--input", required=True, help="Input conversation file")
    complete_extract_parser.add_argument("--session-id", help="Optional session ID")
    complete_extract_parser.set_defaults(func=cmd_complete_extract)
    
    # Complete think command
    complete_think_parser = subparsers.add_parser("complete-think", help="Run think cycle with placement-aware assignment")
    complete_think_parser.add_argument("--domain", help="Focus domain")
    complete_think_parser.set_defaults(func=cmd_complete_think)
    
    # Complete sleep command  
    complete_sleep_parser = subparsers.add_parser("complete-sleep", help="Run complete sleep cycle with hierarchy evolution")
    complete_sleep_parser.add_argument("--no-evolution", action="store_true", 
                                      help="Disable hierarchy evolution (merge/split/promote/reclassify)")
    complete_sleep_parser.set_defaults(func=cmd_complete_sleep)
    
    # Migration command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate to complete coverage system")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    migrate_parser.set_defaults(func=cmd_migrate)
    
    # Explain command
    explain_parser = subparsers.add_parser("explain", help="Explain the complete coverage system")
    explain_parser.add_argument("--query", default="test query", help="Test query for demonstration")
    explain_parser.set_defaults(func=cmd_explain)
    
    # System stats command
    system_stats_parser = subparsers.add_parser("system-stats", help="Show complete system statistics")
    system_stats_parser.set_defaults(func=cmd_system_stats)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s: %(message)s")
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)
    
    if not os.path.exists(args.db):
        print(f"❌ Error: Database not found: {args.db}")
        return 1
    
    if args.debug:
        db_size = os.path.getsize(args.db)
        print(f"🗄  DB: {args.db} ({db_size/1024:.1f} KB)", file=sys.stderr)
        print(f"🔧 Command: {args.command}", file=sys.stderr)
    
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())