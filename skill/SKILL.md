---
name: cashew
description: Persistent thought-graph memory for AI agents. Use cashew CLI to query context before answering substantive questions, extract knowledge during conversations, and run think cycles during idle time. Triggers on session start, knowledge-worthy conversations, heartbeats, and any question about prior context or "what do you know about X".
---

# Cashew — Thought Graph Memory

Cashew gives you a persistent brain across sessions. Without it, you forget everything on compaction or restart. With it, you remember decisions, patterns, relationships, and project status.

## Setup

Requires `cashew-core` Python package:
```bash
pip install cashew-core  # or: pip install git+https://github.com/jugaad-lab/cashew.git
cashew init              # creates ./data/graph.db
```

Set `CASHEW_DB` env var to point to your database, or use `--db` flag on any command.

## Core Protocol

### 1. Session Start — ALWAYS Query First

Before answering any substantive question in a new session, query the brain:

```bash
cashew context --hints "<keywords from the conversation>"
```

If unsure what keywords to use, start with the user's name or topic. This returns:
- **Graph overview** — shape of what you know (domains, clusters, active areas)
- **Recent activity** — what happened in the last few sessions
- **Relevant context** — nodes matching your hints

Do NOT answer questions about prior work, decisions, people, or preferences without querying first.

### 2. During Conversation — Extract Proactively

When any of these happen, extract immediately — don't wait:
- A project status changes
- A decision is made (architectural, personal, strategic)
- A new insight or pattern surfaces
- The user corrects your understanding
- A new person or relationship is established

Write key points to a temp file, then extract:
```bash
cat > /tmp/cashew-extract.md << 'EOF'
- Project X pivoted from approach A to approach B because of Y
- User prefers Z over W for communication
- New decision: shipping weekly instead of monthly
EOF
cashew extract --input /tmp/cashew-extract.md
```

**What to extract:**
- Pattern-level insights, not raw data ("tends to procrastinate when overwhelmed" not "didn't reply Tuesday")
- Corrections and pivots (supersede old understanding)
- Cross-domain connections (when a pattern in one area mirrors another)
- Meta-observations (how the user thinks, decides, works)

**What NOT to extract:**
- Transient chat logistics ("ok sounds good", "let me check")
- Information already in the graph (query first to check)
- Raw data without interpretation

### 3. Idle Time — Think Cycles

During quiet heartbeats or when nothing needs attention, run a think cycle (1-2x/day max):

```bash
cashew think
```

This consolidates knowledge, detects tensions (contradictory beliefs), and evolves the hierarchy. Log what you find in your daily notes.

### 4. Sleep Cycles (Optional)

For deeper consolidation — clustering, hotspot generation, hierarchy evolution:

```bash
cashew sleep
```

Run sparingly (1x/day or less). This is expensive but produces high-quality organization.

## CLI Reference

| Command | Purpose |
|---------|---------|
| `cashew context --hints "..."` | Query brain for relevant context |
| `cashew extract --input file.md` | Extract knowledge from text |
| `cashew think` | Run a think cycle (consolidation) |
| `cashew sleep` | Full sleep cycle (clustering + hierarchy) |
| `cashew stats` | Show graph statistics |
| `cashew init` | Initialize new database |
| `cashew migrate-files --dir path/` | Import markdown files |

## Key Principles

- **Brain is source of truth** for status, decisions, relationships. Files are blob storage for raw content.
- **One context query per session** is usually enough. Don't over-query.
- **Extract sparingly** — only genuinely new knowledge. Quality over quantity.
- **Don't dump raw brain output to user** — it informs YOU, you inform the user naturally.
- **If brain returns nothing useful**, re-query with better hints before falling back to files.

## Integration with Workspace Files

If you use daily memory files (e.g., `memory/YYYY-MM-DD.md`), they complement the brain:
- **Brain** = structured knowledge (what you know, patterns, decisions)
- **Daily files** = raw timeline (what happened when)
- Query brain for understanding, read files for chronological detail

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `CASHEW_DB` | Path to graph database | `./data/graph.db` |
| `KMP_DUPLICATE_LIB_OK` | Set to `TRUE` if you get MKL/OpenMP errors | unset |
