#!/usr/bin/env python3
"""
Cashew Complete Retrieval Module
Pure tree traversal retrieval that works with 100% node coverage.
No more fallback pools needed since every node belongs to a cluster.
"""

import sqlite3
import json
import numpy as np
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict, deque
from dataclasses import dataclass

from core.embeddings import embed_text
from core.hotspots import HOTSPOT_TYPE, HOTSPOT_BOOST

@dataclass
class CompleteRetrievalResult:
    node_id: str
    content: str
    node_type: str
    domain: str
    score: float
    path: List[str]  # How this node was reached in the tree
    cluster_context: str  # Which hotspot contains this node
    
    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "content": self.content,
            "node_type": self.node_type,
            "domain": self.domain,
            "score": self.score,
            "path": self.path,
            "cluster_context": self.cluster_context
        }

def _get_connection(db_path: str) -> sqlite3.Connection:
    """Get database connection"""
    return sqlite3.connect(db_path)

def _load_node_details_complete(db_path: str, node_ids: List[str], domain_filter: Optional[str] = None) -> Dict[str, Dict]:
    """Load node details for multiple node IDs with domain filtering"""
    if not node_ids:
        return {}
    
    conn = _get_connection(db_path)
    cursor = conn.cursor()
    
    placeholders = ','.join(['?'] * len(node_ids))
    
    if domain_filter:
        cursor.execute(f"""
            SELECT id, content, node_type, COALESCE(metadata, '{{}}') as metadata, 
                   COALESCE(domain, 'unknown') as domain
            FROM thought_nodes 
            WHERE id IN ({placeholders})
            AND (decayed IS NULL OR decayed = 0)
            AND COALESCE(domain, 'unknown') = ?
        """, node_ids + [domain_filter])
    else:
        cursor.execute(f"""
            SELECT id, content, node_type, COALESCE(metadata, '{{}}') as metadata, 
                   COALESCE(domain, 'unknown') as domain
            FROM thought_nodes 
            WHERE id IN ({placeholders})
            AND (decayed IS NULL OR decayed = 0)
        """, node_ids)
    
    nodes = {}
    for node_id, content, node_type, metadata, domain in cursor.fetchall():
        try:
            metadata_dict = json.loads(metadata) if metadata else {}
        except (json.JSONDecodeError, TypeError):
            metadata_dict = {}
        
        nodes[node_id] = {
            "content": content,
            "node_type": node_type,
            "domain": domain,
            "metadata": metadata_dict
        }
    
    conn.close()
    return nodes

def _build_hotspot_hierarchy(db_path: str, domain_filter: Optional[str] = None) -> Tuple[Dict[str, List[str]], Dict[str, str], Dict[str, List[str]]]:
    """
    Build the complete hotspot hierarchy.
    
    Returns:
        Tuple of (children_map, parent_map, cluster_members_map)
        - children_map: parent_hotspot_id -> [child_hotspot_ids]
        - parent_map: child_hotspot_id -> parent_hotspot_id  
        - cluster_members_map: hotspot_id -> [member_node_ids]
    """
    conn = _get_connection(db_path)
    cursor = conn.cursor()
    
    # Get all hotspots
    if domain_filter:
        cursor.execute("""
            SELECT id FROM thought_nodes 
            WHERE node_type = ? AND (decayed IS NULL OR decayed = 0) 
            AND COALESCE(domain, 'unknown') = ?
        """, (HOTSPOT_TYPE, domain_filter))
    else:
        cursor.execute("""
            SELECT id FROM thought_nodes 
            WHERE node_type = ? AND (decayed IS NULL OR decayed = 0)
        """, (HOTSPOT_TYPE,))
    
    all_hotspot_ids = set(row[0] for row in cursor.fetchall())
    
    # Find hotspot-to-hotspot relationships (parent -> child hotspots)
    cursor.execute("""
        SELECT de.parent_id, de.child_id
        FROM derivation_edges de
        JOIN thought_nodes tn_parent ON de.parent_id = tn_parent.id
        JOIN thought_nodes tn_child ON de.child_id = tn_child.id
        WHERE tn_parent.node_type = ? AND tn_child.node_type = ?
        AND de.relation = 'summarizes'
        AND (tn_parent.decayed IS NULL OR tn_parent.decayed = 0)
        AND (tn_child.decayed IS NULL OR tn_child.decayed = 0)
    """, (HOTSPOT_TYPE, HOTSPOT_TYPE))
    
    children_map = defaultdict(list)  # parent -> [children]
    parent_map = {}  # child -> parent
    
    for parent_id, child_id in cursor.fetchall():
        if parent_id in all_hotspot_ids and child_id in all_hotspot_ids:
            children_map[parent_id].append(child_id)
            parent_map[child_id] = parent_id
    
    # Find hotspot-to-content relationships (hotspot -> member nodes)
    cursor.execute("""
        SELECT de.parent_id, de.child_id
        FROM derivation_edges de
        JOIN thought_nodes tn_parent ON de.parent_id = tn_parent.id
        JOIN thought_nodes tn_child ON de.child_id = tn_child.id
        WHERE tn_parent.node_type = ? AND tn_child.node_type != ?
        AND de.relation = 'summarizes'
        AND (tn_parent.decayed IS NULL OR tn_parent.decayed = 0)
        AND (tn_child.decayed IS NULL OR tn_child.decayed = 0)
    """, (HOTSPOT_TYPE, HOTSPOT_TYPE))
    
    cluster_members_map = defaultdict(list)  # hotspot -> [content_nodes]
    
    for hotspot_id, member_id in cursor.fetchall():
        if hotspot_id in all_hotspot_ids:
            cluster_members_map[hotspot_id].append(member_id)
    
    conn.close()
    return dict(children_map), parent_map, dict(cluster_members_map)

def _find_root_hotspots(parent_map: Dict[str, str], all_hotspots: Set[str]) -> List[str]:
    """Find hotspots that are not children of other hotspots (root level)"""
    return [hotspot_id for hotspot_id in all_hotspots if hotspot_id not in parent_map]

def _compute_hotspot_similarity(db_path: str, query: str, hotspot_ids: List[str], 
                              cluster_members_map: Dict[str, List[str]]) -> List[Tuple[str, float]]:
    """
    Compute embedding similarity between query and hotspots based on their CONTENT, not just their summary.
    
    For each hotspot, we score it by the BEST content similarity within its cluster,
    not just by the hotspot's own content similarity.
    
    Returns:
        List of (hotspot_id, similarity_score) tuples, sorted by score desc
    """
    if not hotspot_ids:
        return []
    
    try:
        # Get query embedding
        query_embedding = np.array(embed_text(query), dtype=np.float32)
        
        conn = _get_connection(db_path)
        cursor = conn.cursor()
        
        hotspot_similarities = []
        
        for hotspot_id in hotspot_ids:
            max_similarity = 0.0
            
            # Get cluster members for this hotspot
            cluster_members = cluster_members_map.get(hotspot_id, [])
            
            if cluster_members:
                # Score hotspot by its BEST cluster member similarity
                placeholders = ','.join(['?'] * len(cluster_members))
                cursor.execute(f"""
                    SELECT e.node_id, e.vector
                    FROM embeddings e
                    WHERE e.node_id IN ({placeholders})
                """, cluster_members)
                
                for member_id, vector_blob in cursor.fetchall():
                    try:
                        member_vector = np.frombuffer(vector_blob, dtype=np.float32)
                        
                        # Calculate cosine similarity
                        dot_product = np.dot(query_embedding, member_vector)
                        norm_query = np.linalg.norm(query_embedding)
                        norm_member = np.linalg.norm(member_vector)
                        
                        if norm_query > 0 and norm_member > 0:
                            similarity = float(dot_product / (norm_query * norm_member))
                            max_similarity = max(max_similarity, similarity)
                    
                    except Exception as e:
                        continue
            else:
                # Fallback to hotspot's own embedding if no cluster members
                cursor.execute("SELECT vector FROM embeddings WHERE node_id = ?", (hotspot_id,))
                result = cursor.fetchone()
                if result:
                    try:
                        hotspot_vector = np.frombuffer(result[0], dtype=np.float32)
                        
                        dot_product = np.dot(query_embedding, hotspot_vector)
                        norm_query = np.linalg.norm(query_embedding)
                        norm_hotspot = np.linalg.norm(hotspot_vector)
                        
                        if norm_query > 0 and norm_hotspot > 0:
                            max_similarity = float(dot_product / (norm_query * norm_hotspot))
                    except Exception:
                        max_similarity = 0.0
            
            hotspot_similarities.append((hotspot_id, max_similarity))
        
        conn.close()
        
        # Sort by similarity descending
        hotspot_similarities.sort(key=lambda x: x[1], reverse=True)
        return hotspot_similarities
        
    except Exception as e:
        print(f"Error computing hotspot similarities: {e}")
        return []

def _compute_content_similarity(db_path: str, query: str, content_ids: List[str]) -> List[Tuple[str, float]]:
    """
    Compute embedding similarity between query and content nodes.
    
    Returns:
        List of (content_id, similarity_score) tuples, sorted by score desc
    """
    if not content_ids:
        return []
    
    try:
        # Get query embedding
        query_embedding = np.array(embed_text(query), dtype=np.float32)
        
        conn = _get_connection(db_path)
        cursor = conn.cursor()
        
        # Get content embeddings
        placeholders = ','.join(['?'] * len(content_ids))
        cursor.execute(f"""
            SELECT e.node_id, e.vector
            FROM embeddings e
            WHERE e.node_id IN ({placeholders})
        """, content_ids)
        
        content_similarities = []
        
        for content_id, vector_blob in cursor.fetchall():
            try:
                content_vector = np.frombuffer(vector_blob, dtype=np.float32)
                
                # Calculate cosine similarity
                dot_product = np.dot(query_embedding, content_vector)
                norm_query = np.linalg.norm(query_embedding)
                norm_content = np.linalg.norm(content_vector)
                
                if norm_query > 0 and norm_content > 0:
                    similarity = float(dot_product / (norm_query * norm_content))
                    content_similarities.append((content_id, similarity))
            
            except Exception as e:
                print(f"Error computing similarity for content {content_id}: {e}")
                continue
        
        conn.close()
        
        # Sort by similarity descending  
        content_similarities.sort(key=lambda x: x[1], reverse=True)
        return content_similarities
        
    except Exception as e:
        print(f"Error computing content similarities: {e}")
        return []

def retrieve_complete_dfs(db_path: str, query: str, top_k: int = 5, 
                         domain: Optional[str] = None, max_depth: int = 5) -> List[CompleteRetrievalResult]:
    """
    Complete DFS retrieval through the hotspot tree with 100% coverage.
    
    No fallback pools needed - every node is in the tree.
    
    Algorithm:
    1. Start at root hotspots
    2. Compute query similarity to root hotspots
    3. Pick best matching root hotspot(s)
    4. For each chosen root: DFS down the hierarchy
    5. At each level, pick best matching children
    6. Continue until leaf hotspots (no child hotspots)
    7. At leaf hotspots, rank their content members by similarity
    8. Return: context hotspot + top content matches
    
    Args:
        db_path: Path to SQLite database
        query: Search query
        top_k: Number of results to return
        domain: Optional domain filter
        max_depth: Maximum tree depth to traverse
        
    Returns:
        List of CompleteRetrievalResult objects
    """
    if not query or not query.strip():
        return []
    
    # Build hierarchy
    children_map, parent_map, cluster_members_map = _build_hotspot_hierarchy(db_path, domain)
    
    if not cluster_members_map:
        return []  # No clusters exist
    
    all_hotspots = set(children_map.keys()) | set(parent_map.keys()) | set(cluster_members_map.keys())
    root_hotspots = _find_root_hotspots(parent_map, all_hotspots)
    
    if not root_hotspots:
        # No hierarchy - treat all hotspots as roots
        root_hotspots = list(cluster_members_map.keys())
    
    # DFS search through hierarchy
    def dfs_search(current_hotspots: List[str], depth: int = 0) -> Tuple[str, float, List[str]]:
        """
        DFS through hotspot hierarchy.
        
        Returns:
            Tuple of (best_leaf_hotspot_id, best_score, path_to_leaf)
        """
        if depth >= max_depth or not current_hotspots:
            return None, 0.0, []
        
        # Compute similarities for current level hotspots
        hotspot_similarities = _compute_hotspot_similarity(db_path, query, current_hotspots, cluster_members_map)
        
        if not hotspot_similarities:
            return None, 0.0, []
        
        # Take top 3 for exploration to balance precision and coverage
        explore_count = min(3, len(hotspot_similarities))
        best_leaf = None
        best_leaf_score = 0.0
        best_path = []
        
        for hotspot_id, similarity in hotspot_similarities[:explore_count]:
            # Check if this hotspot has child hotspots
            child_hotspots = children_map.get(hotspot_id, [])
            
            if child_hotspots:
                # Has children - recurse deeper
                child_leaf, child_score, child_path = dfs_search(child_hotspots, depth + 1)
                if child_score > best_leaf_score:
                    best_leaf = child_leaf
                    best_leaf_score = child_score
                    best_path = [hotspot_id] + child_path
            else:
                # Leaf hotspot - candidate for final selection
                if similarity > best_leaf_score:
                    best_leaf = hotspot_id
                    best_leaf_score = similarity
                    best_path = [hotspot_id]
        
        return best_leaf, best_leaf_score, best_path
    
    # Execute DFS from root hotspots
    best_hotspot_id, best_hotspot_score, traversal_path = dfs_search(root_hotspots)
    
    if not best_hotspot_id:
        return []
    
    # Get content members from the best leaf hotspot
    content_members = cluster_members_map.get(best_hotspot_id, [])
    
    if not content_members:
        return []
    
    # Rank content members by similarity to query
    content_similarities = _compute_content_similarity(db_path, query, content_members)
    
    # Load node details
    all_result_ids = [best_hotspot_id] + [content_id for content_id, _ in content_similarities]
    node_details = _load_node_details_complete(db_path, all_result_ids, domain)
    
    # Build results
    results = []
    
    # Add the best leaf hotspot as context (boosted score)
    if best_hotspot_id in node_details:
        details = node_details[best_hotspot_id]
        results.append(CompleteRetrievalResult(
            node_id=best_hotspot_id,
            content=details["content"],
            node_type=details["node_type"],
            domain=details["domain"],
            score=best_hotspot_score * HOTSPOT_BOOST,  # Boost hotspot to appear first
            path=traversal_path,
            cluster_context=best_hotspot_id
        ))
    
    # Add content nodes ranked by similarity
    for content_id, content_similarity in content_similarities:
        if content_id in node_details:
            details = node_details[content_id]
            results.append(CompleteRetrievalResult(
                node_id=content_id,
                content=details["content"],
                node_type=details["node_type"],
                domain=details["domain"],
                score=content_similarity,
                path=traversal_path + [content_id],
                cluster_context=best_hotspot_id
            ))
    
    return results[:top_k]

def retrieve_complete_hierarchical(db_path: str, query: str, top_k: int = 5,
                                  top_hotspots: int = 3, domain: Optional[str] = None) -> List[CompleteRetrievalResult]:
    """
    Two-stage hierarchical retrieval with complete coverage.
    
    Stage 1: Find the most relevant hotspot(s) for the query
    Stage 2: Search within their cluster members for specific answers
    
    No unclustered fallback needed since every node is in a cluster.
    
    Args:
        db_path: Path to SQLite database
        query: Search query
        top_k: Number of final results to return
        top_hotspots: Number of hotspots to route through (stage 1)
        domain: Optional domain filter
        
    Returns:
        List of CompleteRetrievalResult objects
    """
    if not query or not query.strip():
        return []
    
    # Build hierarchy
    children_map, parent_map, cluster_members_map = _build_hotspot_hierarchy(db_path, domain)
    
    if not cluster_members_map:
        return []
    
    all_hotspots = list(cluster_members_map.keys())
    
    # Stage 1: Find relevant hotspots
    hotspot_similarities = _compute_hotspot_similarity(db_path, query, all_hotspots, cluster_members_map)
    
    if not hotspot_similarities:
        return []
    
    selected_hotspots = hotspot_similarities[:top_hotspots]
    
    # Stage 2: Get cluster members for selected hotspots  
    search_pool = set()  # Content node IDs to search within
    hotspot_result_ids = set()
    
    for hotspot_id, hotspot_sim in selected_hotspots:
        hotspot_result_ids.add(hotspot_id)
        members = cluster_members_map.get(hotspot_id, [])
        search_pool.update(members)
    
    # Rank the search pool by content similarity
    pool_similarities = _compute_content_similarity(db_path, query, list(search_pool))
    
    # Load node details
    all_candidate_ids = list(hotspot_result_ids) + [content_id for content_id, _ in pool_similarities]
    node_details = _load_node_details_complete(db_path, all_candidate_ids, domain)
    
    # Build results: top-1 hotspot (routing context), then content nodes
    results = []
    
    # Add ONLY the top hotspot as context header
    if selected_hotspots:
        best_hotspot_id, best_h_score = selected_hotspots[0]
        if best_hotspot_id in node_details:
            details = node_details[best_hotspot_id]
            results.append(CompleteRetrievalResult(
                node_id=best_hotspot_id,
                content=details["content"],
                node_type=details["node_type"],
                domain=details["domain"],
                score=best_h_score * HOTSPOT_BOOST,
                path=[best_hotspot_id],
                cluster_context=best_hotspot_id
            ))
    
    # Add ranked content members
    for content_id, content_similarity in pool_similarities:
        if content_id in node_details:
            details = node_details[content_id]
            
            # Find which hotspot contains this content
            containing_hotspot = None
            for hotspot_id in hotspot_result_ids:
                if content_id in cluster_members_map.get(hotspot_id, []):
                    containing_hotspot = hotspot_id
                    break
            
            results.append(CompleteRetrievalResult(
                node_id=content_id,
                content=details["content"],
                node_type=details["node_type"],
                domain=details["domain"],
                score=content_similarity,
                path=[containing_hotspot, content_id] if containing_hotspot else [content_id],
                cluster_context=containing_hotspot or "unknown"
            ))
    
    return results[:top_k]

def retrieve_complete_breadth_first(db_path: str, query: str, top_k: int = 5,
                                   domain: Optional[str] = None) -> List[CompleteRetrievalResult]:
    """
    Breadth-first retrieval that explores all hotspots at once.
    
    Good for queries that might span multiple domains or when you want
    broader coverage rather than focused DFS drilling.
    
    Args:
        db_path: Path to SQLite database  
        query: Search query
        top_k: Number of results to return
        domain: Optional domain filter
        
    Returns:
        List of CompleteRetrievalResult objects
    """
    if not query or not query.strip():
        return []
    
    # Build hierarchy
    children_map, parent_map, cluster_members_map = _build_hotspot_hierarchy(db_path, domain)
    
    if not cluster_members_map:
        return []
    
    # Get all content from all clusters
    all_content_ids = []
    content_to_hotspot = {}
    
    for hotspot_id, members in cluster_members_map.items():
        all_content_ids.extend(members)
        for member_id in members:
            content_to_hotspot[member_id] = hotspot_id
    
    if not all_content_ids:
        return []
    
    # Rank ALL content by similarity (breadth-first approach)
    content_similarities = _compute_content_similarity(db_path, query, all_content_ids)
    
    # Load node details
    node_details = _load_node_details_complete(db_path, 
                                              [cid for cid, _ in content_similarities[:top_k*2]], 
                                              domain)
    
    # Build results
    results = []
    hotspots_included = set()
    
    for content_id, content_similarity in content_similarities:
        if len(results) >= top_k:
            break
            
        if content_id not in node_details:
            continue
        
        details = node_details[content_id]
        containing_hotspot = content_to_hotspot.get(content_id, "unknown")
        
        # For breadth-first, include the context hotspot before the first content from that cluster
        if containing_hotspot != "unknown" and containing_hotspot not in hotspots_included:
            hotspots_included.add(containing_hotspot)
            
            # Load hotspot details if not already loaded
            if containing_hotspot not in node_details:
                hotspot_details = _load_node_details_complete(db_path, [containing_hotspot], domain)
                node_details.update(hotspot_details)
            
            if containing_hotspot in node_details:
                h_details = node_details[containing_hotspot]
                results.append(CompleteRetrievalResult(
                    node_id=containing_hotspot,
                    content=h_details["content"],
                    node_type=h_details["node_type"], 
                    domain=h_details["domain"],
                    score=content_similarity * HOTSPOT_BOOST,  # Inherit score from best content
                    path=[containing_hotspot],
                    cluster_context=containing_hotspot
                ))
        
        # Add the content node
        results.append(CompleteRetrievalResult(
            node_id=content_id,
            content=details["content"],
            node_type=details["node_type"],
            domain=details["domain"],
            score=content_similarity,
            path=[containing_hotspot, content_id],
            cluster_context=containing_hotspot
        ))
    
    return results[:top_k]

def format_complete_context(results: List[CompleteRetrievalResult], include_paths: bool = False) -> str:
    """
    Format complete retrieval results into a prompt-ready context string.
    
    Args:
        results: List of CompleteRetrievalResult objects
        include_paths: Whether to include tree traversal paths in output
        
    Returns:
        Formatted context string
    """
    if not results:
        return "No relevant context found."
    
    context_lines = ["=== RELEVANT CONTEXT (Complete Coverage) ==="]
    
    for i, result in enumerate(results, 1):
        # Basic info line with domain and cluster context
        domain_str = f" (Domain: {result.domain})" if result.domain and result.domain != "unknown" else ""
        cluster_str = f" [Cluster: {result.cluster_context}]" if result.cluster_context != "unknown" else ""
        
        lines = [f"{i}. [{result.node_type.upper()}]{domain_str}{cluster_str} {result.content}"]
        
        # Add tree traversal path if requested
        if include_paths and len(result.path) > 1:
            path_display = " → ".join(result.path[-3:])  # Show last 3 nodes in path
            if len(result.path) > 3:
                path_display = "... → " + path_display
            lines.append(f"   Tree Path: {path_display}")
        
        # Add relevance score for debugging
        lines.append(f"   Relevance: {result.score:.3f}")
        
        context_lines.extend(lines)
        context_lines.append("")  # Blank line between results
    
    return "\n".join(context_lines)

def explain_complete_retrieval(db_path: str, query: str, top_k: int = 5, method: str = "dfs") -> Dict:
    """
    Detailed explanation of the complete retrieval process for debugging.
    
    Args:
        db_path: Path to SQLite database
        query: Search query
        top_k: Number of results to return
        method: Retrieval method ("dfs", "hierarchical", "breadth_first")
        
    Returns:
        Dictionary with detailed breakdown of retrieval process
    """
    # Build hierarchy for explanation
    children_map, parent_map, cluster_members_map = _build_hotspot_hierarchy(db_path)
    
    all_hotspots = set(children_map.keys()) | set(parent_map.keys()) | set(cluster_members_map.keys())
    root_hotspots = _find_root_hotspots(parent_map, all_hotspots)
    
    # Get retrieval results
    if method == "dfs":
        results = retrieve_complete_dfs(db_path, query, top_k)
    elif method == "hierarchical":
        results = retrieve_complete_hierarchical(db_path, query, top_k)
    elif method == "breadth_first":
        results = retrieve_complete_breadth_first(db_path, query, top_k)
    else:
        results = []
    
    # Calculate coverage statistics
    total_content_nodes = sum(len(members) for members in cluster_members_map.values())
    unique_content_nodes = len(set().union(*cluster_members_map.values()) if cluster_members_map else set())
    
    explanation = {
        "query": query,
        "method": method,
        "hierarchy_stats": {
            "total_hotspots": len(all_hotspots),
            "root_hotspots": len(root_hotspots),
            "parent_child_relationships": len(parent_map),
            "clusters_with_content": len(cluster_members_map),
            "total_content_assignments": total_content_nodes,
            "unique_content_nodes": unique_content_nodes,
            "coverage_ratio": unique_content_nodes / total_content_nodes if total_content_nodes > 0 else 1.0
        },
        "root_hotspots": [
            {
                "hotspot_id": hid,
                "cluster_size": len(cluster_members_map.get(hid, [])),
                "has_children": len(children_map.get(hid, []))
            }
            for hid in root_hotspots[:5]  # Show top 5
        ],
        "final_results": [result.to_dict() for result in results],
        "summary": {
            "method_used": method,
            "final_results": len(results),
            "coverage_complete": unique_content_nodes == total_content_nodes,
            "fallback_pools_needed": 0  # Always 0 with complete coverage
        }
    }
    
    return explanation