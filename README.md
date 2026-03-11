# 🥜 cashew — Self-Organizing Thought Graph Engine

A persistent, hierarchical memory system that gives AI agents auditable reasoning and emergent insights. Thoughts are stored as nodes, connected by derivation, and self-maintained through sleep cycles.

## What Is This?

**The brain metaphor:**
- **Graph = long-term memory** (persistent, structured, searchable)
- **LLM = reasoning engine** (intelligence, derivation, pattern recognition)  
- **Context window = working memory** (session-scoped, ephemeral)

cashew stores every thought as a node in a graph, connected to its derivation parents. The system exhibits emergent clustering, power law connectivity, and genuine insight generation through isolated cluster reasoning.

## Key Features

- **1,142 nodes, 3,147 edges** — Hierarchical knowledge graph with 15 distinct node types
- **O(log N) DFS retrieval** — Not flat vector search, but hierarchical hotspot trees
- **Emergent clustering** — No hardcoded categories; hierarchy forms organically from thought patterns
- **Sleep cycles** — Decay unused nodes, promote valuable ones, cross-link, generate dreams
- **Domain separation** — Multiple knowledge domains in one graph
- **Session lifecycle** — Context retrieval on start, extraction on end
- **SQLite + local embeddings** — Zero cloud infrastructure
- **Dashboard visualization** — Live vis.js graph with search and filtering

## What We've Proven

### ✅ Think cycles produce genuine insight
Isolated cluster reasoning generates derivations the human hadn't stated but recognizes as true. Not summaries — actual forward predictions and structural patterns.

**Example:** A silence cluster (17 nodes) produced: *"Silence is TWO patterns, not one — strategic silence works, avoidant silence doesn't."* This insight wasn't in ANY of the 17 source nodes. The system found it structurally.

### ✅ The graph exhibits power law properties naturally  
Node connectivity follows a power law distribution — a few hubs with 40-60 edges, hundreds with 1-2. Preferential attachment emerges without tuning through sleep cycle consolidation.

### ✅ Retroactive self-understanding — the system infers what you never said
You talk about work stress on Tuesday, your relationship on Thursday, leaving religion on Saturday. You never say "these are connected." But sleep cycles find the structural similarity and cross-link them. Weeks later, the query "why do I overcommit?" returns a causal chain spanning all three conversations — people-pleasing → family system that punished authentic expression → approval-seeking as survival strategy. **You never stated the why. The system inferred it retroactively.**

This isn't memory. It's understanding. The graph proposes an interpretation, the human validates or rejects it — either way, they come out with clearer self-knowledge. Validation reinforces the node. Rejection forces you to articulate what *is* true, and that correction gets extracted. Both paths produce insight.

No causal reasoning engine. No why-chain algorithm. Just cosine similarity + derivation edges + sleep cycle cross-linking + an LLM that threads the narrative at query time. The infrastructure is simple. The emergent behavior is not.

### ✅ Hierarchical retrieval scales
DFS through hotspot trees replaces flat search. Context retrieval is O(log N) comparisons instead of O(N) vector similarity.

### ✅ Self-maintenance works at scale
Sleep protocols (decay, promotion, cross-linking, dream generation) function correctly across 1000+ nodes. Early garbage collection issues resolved at scale.

## Architecture

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────┐
│   Query     │───▶│  Thought Engine   │───▶│ Graph Store │
│ (extract,   │    │                   │    │ (SQLite +   │
│  context,   │    │  1. Hierarchical  │    │ embeddings) │
│  think)     │    │     retrieval     │    │             │
└─────────────┘    │  2. LLM reasoning │    │ Nodes:      │
                   │  3. Derivation    │    │ - content   │
                   │     linking       │    │ - metadata  │
                   │  4. Graph update  │    │ - confidence│
                   │  5. Sleep cycles  │    │             │
                   └──────────────────┘    │ Edges:      │
                                           │ - derivation│
                                           │ - reasoning │
                                           │ - weights   │
                                           └─────────────┘
```

## Usage

### Command-Line Interface

```bash
# Generate context for current conversation
python3 scripts/cashew_context.py context --hints "topic keywords"

# Extract knowledge from a conversation
python3 scripts/cashew_context.py extract --input conversation.md

# Run a think cycle (generate insights from clusters)  
python3 scripts/cashew_context.py think

# Run sleep cycle (decay, promote, consolidate)
python3 scripts/cashew_context.py sleep

# Get graph statistics
python3 scripts/cashew_context.py stats

# Complete coverage retrieval (advanced)
python3 scripts/cashew_context.py complete-context --hints "keywords"
```

### Dashboard

View the live graph visualization:

```bash
cd dashboard && python3 -m http.server 8787
# Open http://localhost:8787
```

Or deploy to Cloudflare Pages:
```bash
./scripts/deploy-dashboard.sh
```

### As a Python package

```bash
pip install git+https://github.com/jugaad-lab/cashew.git

cashew init                                    # Bootstrap empty graph
cashew migrate-files --dir ./my-notes/         # Import existing knowledge
cashew context --hints "what am I working on"  # Query the brain
cashew think                                   # Generate new insights
cashew sleep                                   # Consolidate and maintain
cashew stats                                   # Graph overview
```

## The Dual-Growth Loop

1. **Human conversations → nodes** (human-sourced, high confidence)
2. **System think cycles → hypotheses** (machine-sourced, 0.5-0.7 confidence) 
3. **Human feedback → edge corrections** (ground truth)
4. **Sleep consolidation → graph evolution** (decay/promote/cross-link)

The graph grows from both ends: 🧠 Human thoughts (blue/purple/gold/green) and 🤖 System-generated (orange with dashed borders).

## Current State

- **Production-ready** — Used daily as the primary memory system for an AI agent
- **117 tests passing** — Comprehensive test suite, zero failures
- **768KB on disk** — Smaller than a photo, contains a mind's worth of reasoning
- **Zero cloud dependencies** — Runs entirely local on SQLite + sentence transformers

## Key Insight: Power Laws

The same mathematical principles governing earthquakes, forest fires, and income distribution also govern how minds organize. The graph exhibits:

- **Preferential attachment** — New thoughts connect to high-connectivity hubs naturally
- **Self-organized criticality** — Sleep cycles are controlled forest fires that restructure accumulated knowledge  
- **Fractal structure** — Zoom into any cluster, see the same hierarchical patterns
- **Emergent behavior** — Complex organization from simple rules

## Philosophy

- **Orphans are unsolved problems, not bugs.** Don't force connections; let honest gaps remain visible.
- **Unproven ≠ disproven.** Keep hypotheses until evidence decides.
- **Design until the next question requires building.** Then build minimally.
- **Foundation models ARE reasoning engines.** Don't over-engineer what GPT already does well.
- **The fruits of being ambitious:** You might not reach the goal, but you'll get somewhere remarkable.

## Tech Stack

- **Core:** Python + SQLite + NetworkX for graph operations
- **Embeddings:** Local sentence transformers (no cloud dependencies)  
- **Intelligence:** Claude via OpenClaw sub-agents for think cycles
- **Visualization:** vis.js dashboard with real-time updates
- **Testing:** pytest with comprehensive module coverage
- **Deployment:** Cloudflare Pages for dashboard sharing

## Origin Story

Built in a weekend (March 2026). Inspired by a Veritasium video on power laws watched months earlier — the realization that the same mathematics governing earthquakes and forest fires could govern how a mind organizes itself.

Named after *"Aunty, do cats eat cashews?"* — the question that started a lifetime of asking why. The best tools come from the simplest curiosity.

## What's Next

- **Open source launch** — MIT licensed, pip installable, ready for the community
- **MCP server** — Plug into Claude Desktop, Cursor, or any MCP-compatible agent
- **Multi-agent cognition** — Multiple agents sharing one graph with provenance tracking
- **Benchmarks** — Formal evaluation against mem0, Zep, MemGPT on retrieval quality and scalability

**The competitive landscape:** mem0 remembers what you told it. Zep summarizes your conversations. cashew learns how you think — and can show you why.

The graph is the memory. The model is the mind. The combination is something new.