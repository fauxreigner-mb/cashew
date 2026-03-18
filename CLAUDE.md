# CLAUDE.md — Cashew Developer Guide

Cashew is a thought-graph memory engine for AI agents. It stores knowledge as nodes in a SQLite graph, connects them with typed edges, clusters them into hierarchical hotspots, and retrieves relevant context via hybrid embedding + graph traversal.

**IMPORTANT**: Cashew does NOT call LLMs directly. It is purely the BRAIN (storage + retrieval + structure). The PROCESSOR (LLM) is external and provided by the orchestrator (OpenClaw) via `model_fn` parameters. This allows cashew to be used by any system that can provide LLM access, without being coupled to specific API keys or providers.

## Architecture

```
scripts/cashew_context.py  — Main CLI entry point (context, extract, think, sleep, stats)
cashew_cli.py              — Secondary CLI (init, install-crons)
core/                      — Engine modules
integration/               — OpenClaw bridges
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `config.py` | YAML config loading with env var expansion. Global `config` singleton. |
| `embeddings.py` | Sentence-transformer embeddings (all-MiniLM-L6-v2). `embed_text()` is the key function. |
| `retrieval.py` | Hybrid retrieval: embedding similarity + DFS graph walk. `retrieve_dfs()` is the primary retrieval function. |
| `complete_retrieval.py` | Extended retrieval with reranking and domain filtering. |
| `context.py` | Composes retrieval results into formatted context strings for LLM consumption. |
| `placement_aware_extraction.py` | Extracts knowledge from text → nodes + edges. Uses LLM with heuristic fallback. |
| `think_cycle.py` | Autonomous reasoning: reads a cluster, proposes insights, commits above 0.75 confidence. |
| `sleep.py` | Deep consolidation: cross-linking, decay, hotspot maintenance, clustering. Runs daily. |
| `decay.py` | Prunes stale nodes (low access, low confidence, old). Sets `decayed=1`. |
| `clustering.py` | DBSCAN clustering on embeddings. Groups semantically similar nodes. |
| `complete_clustering.py` | Extended clustering with domain inference and hierarchy building. |
| `hotspots.py` | Hierarchical navigation nodes. A hotspot summarizes a cluster of nodes. |
| `hierarchy_evolution.py` | Evolves the hotspot hierarchy: merge, split, promote, reclassify. |
| `traversal.py` | Graph walk utilities (DFS, BFS, path finding). |
| `patterns.py` | Pattern detection across nodes (contradictions, evolutions, cycles). |
| `questions.py` | Detects open questions in conversations for tracking. |
| `session.py` | Session lifecycle management (start, end, extract). |
| `stats.py` | Graph statistics and health metrics. |
| `export.py` | Export graph data to JSON for dashboard visualization. |

### Integration

| Module | Purpose |
|--------|---------|
| `integration/openclaw.py` | OpenClaw agent lifecycle hooks. `get_ai_context()` and `get_user_context()` for domain-filtered retrieval. |
| `integration/complete_integration.py` | Full integration layer with health checks and diagnostics. |

## Database Schema

SQLite with 4 tables:

- **`thought_nodes`** — Knowledge nodes (id, content, node_type, domain, confidence, access_count, decayed, permanent)
- **`derivation_edges`** — Relationships (parent_id, child_id, weight, confidence)
- **`embeddings`** — Vector embeddings per node (node_id, vector as BLOB, model name)
- **`hotspots`** — Cluster summary nodes (id, content, status, cluster_node_ids as JSON)

### Key Columns

- `domain` — Classifies who the knowledge belongs to. Configurable via config.yaml (default: "user" and "ai").
- `node_type` — One of: fact, observation, insight, decision, belief, derived, meta, hotspot_summary
- `decayed` — 0 or 1. Decayed nodes are excluded from retrieval but kept in DB.
- `permanent` — 0 or 1. Permanent nodes are immune to decay.
- `confidence` — Float 0-1. Think cycle outputs are gated at 0.75.

## Configuration

`config.yaml` at project root. Key settings:
- `database.path` — SQLite DB location
- `domains.user` / `domains.ai` — Domain names (replaces old hardcoded values)
- `models.embedding.name` — Embedding model
- `models.llm.model` — LLM for extraction/thinking
- `performance.*` — Token budgets, thresholds, top-k

Environment variables override config: `${VAR:-default}` syntax supported in YAML.

## Conventions

- **Node IDs** — 12-char hex strings generated from content hash (`hashlib.sha256(content)[:12]`)
- **Timestamps** — ISO 8601 strings
- **Edges are untyped** — no `relation` column. Ablation testing proved typed edges don't improve retrieval. Edges are pure connections; semantics come from node content + embeddings.
- **Hotspot cluster_node_ids** — JSON array of node IDs stored as TEXT
- **Embeddings** — 384-dimensional numpy arrays stored as BLOBs

## External LLM Pattern

Cashew follows a strict separation of concerns:

- **Cashew (Brain)**: Stores, retrieves, clusters, and structures knowledge. Embeds nodes locally using sentence-transformers.
- **Orchestrator (Processor)**: Provides LLM access via `model_fn` parameters when calling cashew functions.

### Functions that accept model_fn:
- `extract_from_conversation(model_fn=None)` — Uses heuristic extraction if None
- `run_think_cycle(model_fn=None)` — Skips think cycles if None  
- `run_sleep_cycle(model_fn=None)` — Uses fallback hotspot summaries if None
- `run_clustering_cycle(model_fn=None)` — Creates text summaries only if provided

### CLI LLM Access:
The CLI auto-discovers a running OpenClaw gateway from `~/.openclaw/openclaw.json` and routes LLM calls through it via the `/v1/chat/completions` endpoint (OpenAI-compatible). This is **provider-agnostic** — works with whatever LLM the user configured in OpenClaw (Anthropic, OpenAI, local models, etc).

The `_build_model_fn()` function in `scripts/cashew_context.py` handles discovery. No API keys or provider-specific code needed.

### Never do in cashew:
- `import anthropic` or any LLM client library
- Store API keys or auth tokens
- Make direct API calls to LLM providers
- Create `Client()` objects

## Prompt Injection Pattern (Canonical)

**This is how brain context must be injected into LLM prompts.** All users should use this pattern — don't roll your own.

The function `generate_session_context(db_path, hints)` in `integration/openclaw.py` returns a **pre-formatted, ready-to-inject string**. The caller drops it into their system prompt as-is.

The output has three layers:
1. **Graph Overview** — total nodes, clusters, shape of knowledge
2. **Recent Activity** — last few sessions' worth of new nodes (recency signal)
3. **Relevant Context** — hint-driven semantic search results with domain labels

```
=== GRAPH OVERVIEW ===
Graph: 2124 nodes across 30 clusters.

=== RECENT ACTIVITY ===
1. [fact] Some recent fact... (03-18)

=== RELEVANT CONTEXT ===
1. [FACT] Relevant node content (Domain: user)
2. [DECISION] Another relevant node (Domain: ai)

=== END CONTEXT ===
```

**Rules:**
- Always use `cashew context --hints "..."` or `generate_session_context()` — never assemble prompts from raw node lists
- The output is framed as **background knowledge**, not search results. This changes how the LLM uses it.
- Hotspot summaries are included automatically when relevant nodes connect to them
- The caller should inject this into the system prompt, not the user message

## Important Rules

- **Never delete nodes** — set `decayed=1` instead. The graph is append-mostly.
- **Always embed new nodes** — every node in `thought_nodes` must have a corresponding row in `embeddings`.
- **Confidence gates** — think cycle outputs below 0.75 confidence get discarded, not stored.
- **Domain assignment** — every node must have a domain. Use `config.get_user_domain()` and `config.get_ai_domain()`. Never hardcode domain strings.
- **No hardcoded paths** — use `config.get_db_path()` or accept `--db` CLI arg.
- **Hotspot integrity** — when modifying cluster membership, update both the hotspot's `cluster_node_ids` AND the `summarizes` edges.
- **Backward compatibility** — old databases may have 'raj'/'bunny' as domain names. The config system maps these automatically. Don't break this.
- **No direct LLM calls** — Accept model_fn parameters, never create LLM clients internally.

## Testing

```bash
# Run existing tests
python -m pytest tests/

# Quick end-to-end test
python scripts/test_e2e.py

# Test in clean environment
mkdir /tmp/cashew-test && cd /tmp/cashew-test
python /path/to/cashew_cli.py init
python /path/to/scripts/cashew_context.py context --hints "test" --db data/graph.db
```

## Common Tasks

**Add a new core module:**
1. Create `core/your_module.py`
2. Import config with `from core.config import config, get_db_path`
3. Add CLI subcommand in `scripts/cashew_context.py` if user-facing
4. Update this file

**Modify the schema:**
1. Add migration script in `scripts/migrate_*.py`
2. Update the init schema in `cashew_cli.py` `cmd_init()`
3. Update this doc's schema section

**Add a CLI command:**
- User-facing graph operations → `scripts/cashew_context.py`
- Setup/admin commands → `cashew_cli.py`
