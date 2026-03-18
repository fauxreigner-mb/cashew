#!/usr/bin/env python3
"""
Cashew Think Cycle Module
Analyzes the existing thought graph and generates new derived thoughts through LLM reasoning.
Creates connections between new insights and existing nodes.

Uses model_fn (pluggable LLM) for all reasoning. If model_fn is None, insight generation is skipped.
"""

import sqlite3
import json
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass
import sys
import random
import time

# Import existing cashew modules
from core.context import ContextRetriever
from core.patterns import PatternExtractor
from core.traversal import TraversalEngine
from core.questions import QuestionGenerator

# Database path is now configurable via environment variable or CLI
from .config import get_db_path

@dataclass
class NewThought:
    content: str
    confidence: float
    parent_ids: List[str]
    reasoning: str

class ThinkCycle:
    """Generate new derived thoughts through LLM analysis of the existing graph"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = get_db_path()
        self.db_path = db_path
        self.context = ContextRetriever(db_path)
        self.patterns = PatternExtractor(db_path)
        self.traversal = TraversalEngine(db_path)
        self.questions = QuestionGenerator(db_path)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def _generate_node_id(self, content: str) -> str:
        """Generate unique ID for a node using content hash"""
        return hashlib.sha256(content.encode()).hexdigest()[:12]
    
    def _get_current_timestamp(self) -> str:
        """Get current ISO timestamp"""
        return datetime.now(timezone.utc).isoformat()
    
    def analyze_graph_structure(self, k_hubs: int = 5, k_contradictions: int = 3,
                                 k_leaves: int = 8, k_questions: int = 5) -> Dict:
        """Analyze the current graph, randomly sampling from each category.
        
        Random sampling ensures each think cycle sees different nodes,
        preventing rich-get-richer on hub nodes and maintaining ROI per cycle.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        analysis = {}
        
        # Get ALL hub nodes (nodes with edge count > 2), then random sample
        cursor.execute("""
            SELECT * FROM (
                SELECT tn.id, tn.content, tn.confidence, 
                       (SELECT COUNT(*) FROM derivation_edges de1 WHERE de1.parent_id = tn.id) +
                       (SELECT COUNT(*) FROM derivation_edges de2 WHERE de2.child_id = tn.id) as edge_count
                FROM thought_nodes tn
            ) WHERE edge_count > 2
            ORDER BY edge_count DESC
        """)
        all_hubs = cursor.fetchall()
        analysis['hub_nodes'] = random.sample(all_hubs, min(k_hubs, len(all_hubs))) if all_hubs else []
        
        # Get ALL contradiction nodes, then random sample
        cursor.execute("""
            SELECT DISTINCT tn.id, tn.content, tn.confidence
            FROM thought_nodes tn
            JOIN derivation_edges de ON tn.id = de.child_id OR tn.id = de.parent_id
            WHERE de.reasoning LIKE '%contradict%' OR de.reasoning LIKE '%conflict%'
        """)
        all_contradictions = cursor.fetchall()
        analysis['contradiction_nodes'] = random.sample(all_contradictions, min(k_contradictions, len(all_contradictions))) if all_contradictions else []
        
        # Get ALL leaf nodes (nodes with no children), then random sample
        cursor.execute("""
            SELECT tn.id, tn.content, tn.confidence
            FROM thought_nodes tn
            LEFT JOIN derivation_edges de ON tn.id = de.parent_id
            WHERE de.parent_id IS NULL
        """)
        all_leaves = cursor.fetchall()
        analysis['leaf_nodes'] = random.sample(all_leaves, min(k_leaves, len(all_leaves))) if all_leaves else []
        
        # Get orphan nodes (nodes with no connections at all)
        cursor.execute("""
            SELECT tn.id, tn.content, tn.confidence
            FROM thought_nodes tn
            LEFT JOIN derivation_edges de1 ON tn.id = de1.parent_id
            LEFT JOIN derivation_edges de2 ON tn.id = de2.child_id
            WHERE de1.parent_id IS NULL AND de2.child_id IS NULL
            LIMIT 10
        """)
        analysis['orphan_nodes'] = cursor.fetchall()
        
        # Get ALL question nodes, then random sample
        cursor.execute("""
            SELECT id, content, confidence
            FROM thought_nodes
            WHERE node_type = 'question'
        """)
        all_questions = cursor.fetchall()
        analysis['question_nodes'] = random.sample(all_questions, min(k_questions, len(all_questions))) if all_questions else []
        
        # Get recent high-confidence nodes (random sample from recent)
        cursor.execute("""
            SELECT id, content, confidence
            FROM thought_nodes
            WHERE confidence > 0.8
            ORDER BY timestamp DESC
            LIMIT 50
        """)
        all_high_conf = cursor.fetchall()
        analysis['high_confidence_nodes'] = random.sample(all_high_conf, min(15, len(all_high_conf))) if all_high_conf else []
        
        conn.close()
        return analysis
    
    def generate_insights_from_analysis(self, analysis: Dict, model_fn: Callable = None) -> List[NewThought]:
        """Generate new derived thoughts based on graph analysis using LLM reasoning.
        
        Requires model_fn for all insight generation. If model_fn is None, returns empty list.
        """
        if not model_fn:
            print("  ⚠️ No model_fn provided — skipping LLM-based insight generation")
            return []
        
        insights = []
        
        # Analyze hub nodes for meta-patterns
        hub_insights = self._reason_about_hubs(analysis['hub_nodes'], model_fn)
        insights.extend(hub_insights)
        
        # Analyze contradictions for resolution patterns
        contradiction_insights = self._reason_about_contradictions(analysis['contradiction_nodes'], model_fn)
        insights.extend(contradiction_insights)
        
        # Analyze leaf nodes for extension opportunities
        leaf_insights = self._reason_about_leaves(analysis['leaf_nodes'], model_fn)
        insights.extend(leaf_insights)
        
        # Analyze question nodes for potential answers or deeper questions
        question_insights = self._reason_about_questions(analysis['question_nodes'], model_fn)
        insights.extend(question_insights)
        
        # Generate cross-domain connections
        cross_domain_insights = self._generate_cross_domain_connections(analysis, model_fn)
        insights.extend(cross_domain_insights)
        
        return insights[:50]  # Cap at 50 to avoid overwhelming the graph
    
    def _parse_llm_insights(self, response: str, parent_ids: List[str], prefix: str = "[think cycle]") -> List[NewThought]:
        """Parse LLM response into NewThought objects.
        
        Expected format from LLM (one or more insights):
        INSIGHT: <insight text>
        CONFIDENCE: <0.0-1.0>
        REASONING: <why this insight matters>
        ---
        """
        insights = []
        blocks = response.split('---')
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            insight_text = None
            confidence = 0.6  # default
            reasoning = "LLM think cycle analysis"
            
            for line in block.split('\n'):
                line = line.strip()
                if line.upper().startswith('INSIGHT:'):
                    insight_text = line[len('INSIGHT:'):].strip()
                elif line.upper().startswith('CONFIDENCE:'):
                    try:
                        confidence = float(line[len('CONFIDENCE:'):].strip())
                        confidence = max(0.1, min(0.95, confidence))  # clamp
                    except ValueError:
                        pass
                elif line.upper().startswith('REASONING:'):
                    reasoning = line[len('REASONING:'):].strip()
            
            if insight_text:
                if not insight_text.startswith('['):
                    insight_text = f"{prefix} {insight_text}"
                insights.append(NewThought(
                    content=insight_text,
                    confidence=confidence,
                    parent_ids=parent_ids[:3],  # max 3 parents
                    reasoning=reasoning
                ))
        
        return insights
    
    def _reason_about_hubs(self, hub_nodes: List[tuple], model_fn: Callable) -> List[NewThought]:
        """Analyze hub nodes to identify meta-patterns via LLM."""
        if not hub_nodes:
            return []
        
        node_contents = "\n".join([f"- [{node[0]}] {node[1]}" for node in hub_nodes])
        node_ids = [node[0] for node in hub_nodes]
        
        prompt = f"""You are analyzing the highest-connectivity nodes in a personal knowledge graph. These are hub nodes — they have the most connections to other thoughts.

HUB NODES:
{node_contents}

Task: Identify 1-2 meta-patterns across these hub nodes. What themes converge here? What does the clustering of connections around these topics reveal about the person's thinking architecture?

These are YOUR analytical observations as an AI assistant, not the person's beliefs. Prefix accordingly.

Format each insight as:
INSIGHT: <your observation>
CONFIDENCE: <0.5-0.9>
REASONING: <why this pattern matters>
---"""
        
        try:
            response = model_fn(prompt)
            return self._parse_llm_insights(response, node_ids, "[think cycle]")
        except Exception as e:
            print(f"  ⚠️ Hub reasoning failed: {e}")
            return []
    
    def _reason_about_contradictions(self, contradiction_nodes: List[tuple], model_fn: Callable) -> List[NewThought]:
        """Analyze contradictions for resolution or productive tension via LLM."""
        if not contradiction_nodes:
            return []
        
        node_contents = "\n".join([f"- [{node[0]}] {node[1]}" for node in contradiction_nodes])
        node_ids = [node[0] for node in contradiction_nodes]
        
        prompt = f"""You are analyzing nodes in a knowledge graph that are connected by contradiction or conflict edges. These represent tensions in the person's thinking.

CONTRADICTION NODES:
{node_contents}

Task: For each contradiction, determine: is this a genuine inconsistency that should be resolved, or a productive tension that reveals competing values? Generate 1 insight.

These are YOUR analytical observations, not the person's beliefs.

Format:
INSIGHT: <your observation>
CONFIDENCE: <0.5-0.9>
REASONING: <why this matters>
---"""
        
        try:
            response = model_fn(prompt)
            return self._parse_llm_insights(response, node_ids, "[think cycle]")
        except Exception as e:
            print(f"  ⚠️ Contradiction reasoning failed: {e}")
            return []
    
    def _reason_about_leaves(self, leaf_nodes: List[tuple], model_fn: Callable) -> List[NewThought]:
        """Analyze leaf nodes for extension opportunities via LLM."""
        if not leaf_nodes:
            return []
        
        node_contents = "\n".join([f"- [{node[0]}] {node[1]}" for node in leaf_nodes])
        node_ids = [node[0] for node in leaf_nodes]
        
        prompt = f"""You are analyzing leaf nodes in a knowledge graph — these are thoughts with no outgoing connections. They represent endpoints of reasoning chains that haven't been extended.

LEAF NODES:
{node_contents}

Task: Pick 2-3 of these leaves that could be meaningfully extended. For each, generate an insight that extends the reasoning or connects it to a broader pattern. Don't force connections that don't exist.

These are YOUR analytical observations, not the person's beliefs.

Format each as:
INSIGHT: <your extension or connection>
CONFIDENCE: <0.5-0.9>
REASONING: <what this extends and why>
---"""
        
        try:
            response = model_fn(prompt)
            return self._parse_llm_insights(response, node_ids, "[think cycle]")
        except Exception as e:
            print(f"  ⚠️ Leaf reasoning failed: {e}")
            return []
    
    def _reason_about_questions(self, question_nodes: List[tuple], model_fn: Callable) -> List[NewThought]:
        """Analyze question nodes for potential answers or deeper questions via LLM."""
        if not question_nodes:
            return []
        
        node_contents = "\n".join([f"- [{node[0]}] {node[1]}" for node in question_nodes])
        node_ids = [node[0] for node in question_nodes]
        
        prompt = f"""You are analyzing open question nodes in a knowledge graph — these are unresolved questions the person has been thinking about.

QUESTION NODES:
{node_contents}

Task: For 1-2 of these questions, either:
(a) Propose a hypothesis based on patterns visible in the question itself
(b) Reframe the question to reveal a hidden assumption
(c) Suggest the question contains a false binary

These are YOUR analytical observations, not the person's beliefs.

Format each as:
INSIGHT: <your hypothesis, reframe, or observation>
CONFIDENCE: <0.5-0.9>
REASONING: <what prompted this and why>
---"""
        
        try:
            response = model_fn(prompt)
            return self._parse_llm_insights(response, node_ids, "[think cycle]")
        except Exception as e:
            print(f"  ⚠️ Question reasoning failed: {e}")
            return []
    
    def _generate_cross_domain_connections(self, analysis: Dict, model_fn: Callable) -> List[NewThought]:
        """Generate insights connecting different domains in the graph via LLM."""
        # Combine a sample from different categories for cross-pollination
        all_nodes = []
        for key in ['hub_nodes', 'leaf_nodes', 'question_nodes']:
            for node in analysis.get(key, [])[:3]:
                all_nodes.append(node)
        
        if len(all_nodes) < 3:
            return []
        
        node_contents = "\n".join([f"- [{node[0]}] {node[1]}" for node in all_nodes])
        node_ids = [node[0] for node in all_nodes]
        
        prompt = f"""You are looking at nodes from different parts of a personal knowledge graph — hubs, leaves, and questions mixed together. These come from different domains and reasoning chains.

MIXED NODES:
{node_contents}

Task: Find 1-2 genuine cross-domain connections. These should be non-obvious patterns where an insight in one domain illuminates something in another. Do NOT force connections — if nothing connects, say so.

These are YOUR analytical observations, not the person's beliefs.

Format each as:
INSIGHT: <the cross-domain connection>
CONFIDENCE: <0.5-0.9>
REASONING: <which domains connect and why>
---

If no genuine connections exist, respond with just: NO_CONNECTIONS"""
        
        try:
            response = model_fn(prompt)
            if 'NO_CONNECTIONS' in response:
                return []
            return self._parse_llm_insights(response, node_ids, "[cross-domain insight]")
        except Exception as e:
            print(f"  ⚠️ Cross-domain reasoning failed: {e}")
            return []
    
    def save_insights_to_db(self, insights: List[NewThought]) -> int:
        """Save new thoughts and their edges to the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        saved_count = 0
        timestamp = self._get_current_timestamp()
        
        # Load embeddings once before the loop for performance
        try:
            from core.placement_aware_extraction import check_novelty, load_all_embeddings
            preloaded_embeddings = load_all_embeddings(self.db_path)
        except Exception as e:
            print(f"  ⚠️ Failed to preload embeddings, falling back to per-call loading: {e}")
            preloaded_embeddings = None
        
        for insight in insights:
            # Primary gate: semantic novelty check
            try:
                if preloaded_embeddings is not None:
                    is_novel, max_sim, nearest_id = check_novelty(self.db_path, insight.content, 
                                                                preloaded_embeddings=preloaded_embeddings)
                else:
                    is_novel, max_sim, nearest_id = check_novelty(self.db_path, insight.content)
                if not is_novel:
                    print(f"  ⊘ Rejecting duplicate think insight (sim={max_sim:.3f}): {insight.content[:60]}")
                    continue
                # Borderline + low confidence = skip
                if max_sim > 0.72 and insight.confidence < 0.7:
                    print(f"  ⊘ Rejecting borderline think insight (sim={max_sim:.3f}, conf={insight.confidence}): {insight.content[:60]}")
                    continue
            except Exception as e:
                print(f"  ⚠️ Novelty check failed, falling back to exact match: {e}")
                
            # Generate node ID
            node_id = self._generate_node_id(insight.content)
            
            # Check if this content already exists (exact match fallback)
            cursor.execute("SELECT id FROM thought_nodes WHERE content = ?", (insight.content,))
            if cursor.fetchone():
                continue  # Skip exact duplicate content
            
            # Insert the new thought node — always bunny domain with source_file=system_generated
            insight_content = insight.content
            if not insight_content.startswith("[cross-domain insight]") and not insight_content.startswith("[think cycle]"):
                insight_content = f"[think cycle] {insight_content}"
            try:
                cursor.execute("""
                    INSERT INTO thought_nodes 
                    (id, content, node_type, timestamp, confidence, source_file, last_updated, domain)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (node_id, insight_content, 'derived', timestamp, insight.confidence, 'system_generated', timestamp, 'bunny'))
                
                # Create edges to parent nodes
                for parent_id in insight.parent_ids:
                    cursor.execute("""
                        INSERT OR IGNORE INTO derivation_edges 
                        (parent_id, child_id, weight, reasoning)
                        VALUES (?, ?, ?, ?)
                    """, (parent_id, node_id, 0.8, insight.reasoning))
                
                saved_count += 1
                
            except sqlite3.Error as e:
                print(f"Error saving insight: {e}")
                continue
        
        conn.commit()
        conn.close()
        return saved_count
    
    def run_think_cycle(self, model_fn: Callable = None) -> Dict:
        """Run a complete think cycle.
        
        Args:
            model_fn: Callable (prompt_str) -> response_str for LLM reasoning.
                      If None, insight generation is skipped.
        """
        print("🧠 Starting think cycle...")
        
        # Get initial counts
        from .stats import get_total_node_count, get_think_node_count
        conn = self._get_connection()
        cursor = conn.cursor()
        initial_count = get_total_node_count(cursor, include_decayed=True)
        initial_system_count = get_think_node_count(cursor)
        conn.close()
        
        print(f"📊 Initial state: {initial_count} total nodes, {initial_system_count} system_generated")
        
        # Analyze graph structure (random sampling)
        print("🔍 Analyzing graph structure (random sample)...")
        analysis = self.analyze_graph_structure()
        
        # Log what was sampled
        for key in ['hub_nodes', 'contradiction_nodes', 'leaf_nodes', 'question_nodes']:
            count = len(analysis.get(key, []))
            print(f"  📋 {key}: {count} sampled")
        
        # Generate insights via LLM
        print("💡 Generating new insights via LLM...")
        insights = self.generate_insights_from_analysis(analysis, model_fn=model_fn)
        print(f"Generated {len(insights)} potential insights")
        
        # Save to database
        print("💾 Saving insights to database...")
        saved_count = self.save_insights_to_db(insights)
        
        # Get final counts
        conn = self._get_connection()
        cursor = conn.cursor()
        final_count = get_total_node_count(cursor, include_decayed=True)
        final_system_count = get_think_node_count(cursor)
        conn.close()
        
        # Sample of best new thoughts
        best_insights = sorted(insights[:saved_count], key=lambda x: x.confidence, reverse=True)[:5]
        
        result = {
            'initial_count': initial_count,
            'final_count': final_count,
            'initial_system_count': initial_system_count,
            'final_system_count': final_system_count,
            'new_thoughts_generated': saved_count,
            'best_insights': [{'content': i.content, 'confidence': i.confidence} for i in best_insights]
        }
        
        print("✅ Think cycle complete!")
        return result


def run_think_cycle(db_path: str = None, model_fn: Callable = None) -> Dict:
    """Module-level convenience function, matching sleep.py's pattern."""
    cycle = ThinkCycle(db_path)
    return cycle.run_think_cycle(model_fn=model_fn)


if __name__ == "__main__":
    cycle = ThinkCycle()
    result = cycle.run_think_cycle()
    
    print(f"\n📈 Results:")
    print(f"  Total nodes: {result['initial_count']} → {result['final_count']}")
    print(f"  System nodes: {result['initial_system_count']} → {result['final_system_count']}")
    print(f"  New thoughts: {result['new_thoughts_generated']}")
    
    print(f"\n🌟 Best new insights:")
    for i, insight in enumerate(result['best_insights'], 1):
        print(f"  {i}. [{insight['confidence']:.2f}] {insight['content'][:100]}...")
