#!/usr/bin/env python3
"""
Cashew Hierarchy Evolution Module
Evolves the clustering hierarchy through merge, split, promote, and reclassify operations.

Operations during sleep cycles:
- Merge: Combine clusters with high inter-cluster similarity
- Split: Subdivide large or internally diverse clusters  
- Promote: Create parent-level hotspots for concepts that span multiple clusters
- Reclassify: Move nodes to better-fitting clusters
"""

import sqlite3
import json
import hashlib
import logging
import numpy as np
from typing import List, Dict, Optional, Tuple, Set, Callable
from datetime import datetime, timezone
from dataclasses import dataclass
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine_sim

from core.hotspots import create_hotspot, update_hotspot, get_hotspot, HOTSPOT_TYPE
from core.complete_clustering import load_embeddings_with_metadata, cosine_similarity

logger = logging.getLogger("cashew.hierarchy_evolution")

DB_PATH = "/Users/bunny/.openclaw/workspace/cashew/data/graph.db"

# Evolution parameters
MERGE_THRESHOLD = 0.6          # Avg pairwise similarity to trigger cluster merge
SPLIT_SIZE_THRESHOLD = 15      # Cluster size that triggers split consideration
SPLIT_DIVERSITY_THRESHOLD = 0.4  # Avg intra-cluster similarity below which to split
PROMOTE_SIMILARITY_THRESHOLD = 0.5  # Node similarity across clusters to trigger promotion
RECLASSIFY_IMPROVEMENT_THRESHOLD = 0.1  # Min similarity improvement to move a node


@dataclass
class ClusterStats:
    """Statistics about a cluster for evolution decisions"""
    hotspot_id: str
    member_ids: List[str]
    centroid: np.ndarray
    avg_intra_similarity: float
    size: int
    domain: str
    is_parent: bool
    children: List[str]  # Child hotspot IDs
    
    
@dataclass 
class EvolutionAction:
    """An action taken during hierarchy evolution"""
    action_type: str  # "merge", "split", "promote", "reclassify"
    source_entities: List[str]  # Hotspot IDs or node IDs involved
    target_entities: List[str]  # Result hotspot IDs or node IDs
    reasoning: str
    confidence: float
    

def _get_connection(db_path: str) -> sqlite3.Connection:
    """Get database connection"""
    return sqlite3.connect(db_path)


def _get_all_cluster_stats(db_path: str) -> Dict[str, ClusterStats]:
    """
    Load statistics for all existing clusters.
    
    Returns:
        Dict mapping hotspot_id -> ClusterStats
    """
    node_ids, vectors, node_meta = load_embeddings_with_metadata(db_path)
    if not node_ids:
        return {}
    
    # Build lookup from node_id to vector index
    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}
    
    conn = _get_connection(db_path)
    cursor = conn.cursor()
    
    # Get all hotspots with their cluster members
    cursor.execute("""
        SELECT tn.id, tn.content, COALESCE(tn.domain, 'general') as domain
        FROM thought_nodes tn
        WHERE tn.node_type = ? AND (tn.decayed IS NULL OR tn.decayed = 0)
    """, (HOTSPOT_TYPE,))
    
    hotspots = cursor.fetchall()
    cluster_stats = {}
    
    for hotspot_id, hotspot_content, domain in hotspots:
        # Get cluster members
        cursor.execute("""
            SELECT de.child_id 
            FROM derivation_edges de
            WHERE de.parent_id = ? AND de.relation = 'summarizes'
        """, (hotspot_id,))
        
        member_ids = [row[0] for row in cursor.fetchall()]
        
        # Get members that have embeddings
        member_indices = [id_to_idx[mid] for mid in member_ids if mid in id_to_idx]
        
        if len(member_indices) < 2:
            # Skip clusters with too few embedded members
            continue
        
        # Calculate centroid and intra-cluster similarity
        member_vectors = vectors[member_indices]
        centroid = member_vectors.mean(axis=0)
        
        # Calculate average pairwise similarity within cluster
        sim_matrix = sklearn_cosine_sim(member_vectors)
        # Get upper triangle (excluding diagonal)
        n = len(member_vectors)
        if n > 1:
            similarities = []
            for i in range(n):
                for j in range(i+1, n):
                    similarities.append(sim_matrix[i, j])
            avg_intra_similarity = float(np.mean(similarities))
        else:
            avg_intra_similarity = 1.0
        
        # Check if this is a parent hotspot (has children that are also hotspots)
        cursor.execute("""
            SELECT de.child_id
            FROM derivation_edges de
            JOIN thought_nodes tn ON de.child_id = tn.id
            WHERE de.parent_id = ? AND de.relation = 'summarizes' 
            AND tn.node_type = ?
        """, (hotspot_id, HOTSPOT_TYPE))
        
        child_hotspots = [row[0] for row in cursor.fetchall()]
        
        cluster_stats[hotspot_id] = ClusterStats(
            hotspot_id=hotspot_id,
            member_ids=member_ids,
            centroid=centroid,
            avg_intra_similarity=avg_intra_similarity,
            size=len(member_ids),
            domain=domain,
            is_parent=len(child_hotspots) > 0,
            children=child_hotspots
        )
    
    conn.close()
    return cluster_stats


def identify_merge_candidates(cluster_stats: Dict[str, ClusterStats]) -> List[Tuple[str, str, float]]:
    """
    Identify pairs of clusters that should be merged due to high inter-cluster similarity.
    
    Returns:
        List of (hotspot1_id, hotspot2_id, avg_similarity) tuples
    """
    merge_candidates = []
    hotspot_ids = list(cluster_stats.keys())
    
    # Only consider leaf clusters (not parent hotspots) for merging
    leaf_clusters = {hid: stats for hid, stats in cluster_stats.items() if not stats.is_parent}
    
    if len(leaf_clusters) < 2:
        return merge_candidates
    
    leaf_ids = list(leaf_clusters.keys())
    
    for i, hotspot1_id in enumerate(leaf_ids):
        for hotspot2_id in leaf_ids[i+1:]:
            stats1 = leaf_clusters[hotspot1_id]
            stats2 = leaf_clusters[hotspot2_id]
            
            # Skip if different domains (domains should merge organically)
            if stats1.domain != stats2.domain:
                continue
            
            # Calculate inter-cluster similarity (centroid similarity)
            inter_similarity = cosine_similarity(stats1.centroid, stats2.centroid)
            
            # Also check if combined cluster would have good intra-cluster similarity
            if inter_similarity >= MERGE_THRESHOLD:
                # Additional check: would the merged cluster be cohesive?
                combined_size = stats1.size + stats2.size
                if combined_size <= SPLIT_SIZE_THRESHOLD * 1.5:  # Don't create oversized clusters
                    merge_candidates.append((hotspot1_id, hotspot2_id, inter_similarity))
    
    # Sort by similarity (highest first)
    merge_candidates.sort(key=lambda x: x[2], reverse=True)
    
    logger.info(f"Found {len(merge_candidates)} merge candidates")
    return merge_candidates


def identify_split_candidates(cluster_stats: Dict[str, ClusterStats]) -> List[Tuple[str, str]]:
    """
    Identify clusters that should be split due to size or diversity.
    
    Returns:
        List of (hotspot_id, reason) tuples
    """
    split_candidates = []
    
    for hotspot_id, stats in cluster_stats.items():
        # Skip parent hotspots - they're already split
        if stats.is_parent:
            continue
        
        # Check size threshold
        if stats.size > SPLIT_SIZE_THRESHOLD:
            split_candidates.append((hotspot_id, f"oversized_{stats.size}"))
            continue
        
        # Check diversity threshold
        if stats.avg_intra_similarity < SPLIT_DIVERSITY_THRESHOLD:
            split_candidates.append((hotspot_id, f"diverse_{stats.avg_intra_similarity:.3f}"))
    
    logger.info(f"Found {len(split_candidates)} split candidates")
    return split_candidates


def identify_promotion_candidates(db_path: str, cluster_stats: Dict[str, ClusterStats]) -> List[Tuple[str, List[str], float]]:
    """
    Identify concepts/nodes that appear across multiple clusters and should be promoted to parent level.
    
    Returns:
        List of (concept_content, related_cluster_ids, avg_similarity) tuples
    """
    node_ids, vectors, node_meta = load_embeddings_with_metadata(db_path)
    if not node_ids:
        return []
    
    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}
    promotion_candidates = []
    
    # Find nodes that are semantically similar to multiple cluster centroids
    for node_id in node_ids:
        if node_id not in id_to_idx:
            continue
        
        node_vector = vectors[id_to_idx[node_id]]
        node_content = node_meta[node_id]["content"]
        
        # Calculate similarity to each cluster centroid
        cluster_similarities = []
        for hotspot_id, stats in cluster_stats.items():
            if stats.is_parent:  # Skip parent clusters
                continue
            
            similarity = cosine_similarity(node_vector, stats.centroid)
            if similarity >= PROMOTE_SIMILARITY_THRESHOLD:
                cluster_similarities.append((hotspot_id, similarity))
        
        # If this node is similar to multiple clusters, it's a promotion candidate
        if len(cluster_similarities) >= 2:  # Similar to 2+ clusters
            related_clusters = [hid for hid, sim in cluster_similarities]
            avg_similarity = sum(sim for hid, sim in cluster_similarities) / len(cluster_similarities)
            
            promotion_candidates.append((node_content, related_clusters, avg_similarity))
    
    # Sort by average similarity (highest first) and limit to top candidates
    promotion_candidates.sort(key=lambda x: x[2], reverse=True)
    promotion_candidates = promotion_candidates[:5]  # Top 5 promotion candidates
    
    logger.info(f"Found {len(promotion_candidates)} promotion candidates")
    return promotion_candidates


def identify_reclassification_candidates(db_path: str, cluster_stats: Dict[str, ClusterStats]) -> List[Tuple[str, str, str, float]]:
    """
    Identify nodes that would fit better in a different cluster.
    
    Returns:
        List of (node_id, current_cluster, better_cluster, similarity_improvement) tuples
    """
    node_ids, vectors, node_meta = load_embeddings_with_metadata(db_path)
    if not node_ids:
        return []
    
    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}
    reclassification_candidates = []
    
    # For each node, check if it would fit better in a different cluster
    for node_id in node_ids:
        if node_id not in id_to_idx:
            continue
        
        node_vector = vectors[id_to_idx[node_id]]
        
        # Find current cluster
        current_cluster = None
        current_similarity = 0.0
        
        for hotspot_id, stats in cluster_stats.items():
            if node_id in stats.member_ids:
                current_cluster = hotspot_id
                current_similarity = cosine_similarity(node_vector, stats.centroid)
                break
        
        if not current_cluster:
            continue  # Node not in any cluster (shouldn't happen with complete clustering)
        
        # Find best alternative cluster
        best_alternative = None
        best_similarity = current_similarity
        
        for hotspot_id, stats in cluster_stats.items():
            if hotspot_id == current_cluster or stats.is_parent:
                continue
            
            similarity = cosine_similarity(node_vector, stats.centroid)
            if similarity > best_similarity + RECLASSIFY_IMPROVEMENT_THRESHOLD:
                best_alternative = hotspot_id
                best_similarity = similarity
        
        if best_alternative:
            improvement = best_similarity - current_similarity
            reclassification_candidates.append((
                node_id, current_cluster, best_alternative, improvement
            ))
    
    # Sort by improvement (highest first) and limit
    reclassification_candidates.sort(key=lambda x: x[3], reverse=True)
    reclassification_candidates = reclassification_candidates[:10]  # Top 10
    
    logger.info(f"Found {len(reclassification_candidates)} reclassification candidates")
    return reclassification_candidates


def execute_merge(db_path: str, hotspot1_id: str, hotspot2_id: str, 
                 model_fn: Optional[Callable[[str], str]] = None) -> str:
    """
    Merge two clusters by combining their hotspots and members.
    
    Returns:
        ID of the merged hotspot
    """
    conn = _get_connection(db_path)
    cursor = conn.cursor()
    
    # Get both hotspots
    cursor.execute("""
        SELECT id, content, domain, metadata FROM thought_nodes 
        WHERE id IN (?, ?) AND node_type = ?
    """, (hotspot1_id, hotspot2_id, HOTSPOT_TYPE))
    
    hotspots = cursor.fetchall()
    if len(hotspots) != 2:
        conn.close()
        raise ValueError(f"Could not find both hotspots: {hotspot1_id}, {hotspot2_id}")
    
    # Choose the hotspot with more members to be the primary
    cursor.execute("""
        SELECT COUNT(*) FROM derivation_edges 
        WHERE parent_id = ? AND relation = 'summarizes'
    """, (hotspot1_id,))
    count1 = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM derivation_edges 
        WHERE parent_id = ? AND relation = 'summarizes'
    """, (hotspot2_id,))
    count2 = cursor.fetchone()[0]
    
    if count1 >= count2:
        primary_id, secondary_id = hotspot1_id, hotspot2_id
    else:
        primary_id, secondary_id = hotspot2_id, hotspot1_id
    
    # Get all members from secondary cluster
    cursor.execute("""
        SELECT child_id FROM derivation_edges 
        WHERE parent_id = ? AND relation = 'summarizes'
    """, (secondary_id,))
    
    secondary_members = [row[0] for row in cursor.fetchall()]
    
    # Move all secondary members to primary cluster
    for member_id in secondary_members:
        cursor.execute("""
            UPDATE derivation_edges 
            SET parent_id = ?, reasoning = ?
            WHERE parent_id = ? AND child_id = ? AND relation = 'summarizes'
        """, (primary_id, f"Cluster merge: {secondary_id} -> {primary_id}", secondary_id, member_id))
    
    # Generate merged summary if model is available
    if model_fn:
        primary_content = next(h[1] for h in hotspots if h[0] == primary_id)
        secondary_content = next(h[1] for h in hotspots if h[0] == secondary_id)
        
        prompt = f"""Two related clusters are being merged. Create a new summary that captures both areas:

Cluster 1: {primary_content}
Cluster 2: {secondary_content}

Merged summary (1-2 sentences):"""
        
        try:
            merged_summary = model_fn(prompt).strip()
            cursor.execute("""
                UPDATE thought_nodes SET content = ?, last_updated = ?
                WHERE id = ?
            """, (merged_summary, datetime.now(timezone.utc).isoformat(), primary_id))
        except Exception as e:
            logger.warning(f"Failed to generate merged summary: {e}")
    
    # Mark secondary hotspot as decayed
    cursor.execute("""
        UPDATE thought_nodes SET decayed = 1 WHERE id = ?
    """, (secondary_id,))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Merged clusters: {secondary_id} -> {primary_id} ({len(secondary_members)} members moved)")
    return primary_id


def execute_split(db_path: str, hotspot_id: str, reason: str,
                 model_fn: Optional[Callable[[str], str]] = None) -> List[str]:
    """
    Split a cluster into sub-clusters.
    
    Returns:
        List of new sub-cluster hotspot IDs
    """
    from core.complete_clustering import detect_complete_clusters
    
    conn = _get_connection(db_path)
    cursor = conn.cursor()
    
    # Get cluster members
    cursor.execute("""
        SELECT de.child_id, tn.content, COALESCE(tn.domain, 'general') as domain
        FROM derivation_edges de
        JOIN thought_nodes tn ON de.child_id = tn.id
        WHERE de.parent_id = ? AND de.relation = 'summarizes'
        AND (tn.decayed IS NULL OR tn.decayed = 0)
    """, (hotspot_id,))
    
    members = cursor.fetchall()
    if len(members) < 6:  # Need at least 6 members to split into 2 groups of 3
        conn.close()
        logger.warning(f"Cannot split cluster {hotspot_id}: too few members ({len(members)})")
        return []
    
    member_ids = [m[0] for m in members]
    
    # Create temporary sub-clustering on just these members
    # This is a simplified version - in practice, you'd use the embedding vectors
    # and run a tighter DBSCAN on just this subset
    
    # For now, simple domain-based splitting
    domain_groups = {}
    for member_id, content, domain in members:
        if domain not in domain_groups:
            domain_groups[domain] = []
        domain_groups[domain].append(member_id)
    
    # If we have meaningful domain groups, split by domain
    if len(domain_groups) > 1 and all(len(group) >= 3 for group in domain_groups.values()):
        new_hotspot_ids = []
        
        for domain, group_members in domain_groups.items():
            if len(group_members) < 3:
                continue  # Skip small groups
                
            # Create new hotspot for this sub-cluster
            original_content = cursor.execute(
                "SELECT content FROM thought_nodes WHERE id = ?", (hotspot_id,)
            ).fetchone()[0]
            
            sub_content = f"[{domain.upper()} SPLIT] {original_content[:60]}..."
            if model_fn:
                try:
                    # Get sample content from this group
                    sample_contents = []
                    for mid in group_members[:3]:
                        cursor.execute("SELECT content FROM thought_nodes WHERE id = ?", (mid,))
                        result = cursor.fetchone()
                        if result:
                            sample_contents.append(result[0][:80])
                    
                    prompt = f"""Create a focused summary for this sub-cluster in the {domain} domain:

Sample thoughts:
{chr(10).join(f'- {c}' for c in sample_contents)}

Sub-cluster summary (1-2 sentences):"""
                    
                    sub_content = model_fn(prompt).strip()
                except Exception as e:
                    logger.warning(f"Failed to generate sub-cluster summary: {e}")
            
            new_hotspot_id = create_hotspot(
                db_path=db_path,
                content=sub_content,
                status="auto_generated_split",
                file_pointers={},
                cluster_node_ids=group_members,
                domain=domain,
                tags=["auto_cluster", "split_result", f"split_from_{hotspot_id}"]
            )
            new_hotspot_ids.append(new_hotspot_id)
        
        # Mark original hotspot as parent if we created multiple sub-clusters
        if len(new_hotspot_ids) > 1:
            cursor.execute("""
                UPDATE thought_nodes 
                SET content = ?, metadata = json_set(COALESCE(metadata, '{}'), '$.is_split_parent', true)
                WHERE id = ?
            """, (f"[PARENT] {cursor.execute('SELECT content FROM thought_nodes WHERE id = ?', (hotspot_id,)).fetchone()[0]}", hotspot_id))
            
            # Create parent-child relationships
            for new_hotspot_id in new_hotspot_ids:
                cursor.execute("""
                    INSERT OR IGNORE INTO derivation_edges 
                    (parent_id, child_id, relation, weight, reasoning)
                    VALUES (?, ?, 'summarizes', 0.9, ?)
                """, (hotspot_id, new_hotspot_id, f"Split operation result"))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Split cluster {hotspot_id} into {len(new_hotspot_ids)} sub-clusters (reason: {reason})")
        return new_hotspot_ids
    
    conn.close()
    logger.warning(f"Could not split cluster {hotspot_id}: insufficient domain diversity")
    return []


def execute_promotion(db_path: str, concept_content: str, related_cluster_ids: List[str],
                     model_fn: Optional[Callable[[str], str]] = None) -> str:
    """
    Create a parent-level hotspot that captures a concept spanning multiple clusters.
    
    Returns:
        ID of the promoted hotspot
    """
    if model_fn:
        cluster_summaries = []
        conn = _get_connection(db_path)
        cursor = conn.cursor()
        
        for cluster_id in related_cluster_ids:
            cursor.execute("SELECT content FROM thought_nodes WHERE id = ?", (cluster_id,))
            result = cursor.fetchone()
            if result:
                cluster_summaries.append(result[0][:80])
        
        conn.close()
        
        prompt = f"""A concept appears across multiple clusters and should be promoted to a parent level. Create a parent hotspot summary.

Cross-cluster concept: {concept_content[:100]}

Related clusters:
{chr(10).join(f'- {s}' for s in cluster_summaries)}

Parent-level summary (1-2 sentences):"""
        
        try:
            parent_content = model_fn(prompt).strip()
        except Exception as e:
            logger.warning(f"Failed to generate promotion summary: {e}")
            parent_content = f"[PROMOTED] {concept_content[:80]}"
    else:
        parent_content = f"[PROMOTED] {concept_content[:80]}"
    
    # Infer domain from related clusters
    conn = _get_connection(db_path)
    cursor = conn.cursor()
    
    domains = []
    for cluster_id in related_cluster_ids:
        cursor.execute("SELECT COALESCE(domain, 'general') FROM thought_nodes WHERE id = ?", (cluster_id,))
        result = cursor.fetchone()
        if result:
            domains.append(result[0])
    
    # Use most common domain, or "cross_domain" if mixed
    if domains:
        domain_counts = {d: domains.count(d) for d in set(domains)}
        if len(domain_counts) == 1:
            promoted_domain = list(domain_counts.keys())[0]
        else:
            promoted_domain = "cross_domain"
    else:
        promoted_domain = "general"
    
    # Create the promoted hotspot
    promoted_hotspot_id = create_hotspot(
        db_path=db_path,
        content=parent_content,
        status="auto_generated_promotion",
        file_pointers={},
        cluster_node_ids=[],  # No direct members - this is a parent
        domain=promoted_domain,
        tags=["auto_cluster", "promoted", "cross_cluster"]
    )
    
    # Create parent-child relationships
    for cluster_id in related_cluster_ids:
        cursor.execute("""
            INSERT OR IGNORE INTO derivation_edges 
            (parent_id, child_id, relation, weight, reasoning)
            VALUES (?, ?, 'summarizes', 0.8, ?)
        """, (promoted_hotspot_id, cluster_id, f"Concept promotion: shared theme"))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Promoted concept to parent hotspot {promoted_hotspot_id} covering {len(related_cluster_ids)} clusters")
    return promoted_hotspot_id


def execute_reclassification(db_path: str, node_id: str, current_cluster: str, 
                           better_cluster: str, improvement: float):
    """
    Move a node from its current cluster to a better-fitting cluster.
    """
    conn = _get_connection(db_path)
    cursor = conn.cursor()
    
    # Remove from current cluster
    cursor.execute("""
        DELETE FROM derivation_edges 
        WHERE parent_id = ? AND child_id = ? AND relation = 'summarizes'
    """, (current_cluster, node_id))
    
    # Add to better cluster
    cursor.execute("""
        INSERT OR IGNORE INTO derivation_edges 
        (parent_id, child_id, relation, weight, reasoning)
        VALUES (?, ?, 'summarizes', 0.8, ?)
    """, (better_cluster, node_id, f"Reclassification: similarity improvement {improvement:.3f}"))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Reclassified node {node_id}: {current_cluster} -> {better_cluster} (improvement: {improvement:.3f})")


def run_hierarchy_evolution_cycle(db_path: str, model_fn: Optional[Callable[[str], str]] = None,
                                 dry_run: bool = False) -> Dict:
    """
    Run a complete hierarchy evolution cycle with merge, split, promote, and reclassify operations.
    
    Args:
        db_path: Path to graph database
        model_fn: Optional LLM function for generating summaries
        dry_run: If True, don't modify database
        
    Returns:
        Summary dict of evolution actions taken
    """
    results = {
        "merges_performed": 0,
        "splits_performed": 0,
        "promotions_performed": 0,
        "reclassifications_performed": 0,
        "actions": []
    }
    
    logger.info("Starting hierarchy evolution cycle")
    
    # Load current cluster statistics
    cluster_stats = _get_all_cluster_stats(db_path)
    if not cluster_stats:
        logger.info("No clusters found for evolution")
        return results
    
    logger.info(f"Analyzing {len(cluster_stats)} clusters for evolution opportunities")
    
    # 1. Identify and execute merges
    merge_candidates = identify_merge_candidates(cluster_stats)
    for hotspot1_id, hotspot2_id, similarity in merge_candidates[:3]:  # Limit to top 3 merges
        if dry_run:
            results["actions"].append({
                "type": "merge",
                "source": [hotspot1_id, hotspot2_id],
                "target": hotspot1_id,
                "similarity": similarity,
                "status": "dry_run"
            })
        else:
            try:
                merged_id = execute_merge(db_path, hotspot1_id, hotspot2_id, model_fn)
                results["merges_performed"] += 1
                results["actions"].append({
                    "type": "merge", 
                    "source": [hotspot1_id, hotspot2_id],
                    "target": merged_id,
                    "similarity": similarity,
                    "status": "completed"
                })
            except Exception as e:
                logger.error(f"Failed to merge {hotspot1_id} and {hotspot2_id}: {e}")
                results["actions"].append({
                    "type": "merge",
                    "source": [hotspot1_id, hotspot2_id],
                    "target": None,
                    "similarity": similarity,
                    "status": f"failed: {e}"
                })
    
    # Refresh cluster stats after merges
    if results["merges_performed"] > 0:
        cluster_stats = _get_all_cluster_stats(db_path)
    
    # 2. Identify and execute splits
    split_candidates = identify_split_candidates(cluster_stats)
    for hotspot_id, reason in split_candidates[:2]:  # Limit to top 2 splits
        if dry_run:
            results["actions"].append({
                "type": "split",
                "source": [hotspot_id],
                "target": [],
                "reason": reason,
                "status": "dry_run"
            })
        else:
            try:
                new_hotspots = execute_split(db_path, hotspot_id, reason, model_fn)
                if new_hotspots:
                    results["splits_performed"] += 1
                    results["actions"].append({
                        "type": "split",
                        "source": [hotspot_id],
                        "target": new_hotspots,
                        "reason": reason,
                        "status": "completed"
                    })
            except Exception as e:
                logger.error(f"Failed to split {hotspot_id}: {e}")
                results["actions"].append({
                    "type": "split",
                    "source": [hotspot_id],
                    "target": [],
                    "reason": reason,
                    "status": f"failed: {e}"
                })
    
    # Refresh cluster stats after splits
    if results["splits_performed"] > 0:
        cluster_stats = _get_all_cluster_stats(db_path)
    
    # 3. Identify and execute promotions
    promotion_candidates = identify_promotion_candidates(db_path, cluster_stats)
    for concept_content, related_clusters, avg_similarity in promotion_candidates[:2]:  # Limit to top 2
        if dry_run:
            results["actions"].append({
                "type": "promote",
                "source": related_clusters,
                "target": [],
                "concept": concept_content[:60],
                "similarity": avg_similarity,
                "status": "dry_run"
            })
        else:
            try:
                promoted_id = execute_promotion(db_path, concept_content, related_clusters, model_fn)
                results["promotions_performed"] += 1
                results["actions"].append({
                    "type": "promote",
                    "source": related_clusters,
                    "target": [promoted_id],
                    "concept": concept_content[:60],
                    "similarity": avg_similarity,
                    "status": "completed"
                })
            except Exception as e:
                logger.error(f"Failed to promote concept: {e}")
                results["actions"].append({
                    "type": "promote",
                    "source": related_clusters,
                    "target": [],
                    "concept": concept_content[:60],
                    "similarity": avg_similarity,
                    "status": f"failed: {e}"
                })
    
    # 4. Identify and execute reclassifications
    reclassification_candidates = identify_reclassification_candidates(db_path, cluster_stats)
    for node_id, current_cluster, better_cluster, improvement in reclassification_candidates[:5]:  # Top 5
        if dry_run:
            results["actions"].append({
                "type": "reclassify",
                "source": [node_id],
                "from_cluster": current_cluster,
                "to_cluster": better_cluster,
                "improvement": improvement,
                "status": "dry_run"
            })
        else:
            try:
                execute_reclassification(db_path, node_id, current_cluster, better_cluster, improvement)
                results["reclassifications_performed"] += 1
                results["actions"].append({
                    "type": "reclassify",
                    "source": [node_id],
                    "from_cluster": current_cluster,
                    "to_cluster": better_cluster,
                    "improvement": improvement,
                    "status": "completed"
                })
            except Exception as e:
                logger.error(f"Failed to reclassify node {node_id}: {e}")
                results["actions"].append({
                    "type": "reclassify",
                    "source": [node_id],
                    "from_cluster": current_cluster,
                    "to_cluster": better_cluster,
                    "improvement": improvement,
                    "status": f"failed: {e}"
                })
    
    total_actions = (results["merges_performed"] + results["splits_performed"] + 
                    results["promotions_performed"] + results["reclassifications_performed"])
    
    logger.info(f"Hierarchy evolution cycle completed: {total_actions} actions performed")
    
    return results