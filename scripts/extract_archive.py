#!/usr/bin/env python3
"""Extract all conversations from Claude archive into cashew brain.

Usage:
    python3 scripts/extract_archive.py <conversations.json> [--dry-run] [--min-chars 200] [--skip-existing]
"""
import json
import sys
import os
import subprocess
import tempfile
import time
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", help="Path to conversations.json")
    parser.add_argument("--dry-run", action="store_true", help="Just show what would be extracted")
    parser.add_argument("--min-chars", type=int, default=200, help="Skip conversations with fewer human chars")
    parser.add_argument("--skip-existing", action="store_true", help="Skip conversations already in source_file tags")
    parser.add_argument("--start-from", type=int, default=0, help="Start from conversation index N")
    parser.add_argument("--max-chars", type=int, default=8000, help="Max chars per extraction batch")
    args = parser.parse_args()

    with open(args.archive) as f:
        data = json.load(f)

    # Sort by size (biggest first for max impact)
    convs = []
    for conv in data:
        name = conv.get("name", "untitled")
        msgs = conv.get("chat_messages", [])
        human_msgs = [m for m in msgs if m.get("sender") == "human"]
        assistant_msgs = [m for m in msgs if m.get("sender") == "assistant"]
        human_text = "\n".join(m.get("text", "") for m in human_msgs if m.get("text"))
        # Include assistant messages for context (but mark them)
        all_text_parts = []
        for m in msgs:
            sender = m.get("sender", "?")
            text = m.get("text", "")
            if not text:
                continue
            # Skip tool use/result blocks
            if sender not in ("human", "assistant"):
                continue
            prefix = "Raj:" if sender == "human" else "Claude:"
            all_text_parts.append(f"{prefix} {text}")
        
        full_text = "\n\n".join(all_text_parts)
        human_chars = len(human_text)
        convs.append((name, human_chars, full_text, conv.get("created_at", "")))

    convs.sort(key=lambda x: -x[1])

    # Filter
    eligible = [(i, name, chars, text, date) for i, (name, chars, text, date) in enumerate(convs) 
                if chars >= args.min_chars]

    print(f"Archive: {len(data)} conversations")
    print(f"Eligible (>={args.min_chars} human chars): {len(eligible)}")
    print(f"Starting from index: {args.start_from}")
    print()

    if args.dry_run:
        for i, name, chars, text, date in eligible:
            print(f"  [{i:2d}] {chars:>6} chars | {name} ({date[:10] if date else '?'})")
        print(f"\nTotal conversations to process: {len(eligible) - args.start_from}")
        return

    # Process
    cashew_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    total_nodes = 0
    total_edges = 0
    failures = []

    for idx, (i, name, chars, text, date) in enumerate(eligible):
        if idx < args.start_from:
            continue

        # Truncate very long conversations to max_chars for the extraction
        # Focus on human messages for very long convos
        if len(text) > args.max_chars:
            # Take first and last portions to capture arc of conversation
            half = args.max_chars // 2
            text = text[:half] + "\n\n[... middle of conversation truncated ...]\n\n" + text[-half:]

        safe_name = name.replace("/", "-").replace("\\", "-")[:50]
        print(f"\n[{idx+1}/{len(eligible)}] Processing: {name} ({chars} chars)")

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, prefix=f'cashew-archive-') as f:
            f.write(f"# Conversation: {name}\n")
            f.write(f"# Date: {date[:10] if date else 'unknown'}\n\n")
            f.write(text)
            tmp_path = f.name

        try:
            env = os.environ.copy()
            env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
            result = subprocess.run(
                [sys.executable, "scripts/cashew_context.py", "extract", "--input", tmp_path],
                capture_output=True, text=True, timeout=120,
                cwd=cashew_dir, env=env
            )

            if result.returncode == 0:
                # Parse output for stats
                output = result.stdout + result.stderr
                try:
                    # Find JSON in output
                    json_start = output.find('{\n  "success"')
                    if json_start == -1:
                        json_start = output.find('{"success"')
                    if json_start >= 0:
                        json_end = output.find('\n}', json_start) + 2
                        stats = json.loads(output[json_start:json_end])
                        nodes = stats.get("new_nodes", 0)
                        edges = stats.get("new_edges", 0)
                        total_nodes += nodes
                        total_edges += edges
                        print(f"  ✅ +{nodes} nodes, +{edges} edges")
                    else:
                        print(f"  ✅ (couldn't parse stats)")
                except (json.JSONDecodeError, ValueError):
                    print(f"  ✅ (couldn't parse stats)")
            else:
                print(f"  ❌ FAILED: {result.stderr[-200:]}")
                failures.append(name)
        except subprocess.TimeoutExpired:
            print(f"  ⏰ TIMEOUT")
            failures.append(name)
        finally:
            os.unlink(tmp_path)

        # Small delay to not hammer the API
        time.sleep(2)

    print(f"\n{'='*60}")
    print(f"EXTRACTION COMPLETE")
    print(f"  Conversations processed: {len(eligible) - args.start_from}")
    print(f"  New nodes: {total_nodes}")
    print(f"  New edges: {total_edges}")
    if failures:
        print(f"  Failures: {len(failures)}")
        for f in failures:
            print(f"    - {f}")

if __name__ == "__main__":
    main()
