# CLAUDE.md — Cashew Developer Guide

Cashew is a thought-graph memory engine for AI agents. It stores knowledge as nodes in a SQLite graph, connects them with typed edges, clusters them into hierarchical hotspots, and retrieves relevant context via hybrid embedding + graph traversal.

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
- **`derivation_edges`** — Relationships (parent_id, child_id, relation, weight, confidence)
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
- **Edge relations** — Free-text but common ones: `summarizes`, `relates_to`, `contradicts`, `derived_from`, `evolved_to`
- **Hotspot cluster_node_ids** — JSON array of node IDs stored as TEXT
- **Embeddings** — 384-dimensional numpy arrays stored as BLOBs

## Important Rules

- **Never delete nodes** — set `decayed=1` instead. The graph is append-mostly.
- **Always embed new nodes** — every node in `thought_nodes` must have a corresponding row in `embeddings`.
- **Confidence gates** — think cycle outputs below 0.75 confidence get discarded, not stored.
- **Domain assignment** — every node must have a domain. Use `config.get_user_domain()` and `config.get_ai_domain()`. Never hardcode domain strings.
- **No hardcoded paths** — use `config.get_db_path()` or accept `--db` CLI arg.
- **Hotspot integrity** — when modifying cluster membership, update both the hotspot's `cluster_node_ids` AND the `summarizes` edges.
- **Backward compatibility** — old databases may have 'raj'/'bunny' as domain names. The config system maps these automatically. Don't break this.

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
