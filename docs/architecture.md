# Cashew Hierarchical Retrieval Architecture

## Overview

Cashew implements a hierarchical retrieval system that uses recursive clustering to build a tree of hotspot nodes. Instead of flat search over 1,100+ nodes, the system performs a DFS (Depth-First Search) through a tree of hotspots where search complexity is O(log N).

## Core Principles

1. **Graph is source of truth** - The SQLite database holds the authoritative state of all knowledge
2. **Files are blob storage** - Markdown files contain raw content but no status information  
3. **Hotspots are the index** - Hierarchical summary nodes that act as routing points for efficient retrieval
4. **Emergent clustering** - No hardcoded categories; hierarchy forms organically from thought patterns

## Current System State

- **1,142 thought nodes** across 15 distinct node types
- **3,147 derivation edges** with reasoning annotations  
- **Hierarchical hotspot tree** with recursive DBSCAN clustering
- **O(log N) retrieval** via DFS traversal through hotspots
- **Domain separation** with cross-domain insight generation

## Hierarchical Retrieval System

### Hotspot Tree Structure

Hotspots form a tree where:
- **Root hotspots**: High-level domain summaries not children of other hotspots
- **Parent hotspots**: Summarize large clusters and point to sub-hotspots  
- **Leaf hotspots**: Summarize final clusters and point to detail nodes
- **Detail nodes**: Original knowledge nodes (thoughts, facts, decisions, experiences)

```
Root Hotspot: "Technical Work & Engineering"
├── Parent Hotspot: "System Architecture" 
│   ├── Leaf Hotspot: "Database Design"
│   │   ├── Detail: "SQLite schema for thought storage"
│   │   ├── Detail: "Embedding vector storage optimization"  
│   │   └── Detail: "Foreign key constraints for graph integrity"
│   └── Leaf Hotspot: "Graph Algorithms"
│       ├── Detail: "DFS traversal implementation"
│       └── Detail: "Recursive clustering with DBSCAN"
└── Parent Hotspot: "Development Process"
    └── Leaf Hotspot: "Testing Philosophy" 
        ├── Detail: "Every behavior gets a test"
        └── Detail: "Falsifiability as engineering principle"
```

### Recursive Cluster Detection

The clustering system (`core/clustering.py` and `core/complete_clustering.py`) uses recursive DBSCAN:

1. **Initial clustering**: Run DBSCAN on all nodes with `eps=0.35`, `min_samples=3`
2. **Size check**: If cluster > `max_cluster_size=15`, recursively split
3. **Tighter clustering**: Re-run DBSCAN on large clusters with `eps = eps * 0.7`  
4. **Hotspot creation**: Generate summaries for clusters via LLM reasoning
5. **Hierarchy building**: Connect parent→child with `summarizes` edges
6. **Recursion**: Repeat until all clusters ≤ max_cluster_size

### DFS Search Algorithm

The complete retrieval system (`core/complete_retrieval.py`) implements hierarchical DFS:

```python
def dfs_search_hierarchical(hints: List[str]) -> List[str]:
    """
    Hierarchical DFS through hotspot tree
    Returns: List of relevant node IDs ranked by relevance
    """
    # 1. Start at root hotspots (no incoming summarizes edges)
    root_hotspots = get_root_hotspots()
    
    # 2. Compute embedding similarity for current level
    current_level = root_hotspots
    
    # 3. DFS traversal
    for depth in range(MAX_DEPTH):
        # Rank current level hotspots by similarity to query
        scored_hotspots = [(id, similarity(hints_embedding, id)) 
                          for id in current_level]
        scored_hotspots.sort(reverse=True)
        
        # Take top candidates for exploration  
        best_hotspots = [id for id, score in scored_hotspots[:3] 
                        if score > threshold]
        
        # Check if we can go deeper
        next_level = []
        for hotspot_id in best_hotspots:
            children = get_child_hotspots(hotspot_id)
            if children:
                next_level.extend(children)
            else:
                # Leaf hotspot - collect its detail nodes
                return get_cluster_members(hotspot_id)
        
        if not next_level:
            break
        current_level = next_level
    
    return []
```

### Search Flow

1. **Root discovery**: Find all root-level hotspots (not summarized by others)
2. **Embedding comparison**: Compare query embedding against current level hotspots  
3. **Best match selection**: Pick top 2-3 most similar hotspots based on threshold
4. **Recursive descent**: For each selected hotspot:
   - Check if it has child hotspots
   - If yes: compare query against children, select best matches, recurse
   - If no (leaf): collect cluster members as final results
5. **Result ranking**: Return detail nodes ranked by similarity to original query

## Sleep Cycle Maintenance  

The sleep protocol (`core/sleep.py`) maintains hierarchical structure through:

### Clustering Phase
- Runs recursive clustering with configurable `max_cluster_size`
- Creates new parent/child hotspots for evolved clusters
- Preserves stable existing hotspot relationships
- Updates stale hotspots that drift from their cluster centroids

### Staleness Detection
- Computes cosine similarity between hotspot embedding and cluster centroid
- Marks hotspots as stale if similarity drops below threshold (typically 0.65)
- Regenerates stale hotspot summaries using LLM with current cluster content

### Dream Generation
- Identifies connections between previously isolated clusters
- Creates "dream nodes" that bridge different knowledge domains
- Parents of dream nodes span multiple clusters, converting forest to connected graph

## Scalability Analysis

| Node Count | Flat Search (O(N)) | Hierarchical DFS (O(log N)) | Speedup |
|------------|-------------------|---------------------------|---------|
| 100        | 100 comparisons   | ~7 comparisons           | 14x     |
| 1,000      | 1,000 comparisons | ~10 comparisons          | 100x    |
| 10,000     | 10,000 comparisons| ~15 comparisons          | 667x    |
| 100,000    | 100,000 comparisons| ~20 comparisons         | 5,000x  |

DFS search achieves logarithmic complexity by:
- Only comparing against 5-10 hotspots at each tree level
- Tree depth typically 3-4 levels for reasonable cluster sizes (max 15 nodes)
- Avoiding brute-force comparison against all detail nodes
- Pruning irrelevant branches early in traversal

## Implementation Details

### Core Modules

1. **`core/complete_clustering.py`**: Hierarchical clustering with recursive DBSCAN
2. **`core/complete_retrieval.py`**: DFS traversal through hotspot trees  
3. **`core/context.py`**: Context generation orchestration
4. **`core/session.py`**: Session lifecycle with hierarchical retrieval
5. **`core/sleep.py`**: Sleep cycles with cluster maintenance
6. **`core/traversal.py`**: Graph traversal operations (why/how/audit)

### Database Schema Utilization

Uses existing thought graph schema:
- **Hotspots**: `node_type='hotspot'`, content contains cluster summary
- **Summarization edges**: `relation='summarizes'` from hotspot to members  
- **Derivation edges**: `relation='derived_from'` for thought chains
- **Cross-links**: `relation='relates_to'` from sleep cycle bridge-building

### Command-Line Interface

```bash
# Complete coverage context (hierarchical DFS)
python3 scripts/cashew_context.py complete-context --hints "keywords"

# Legacy flat retrieval (for comparison)  
python3 scripts/cashew_context.py context --hints "keywords"

# System statistics including cluster metrics
python3 scripts/cashew_context.py system-stats

# Run complete sleep cycle with hierarchy evolution
python3 scripts/cashew_context.py complete-sleep
```

## Performance Characteristics

### Search Performance
- **Cold start**: ~150-300ms (embedding computation + DFS traversal)
- **Warm retrieval**: ~50-100ms (DFS traversal with cached embeddings)
- **Memory usage**: O(hotspots) not O(all_nodes), typically 10-15% of total nodes

### Tree Maintenance  
- **Sleep cycle frequency**: Every 10-20 new nodes or manual trigger
- **Clustering computation**: O(N²) for distance matrix, amortized over many searches
- **Hierarchy updates**: O(clusters) for staleness detection and regeneration
- **Cross-linking**: O(clusters²) for dream node generation

### Storage Efficiency
- **Database size**: ~768KB for 1,142 nodes (smaller than a photo)
- **Embedding vectors**: Local sentence-transformers, no API dependencies
- **Hotspot overhead**: ~5-10% additional nodes for indexing structure

## Testing & Validation

### Automated Test Coverage
The test suite (`tests/`) covers:
- **`test_retrieval.py`**: Hierarchical vs flat retrieval accuracy comparison
- **`test_clustering.py`**: Recursive DBSCAN cluster formation
- **`test_sleep.py`**: Sleep cycle maintenance operations
- **`test_traversal.py`**: Graph traversal correctness (why/how/audit)

### Quality Metrics
- **Recall@5**: Percentage of relevant results in top 5 hits
- **Query latency**: Response time for context generation  
- **Cluster coherence**: Intra-cluster similarity vs inter-cluster similarity
- **Tree balance**: Distribution of leaf cluster sizes

### Integration Testing
```bash
# Run complete system test
cd /Users/bunny/.openclaw/workspace/cashew
KMP_DUPLICATE_LIB_OK=TRUE python3 -m pytest tests/ -v

# Test retrieval quality
python3 scripts/cashew_context.py complete-context --hints "engineering work"
python3 scripts/cashew_context.py complete-context --hints "system design patterns"  
python3 scripts/cashew_context.py complete-context --hints "testing philosophy"
```

## Think Cycle Integration

### Isolated Cluster Reasoning
The think cycle system (`core/think_cycle.py`) uses hierarchical clustering for insight generation:

1. **Cluster isolation**: Select coherent clusters (leaf hotspots with 5-15 members)
2. **Context feed**: Send ONLY cluster members to LLM, no external context
3. **Pattern recognition**: LLM generates hypotheses about cluster patterns
4. **Derivation linking**: New insights link back to cluster members as parents
5. **Validation**: Human confirms insights as genuinely novel or derivative

### Think Cycle Results
- **Silence cluster (17 nodes)**: Generated insight "Silence is TWO patterns — strategic vs avoidant"  
- **4/4 insights confirmed** as genuinely novel by human validation
- **Structural emergence**: Insights not explicitly stated in any parent nodes

## Domain Separation

### Multi-Domain Architecture  
The graph supports multiple knowledge domains within a single database:

- **Domain field**: Each node tagged with domain (personal, technical, philosophical, etc.)
- **Cross-domain hotspots**: Hotspots can summarize nodes from multiple domains
- **Boundary spanning**: Think cycles can generate insights across domain boundaries  
- **Domain-specific retrieval**: Query hints can target specific domains when needed

### Domain Bridge Generation
Sleep cycles create cross-domain connections:
- **Dream nodes**: Generated insights that connect previously separate domains
- **Cross-pollination**: Technical insights applied to personal situations, etc.
- **Emergent interdisciplinarity**: No hardcoded cross-domain rules, emerges from content

## Future Enhancements

### Short-term (Next Release)
1. **Query routing optimization**: Skip irrelevant tree branches based on query analysis
2. **Incremental clustering**: Update tree structure without full re-clustering  
3. **Performance benchmarking**: Systematic comparison against flat search baselines
4. **Cluster rebalancing**: Automatic split/merge based on access patterns

### Medium-term  
1. **Temporal hotspots**: Time-aware clustering for recency-biased retrieval
2. **Confidence-weighted traversal**: Use node confidence scores in DFS path selection
3. **Adaptive thresholds**: Dynamic similarity thresholds based on query characteristics
4. **Multi-modal embeddings**: Support for images, audio in thought nodes

### Long-term
1. **Federated graphs**: Multiple agents sharing hierarchical knowledge structures
2. **Real-time collaboration**: Live multi-agent graph updates with conflict resolution
3. **Transfer learning**: Hotspot patterns from one domain applying to new domains
4. **Explainable retrieval**: Human-readable explanations for why specific results were selected

## Key Architectural Insights

### Emergent Hierarchy
Unlike traditional knowledge graphs with predetermined categories, cashew's hierarchy emerges from the data itself through recursive clustering. This creates more natural, semantically coherent groupings.

### Power Law Properties
The graph exhibits natural power law behavior with a few highly connected hub nodes and many leaf nodes. Hierarchical clustering preserves this structure while enabling efficient traversal.

### Think-Retrieve Symbiosis  
The think cycle system both consumes and produces hierarchical structure — isolated clusters generate insights that create new hierarchical relationships, creating a positive feedback loop for organization.

### Scalable Self-Organization
As the graph grows, the hierarchical structure automatically adapts through sleep cycles, maintaining logarithmic retrieval performance without manual reorganization.