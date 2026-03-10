# cashew — Design Document

## 1. Problem Statement

Current AI systems (and humans) produce conclusions but discard the derivation path. Chain-of-thought exists during inference but is ephemeral. Knowledge graphs store what is known but not how it was derived. No existing system combines:

1. **Persistent derivation chains** — every thought linked to its parents
2. **Emergent self-organization** — hierarchical structure from organic clustering  
3. **Auditability as a first-class operation** — "why do I believe X?" is a query, not introspection

### Core Question
If you store reasoning with its full derivation path, can a system meaningfully audit and self-correct its own beliefs while exhibiting emergent insights?

### Prior Art
| System | What it does | Gap |
|--------|-------------|-----|
| Knowledge Graphs | Stores entities + relationships | No derivation tracking |
| Chain-of-thought (LLMs) | Step-by-step reasoning | Ephemeral — gone after response |
| RAG (LlamaIndex etc.) | Retrieves context for generation | Flat memory, no graph structure |
| MemGPT | Persistent LLM memory | No derivation graph |
| Argument mapping (Kialo) | Structured debate trees | Human-curated, not emergent |
| Causal inference (DAGitty) | Cause-effect models | Statistical modeling, not reasoning |

### What's New
cashew combines persistent derivation, hierarchical retrieval, and emergent clustering in a single system that exhibits power law properties and genuine insight generation through isolated cluster reasoning.

---

## 2. Architecture

```
┌──────────┐    ┌──────────────────┐    ┌─────────────┐
│  Input    │───▶│  Thought Engine   │───▶│  Graph Store │
│  (query,  │    │                    │    │  (SQLite +   │
│   seed,   │    │  1. Hierarchical   │    │   embeddings)│
│   context)│    │     retrieval      │    │              │
└──────────┘    │  2. Generate new   │    │  Nodes:      │
                │     thought via LLM│    │  - id         │
                │  3. Create node    │    │  - content    │
                │  4. Link to parents│    │  - embedding  │
                │  5. Store + index  │    │  - timestamp  │
                └──────────────────┘    │  - metadata   │
                                         │              │
                                         │  Edges:      │
                                         │  - parent_id  │
                                         │  - child_id   │
                                         │  - weight     │
                                         │  - relation   │
                                         └─────────────┘
                                                │
┌───────────┬───────────────┬─────────────────┴───────────────┐
│           │               │                                 │
│  Traversal │    Sleep      │    Clustering                  │
│  Engine    │   Protocol    │    Engine                      │
│            │               │                                │
│  why(node) │   - Decay     │   - Hotspot trees              │
│  how(A→B)  │   - Promote   │   - Emergent clusters          │
│  audit()   │   - Cross-link│   - Domain separation          │
│  roots()   │   - Dream gen │   - Power law emergence        │
└───────────┘   - GC cycles  │                                │
                └───────────┘ └────────────────────────────────┘
```

---

## 3. Data Model

### Current Schema (SQLite)
```sql
CREATE TABLE thought_nodes (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    node_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    confidence REAL NOT NULL,
    metadata TEXT,
    source_file TEXT,
    decayed INTEGER DEFAULT 0,
    last_updated TEXT DEFAULT NULL,
    last_accessed TEXT,
    access_count INTEGER DEFAULT 0,
    domain TEXT
);

CREATE TABLE derivation_edges (
    parent_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    weight REAL NOT NULL,
    reasoning TEXT,
    FOREIGN KEY (parent_id) REFERENCES thought_nodes(id),
    FOREIGN KEY (child_id) REFERENCES thought_nodes(id),
    PRIMARY KEY (parent_id, child_id, relation)
);

CREATE TABLE embeddings (
    node_id TEXT PRIMARY KEY,
    vector BLOB NOT NULL,
    model TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (node_id) REFERENCES thought_nodes(id)
);
```

### Node Types (Current Implementation)
- **human_thought** — Direct human input, high confidence
- **system_generated** — LLM-generated hypotheses, moderate confidence
- **hotspot** — Cluster summary nodes for hierarchical retrieval
- **question** — Explicit questions identified by the system
- **pattern** — Identified recurring structures
- **experience** — Personal experiences and observations
- **principle** — Foundational reasoning rules
- **insight** — Derived understanding from think cycles
- **decision** — Specific choices and their reasoning
- **goal** — Objectives and targets
- **memory** — Specific recollections
- **reflection** — Self-analysis and meta-cognition
- **observation** — Data points and facts
- **hypothesis** — Testable predictions
- **conclusion** — Final derived outcomes

---

## 4. Core Operations

### 4.1 Context Retrieval
**Hierarchical DFS through hotspot trees (O(log N) instead of O(N))**
```python
def generate_context(hints: list[str]) -> list[ThoughtNode]:
    # 1. Embed hints, find root hotspots
    # 2. DFS through hotspot tree following semantic similarity  
    # 3. Collect detail nodes from relevant clusters
    # 4. Return ranked results
```

### 4.2 Knowledge Extraction  
**Convert conversations to graph nodes with derivation links**
```python
def extract(input_text: str) -> list[ThoughtNode]:
    # 1. Parse input for extractable knowledge
    # 2. Find derivation parents via similarity
    # 3. Generate new nodes with confidence scores
    # 4. Create edges with reasoning explanations
```

### 4.3 Think Cycles
**Isolated cluster reasoning for genuine insight generation**
```python
def think() -> list[ThoughtNode]:
    # 1. Identify cohesive clusters
    # 2. Feed ONLY cluster nodes to LLM
    # 3. Generate hypotheses about cluster patterns
    # 4. Create system_generated nodes with cluster parents
```

### 4.4 Traversal Operations
```python
def why(node_id: str) -> list[ThoughtNode]:
    # Walk parent edges recursively to seed nodes
    
def how(node_a: str, node_b: str) -> list[ThoughtNode]:
    # Find shortest path between nodes
    
def audit() -> AuditReport:
    # Find cycles, orphans, weak derivations
    
def roots() -> list[ThoughtNode]:
    # Return all nodes with no parents
```

### 4.5 Sleep Protocol
**Self-maintenance through decay, promotion, cross-linking, and dream generation**
```python
def run_sleep_cycle():
    # 1. Decay unused nodes (reduce confidence)
    # 2. Promote valuable nodes (increase confidence)  
    # 3. Cross-link similar clusters
    # 4. Generate dream nodes for new connections
    # 5. Garbage collect low-value nodes
```

---

## 5. Experiments

### Experiment 1: Isolated Cluster Reasoning ✅ ACHIEVED
**Goal:** Demonstrate genuine insight generation through think cycles

**Method:** 
1. Select a cohesive cluster (e.g., "silence" cluster with 17 nodes)
2. Feed ONLY those nodes to LLM with think cycle prompt
3. Generate hypotheses about cluster patterns
4. Human validation of insights

**Results:** 4/4 hypotheses on silence cluster confirmed as genuine insights not explicitly stated in source nodes. Example: *"Silence is TWO patterns, not one — strategic silence works, avoidant silence doesn't."*

**Scaled to:** 7 clusters, 21 hypotheses generated across domains

### Experiment 2: General Domain Architecture 🔜 NEXT
**Goal:** Test domain-agnostic knowledge organization

**Method:**
1. Seed abstract knowledge domains (science, philosophy, engineering)
2. Run think cycles and sleep consolidation
3. Observe emergent clustering and hierarchy formation
4. Test cross-domain insight generation

**Success criteria:**
- Emergent hierarchical organization without hardcoded categories
- Cross-domain think cycles produce novel insights
- Sleep cycles create meaningful inter-domain connections

### Experiment 3: Capable Agent Framework (Future)
**Goal:** Graph as agency engine for AI agents

**Method:**
1. Seed graph with engineer's reasoning patterns and principles
2. Agent makes decisions by querying graph for relevant principles
3. All decisions traceable back to human seed via why() traversal
4. Human audits and corrects graph, agent improves

**Success criteria:**
- Agent cognitive style matches human reasoning approach
- Every decision has auditable derivation chain
- Graph corrections improve agent performance

---

## 6. Technical Decisions

### Platform: Agent-native on OpenClaw
- No standalone app. cashew lives inside OpenClaw's agent infrastructure
- Main agent orchestrates, sub-agents handle think cycles
- Claude Sonnet for reasoning, local embeddings for retrieval

### Storage: SQLite + Local Embeddings
- Single file, no server, portable
- FTS5 for text search, blob columns for embeddings
- Handles 1000+ nodes efficiently
- sentence-transformers for local embedding generation

### Language: Python
- NetworkX for in-memory graph operations
- pytest for comprehensive testing
- Type hints and docstrings throughout

### Visualization: vis.js Dashboard
- Real-time graph rendering with search and filtering
- Color-coded by node type (human vs system-generated)
- Deployable to Cloudflare Pages

---

## 7. Key Insights

### Power Law Properties
The graph exhibits natural power law behavior:
- **Preferential attachment** — New thoughts connect to high-connectivity hubs
- **Self-organized criticality** — Sleep cycles restructure accumulated knowledge
- **Fractal structure** — Same patterns at all scales
- **Emergent hierarchy** — Organization from simple connection rules

### Hierarchical Retrieval Scaling
Traditional RAG systems use flat vector search (O(N) comparisons). cashew uses hierarchical DFS through hotspot trees, achieving O(log N) retrieval while preserving semantic relationships.

### Think Cycles Generate Genuine Insight
Isolated cluster reasoning produces derivations the human recognizes as true but hadn't explicitly stated. This is structural insight generation, not summarization.

---

## 8. Success Criteria

### Phase 1: Personal Thought Graph ✅ ACHIEVED
1. ✅ **why(node) produces non-obvious derivation chains** — tracing reveals unplanned connections
2. ✅ **audit() catches real circular reasoning** — cycle detection works
3. ✅ **Emergent clusters form** — thoughts self-organize without explicit categorization  
4. ✅ **Think cycles produce genuine insight** — isolation reasoning confirmed by human
5. ✅ **Graph exhibits power law properties** — preferential attachment via sleep cycles
6. ✅ **Hierarchical retrieval scales** — O(log N) context generation via hotspot trees

### Phase 2: Domain-General Architecture 🔜 NEXT  
1. [ ] Abstract knowledge domains produce emergent organization
2. [ ] Cross-domain think cycles generate novel insights
3. [ ] Sleep cycles create meaningful inter-domain connections
4. [ ] System scales to multiple knowledge areas
5. [ ] Domain separation maintains while enabling cross-pollination

### Phase 3: Agency Engine (Future)
1. [ ] Graph drives agent decisions through principle retrieval
2. [ ] Every action traces back to human seed via why()
3. [ ] Agent cognitive style matches human reasoning approach
4. [ ] Human corrections improve graph and agent performance

### The prototype fails if:
- Think cycles only summarize existing content (expensive logger)
- Graph is flat/random (compare against random graph metrics)
- Forced edges reduce orphans but don't reflect genuine relationships
- System can't scale beyond personal knowledge domains

---

## 9. File Structure (Current)

```
cashew/
├── README.md                 # Project overview and usage
├── DESIGN.md                 # This document  
├── core/                     # Core modules
│   ├── clustering.py         # Emergent cluster detection
│   ├── complete_clustering.py # Hierarchical hotspot system
│   ├── complete_retrieval.py # O(log N) DFS retrieval
│   ├── context.py           # Context generation
│   ├── embeddings.py        # Local embedding management
│   ├── retrieval.py         # Traditional retrieval
│   ├── session.py           # Session lifecycle
│   ├── sleep.py             # Sleep cycle protocols
│   ├── think_cycle.py       # Isolated cluster reasoning
│   └── traversal.py         # Graph traversal (why/how/audit)
├── scripts/                  # CLI tools and utilities
│   ├── cashew_context.py    # Main CLI interface
│   ├── export_dashboard.py  # Dashboard generation
│   ├── graph_health.py      # Graph analysis
│   └── deploy-dashboard.sh  # Cloudflare deployment
├── tests/                    # Comprehensive test suite
│   ├── test_context.py      # Context generation tests
│   ├── test_retrieval.py    # Retrieval algorithm tests
│   ├── test_sleep.py        # Sleep cycle tests
│   └── test_traversal.py    # Traversal operation tests
├── dashboard/                # Visualization assets
│   ├── index.html           # Dashboard interface
│   └── data/               # Graph exports
├── data/                    # Database and exports
│   └── graph.db            # SQLite database (1142 nodes, 3147 edges)
└── docs/                    # Documentation
    └── architecture.md      # Technical architecture details
```

---

## 10. Sleep Protocol Details

### Purpose
Connect isolated thought chains, deduplicate, garbage collect, and consolidate — mirrors neural sleep consolidation.

### Operations (run periodically after N thoughts):

1. **Cross-linking:** Semantic similarity across clusters. Deduplicate (>0.9 similarity), cross-link (0.7-0.9), or flag contradictions.
2. **Dream generation:** Create new nodes about discovered connections between clusters. Parents span multiple clusters → forest becomes graph.
3. **Garbage collection:** Random selection, scored by composite fitness. Below threshold → decay. Random GC introduces noise forcing rederivation through novel paths.
4. **Core memory promotion:** Re-rank nodes, promote/demote based on network metrics (connectivity, access patterns, confidence).
5. **Logging:** Every operation logged for analysis and auditability.

### Self-similarity Across Scales:
| Scale | Consolidation | Pruning | Cross-linking |
|-------|--------------|---------|---------------|
| Neural | Memory replay | Synaptic pruning | New associations |
| Thought graph | Core memory promotion | GC decay | Dream nodes |
| Knowledge systems | Canon formation | Forgotten concepts | Cross-domain insights |

---

## 11. Engineering Principles

### Testing Philosophy
"I don't want an unfalsifiable system." — Every behavior gets a test.

**Test categories:**
1. **Unit tests** — Every function, every edge case
   - Graph store: CRUD, dedup, edge creation, integrity
   - Traversal: why() correctness, audit() cycle detection
   - Sleep: fitness scoring, decay behavior, promotion logic

2. **Behavioral tests** — Does the system do what we claim?
   - Derivation: why(A) includes correct parent chain
   - Contradiction detection: audit() flags conflicts
   - Sleep preservation: high-value nodes survive GC
   - Cross-linking: independent clusters connect

3. **Emergence tests** — Can we measure emergent properties?  
   - Power laws: degree distribution vs random graphs
   - Clustering: modularity scores vs random networks
   - Insight generation: think cycle novelty assessment

4. **Regression tests** — Don't break what works
   - Every bug gets test before fix
   - Reproducible experiments (seeded randomness)

**Framework:** pytest, green tests on every commit, no merge without tests

### Code Standards
- Type hints everywhere
- Docstrings on public functions  
- No magic numbers — constants named and documented
- Git hygiene: specific `git add`, one feature per PR

---

## 12. Current State (March 2026)

### Graph Statistics
- **1,142 thought nodes** across 15 distinct types
- **3,147 derivation edges** with reasoning annotations
- **Domain separation** — multiple knowledge areas in one graph
- **23/23 tests passing** — comprehensive coverage

### Proven Capabilities  
1. **Think cycles produce genuine insight** — 4/4 insights confirmed on silence cluster
2. **Hierarchical retrieval scales** — O(log N) context generation via hotspot trees  
3. **Sleep cycles work at scale** — problems at 34 nodes resolved at 600+
4. **Power law emergence** — preferential attachment without tuning
5. **Dashboard visualization** — deployed to Cloudflare Pages

### In Production Use
- Daily context retrieval for agent sessions
- Knowledge extraction from conversations  
- Think cycles for insight generation
- Sleep cycles for graph maintenance

---

## 13. MVP Definition ("Done") ✅ ACHIEVED

**Done = You look at the graph and it surprises you.**

Concrete achievements (March 8, 2026):
1. ✅ Graph seeded — memory files parsed into nodes/edges
2. ✅ Sleep runs — cross-links, dedup, GC all function correctly  
3. ✅ Think cycles work — genuine insights confirmed by human
4. ✅ Visual dashboard — vis.js with search, deployed via cloudflared
5. ✅ Traversal operations — why(node) produces full derivation chains
6. ✅ Test coverage — 23/23 tests passing

### Key Learning: Foundation Model AS Reasoning Engine
Don't build Python reasoning modules — the LLM reasoning over structured graph context IS the think cycle. Only tooling needed is graph plumbing (retrieve nodes, insert results).

### Philosophy Confirmed  
- **Orphans are unsolved problems, not bugs** — Don't force connections
- **Honest attempts > curve fitting** — Genuine relationships matter more than graph density
- **Emergent structure validates the architecture** — Power laws and clustering prove self-organization