#!/usr/bin/env python3
"""
Script to populate the apologetics argument graph database with structured arguments,
objections, and responses from major Christian apologetics sources.
"""

import sqlite3
import uuid
from typing import List, Tuple, Dict

def generate_node_id(prefix: str = "node") -> str:
    """Generate a unique node ID."""
    return f"{prefix}_{str(uuid.uuid4())[:8]}"

def add_node(cursor: sqlite3.Cursor, content: str, node_type: str, source: str, category: str) -> str:
    """Add a node to the database and return its ID."""
    node_id = generate_node_id()
    cursor.execute(
        "INSERT INTO argument_nodes (id, content, node_type, source, category) VALUES (?, ?, ?, ?, ?)",
        (node_id, content, node_type, source, category)
    )
    return node_id

def add_edge(cursor: sqlite3.Cursor, source_id: str, target_id: str, relation: str, reasoning: str = ""):
    """Add an edge to the database."""
    cursor.execute(
        "INSERT OR IGNORE INTO argument_edges (source_id, target_id, relation, reasoning) VALUES (?, ?, ?, ?)",
        (source_id, target_id, relation, reasoning)
    )

def populate_kalam_argument(cursor: sqlite3.Cursor) -> Dict[str, str]:
    """Populate the Kalam Cosmological Argument structure."""
    # Core premises and conclusion
    premise1_id = add_node(cursor, "Everything that begins to exist has a cause", "premise", "William Lane Craig", "cosmological")
    premise2_id = add_node(cursor, "The universe began to exist", "premise", "William Lane Craig", "cosmological")
    conclusion1_id = add_node(cursor, "Therefore, the universe has a cause", "conclusion", "William Lane Craig", "cosmological")
    
    # Logical dependencies
    add_edge(cursor, premise1_id, conclusion1_id, "supports", "First premise supports conclusion via universal causal principle")
    add_edge(cursor, premise2_id, conclusion1_id, "supports", "Second premise supports conclusion by establishing universe's beginning")
    
    # Conceptual analysis (Craig's extension)
    premise3_id = add_node(cursor, "If the universe has a cause, then an uncaused, personal Creator exists", "premise", "William Lane Craig", "cosmological")
    conclusion2_id = add_node(cursor, "Therefore, an uncaused, personal Creator exists", "conclusion", "William Lane Craig", "cosmological")
    
    add_edge(cursor, conclusion1_id, premise3_id, "supports", "First conclusion feeds into conceptual analysis")
    add_edge(cursor, premise3_id, conclusion2_id, "supports", "Conceptual analysis yields personal Creator")
    
    # Major objections and responses
    
    # Objections to Premise 1
    quantum_obj = add_node(cursor, "Quantum events appear uncaused (quantum indeterminacy)", "objection", "Paul Davies / Quantum Physics", "cosmological")
    quantum_resp = add_node(cursor, "Quantum events have necessary conditions even if not sufficient causes", "response", "William Lane Craig", "cosmological")
    add_edge(cursor, quantum_obj, premise1_id, "if_objection", "Challenges universal causation principle")
    add_edge(cursor, premise1_id, quantum_resp, "then_response", "Response to quantum objection")
    
    vacuum_obj = add_node(cursor, "Virtual particles emerge from quantum vacuum without cause", "objection", "Lawrence Krauss / Quentin Smith", "cosmological")
    vacuum_resp = add_node(cursor, "Quantum vacuum is not 'nothing' but energetic medium with physical laws", "response", "William Lane Craig", "cosmological")
    add_edge(cursor, vacuum_obj, premise1_id, "if_objection", "Vacuum fluctuations as counterexample")
    add_edge(cursor, premise1_id, vacuum_resp, "then_response", "Vacuum is not true nothing")
    
    hume_obj = add_node(cursor, "Effects without causes are conceivable (Hume)", "objection", "David Hume / J.L. Mackie", "cosmological")
    hume_resp = add_node(cursor, "Conceivability doesn't establish real possibility; Hume himself believed in causation", "response", "William Lane Craig", "cosmological")
    add_edge(cursor, hume_obj, premise1_id, "if_objection", "Challenges necessary connection between cause and effect")
    add_edge(cursor, premise1_id, hume_resp, "then_response", "Conceivability vs. real possibility distinction")
    
    # Objections to Premise 2
    bgt_obj = add_node(cursor, "Borde-Guth-Vilenkin theorem applies only to classical spacetime", "objection", "Sean Carroll", "cosmological")
    bgt_resp = add_node(cursor, "Even quantum pre-classical regions cannot exist timelessly due to instability", "response", "William Lane Craig", "cosmological")
    add_edge(cursor, bgt_obj, premise2_id, "if_objection", "BGV theorem limitations")
    add_edge(cursor, premise2_id, bgt_resp, "then_response", "Quantum instability argument")
    
    eternal_obj = add_node(cursor, "Emergent/cyclic models avoid beginning", "objection", "Various cosmologists", "cosmological")
    eternal_resp = add_node(cursor, "Such models violate thermodynamics or remain subject to BGV theorem", "response", "William Lane Craig", "cosmological")
    add_edge(cursor, eternal_obj, premise2_id, "if_objection", "Alternative cosmological models")
    add_edge(cursor, premise2_id, eternal_resp, "then_response", "Thermodynamic and BGV constraints")
    
    # Circular dependency example
    time_obj = add_node(cursor, "Causation requires time, but universe creates time", "objection", "Adolf Grünbaum", "cosmological")
    time_resp = add_node(cursor, "Agent causation by timeless being can create first temporal effect", "response", "William Lane Craig", "cosmological")
    add_edge(cursor, time_obj, conclusion1_id, "if_objection", "Temporal causation paradox")
    add_edge(cursor, conclusion1_id, time_resp, "then_response", "Agent causation solution")
    
    # This creates a potential circular dependency where the conclusion depends on assumptions that depend on the conclusion
    add_edge(cursor, time_resp, premise3_id, "circular_dep", "Agent causation response assumes personal causation")
    
    return {
        'premise1': premise1_id,
        'premise2': premise2_id,
        'conclusion1': conclusion1_id,
        'conclusion2': conclusion2_id
    }

def populate_lewis_trilemma(cursor: sqlite3.Cursor) -> Dict[str, str]:
    """Populate C.S. Lewis's trilemma (Liar, Lunatic, or Lord)."""
    # Core assumption and premises
    assumption_id = add_node(cursor, "Jesus claimed to be God", "assumption", "C.S. Lewis", "historical")
    premise1_id = add_node(cursor, "Jesus was either lying about being God, deluded about being God, or actually God", "premise", "C.S. Lewis", "historical")
    premise2_id = add_node(cursor, "Jesus was not a liar (good moral character)", "premise", "C.S. Lewis", "historical")
    premise3_id = add_node(cursor, "Jesus was not a lunatic (rational teaching and behavior)", "premise", "C.S. Lewis", "historical")
    conclusion_id = add_node(cursor, "Therefore, Jesus is God", "conclusion", "C.S. Lewis", "historical")
    
    # Dependencies
    add_edge(cursor, assumption_id, premise1_id, "requires", "Trilemma depends on divinity claims")
    add_edge(cursor, premise1_id, conclusion_id, "supports", "Elimination leads to divine conclusion")
    add_edge(cursor, premise2_id, conclusion_id, "supports", "Eliminates liar option")
    add_edge(cursor, premise3_id, conclusion_id, "supports", "Eliminates lunatic option")
    
    # Major objections and responses
    
    # False trilemma objection
    legend_obj = add_node(cursor, "Fourth option: Jesus is legendary (claims invented by later Christians)", "objection", "Critical scholars / William Lane Craig", "historical")
    legend_resp = add_node(cursor, "Gospel accounts are not legends based on literary analysis", "response", "C.S. Lewis", "historical")
    add_edge(cursor, legend_obj, premise1_id, "if_objection", "Additional option breaks trilemma")
    add_edge(cursor, premise1_id, legend_resp, "then_response", "Literary genre defense")
    
    claims_obj = add_node(cursor, "Scholarly consensus: Jesus did not claim to be God", "objection", "John Hick / Bart Ehrman", "historical")
    claims_resp = add_node(cursor, "Conservative scholars disagree; Bible taken at face value shows divine claims", "response", "Donald Williams", "historical")
    add_edge(cursor, claims_obj, assumption_id, "if_objection", "Challenges fundamental assumption")
    add_edge(cursor, assumption_id, claims_resp, "then_response", "Conservative biblical interpretation")
    
    # This creates a circular dependency where the response assumes what needs to be proven
    add_edge(cursor, claims_resp, assumption_id, "circular_dep", "Response assumes biblical accuracy which assumes divine claims")
    
    prophet_obj = add_node(cursor, "Jesus could be a great prophet without being God", "objection", "Craig Evans", "historical")
    prophet_resp = add_node(cursor, "Divine claims preclude merely prophetic status", "response", "C.S. Lewis defenders", "historical")
    add_edge(cursor, prophet_obj, premise1_id, "if_objection", "Additional option: great prophet")
    add_edge(cursor, premise1_id, prophet_resp, "then_response", "Claims too extreme for prophet")
    
    return {
        'assumption': assumption_id,
        'conclusion': conclusion_id
    }

def populate_moral_argument(cursor: sqlite3.Cursor) -> Dict[str, str]:
    """Populate William Lane Craig's moral argument."""
    premise1_id = add_node(cursor, "If God does not exist, objective moral values do not exist", "premise", "William Lane Craig", "moral")
    premise2_id = add_node(cursor, "Objective moral values do exist", "premise", "William Lane Craig", "moral")
    conclusion_id = add_node(cursor, "Therefore, God exists", "conclusion", "William Lane Craig", "moral")
    
    add_edge(cursor, premise1_id, conclusion_id, "supports", "Modus tollens: if no God, no objective morality")
    add_edge(cursor, premise2_id, conclusion_id, "supports", "Objective morality exists")
    
    # Objections and responses
    grounding_obj = add_node(cursor, "Evolution can ground objective morality", "objection", "Naturalistic ethicists", "moral")
    grounding_resp = add_node(cursor, "Evolution explains genesis of moral beliefs, not ontological foundation", "response", "William Lane Craig", "moral")
    add_edge(cursor, grounding_obj, premise1_id, "if_objection", "Naturalistic alternative to theistic grounding")
    add_edge(cursor, premise1_id, grounding_resp, "then_response", "Genesis vs ontology distinction")
    
    euthyphro_obj = add_node(cursor, "Divine command theory faces Euthyphro dilemma", "objection", "Plato / Modern critics", "moral")
    euthyphro_resp = add_node(cursor, "God's nature provides ontological foundation, commands provide epistemic access", "response", "William Lane Craig", "moral")
    add_edge(cursor, euthyphro_obj, premise1_id, "if_objection", "Problems with divine command theory")
    add_edge(cursor, premise1_id, euthyphro_resp, "then_response", "Nature vs command distinction")
    
    return {
        'premise1': premise1_id,
        'conclusion': conclusion_id
    }

def populate_plantinga_reformed_epistemology(cursor: sqlite3.Cursor) -> Dict[str, str]:
    """Populate Alvin Plantinga's Reformed epistemology."""
    premise1_id = add_node(cursor, "Belief in God can be properly basic (warrant without evidence)", "premise", "Alvin Plantinga", "epistemological")
    premise2_id = add_node(cursor, "Properly basic beliefs are rational if produced by properly functioning cognitive faculties", "premise", "Alvin Plantinga", "epistemological")
    premise3_id = add_node(cursor, "God designed cognitive faculties with sensus divinitatis", "premise", "Alvin Plantinga", "epistemological")
    conclusion_id = add_node(cursor, "Therefore, belief in God can be rational without arguments", "conclusion", "Alvin Plantinga", "epistemological")
    
    add_edge(cursor, premise1_id, conclusion_id, "supports", "Basic belief status confers rationality")
    add_edge(cursor, premise2_id, conclusion_id, "supports", "Proper function theory")
    add_edge(cursor, premise3_id, premise2_id, "supports", "Design plan includes divine awareness")
    
    # Objections and responses
    pumpkin_obj = add_node(cursor, "Great Pumpkin objection: any belief could be properly basic", "objection", "Critics", "epistemological")
    pumpkin_resp = add_node(cursor, "Objection assumes classical foundationalist criteria are exhaustive", "response", "Alvin Plantinga", "epistemological")
    add_edge(cursor, pumpkin_obj, premise1_id, "if_objection", "Unlimited basicality problem")
    add_edge(cursor, premise1_id, pumpkin_resp, "then_response", "Classical foundationalism critique")
    
    naturalistic_obj = add_node(cursor, "Naturalistic explanations exist for religious experience", "objection", "Justin Barrett", "epistemological")
    naturalistic_resp = add_node(cursor, "Genesis of belief doesn't undermine warrant if properly functioning", "response", "Alvin Plantinga", "epistemological")
    add_edge(cursor, naturalistic_obj, premise3_id, "if_objection", "Natural origins of religious belief")
    add_edge(cursor, premise3_id, naturalistic_resp, "then_response", "Warrant independent of genesis")
    
    # Circular dependency
    add_edge(cursor, premise3_id, conclusion_id, "circular_dep", "Design assumption requires theism to warrant theistic belief")
    
    return {
        'conclusion': conclusion_id
    }

def populate_aquinas_five_ways(cursor: sqlite3.Cursor) -> Dict[str, str]:
    """Populate Thomas Aquinas's Five Ways."""
    
    # First Way: Motion/Change
    motion_premise1 = add_node(cursor, "Some things are changing (potency to act)", "premise", "Thomas Aquinas", "cosmological")
    motion_premise2 = add_node(cursor, "Whatever is changing is being changed by something else", "premise", "Thomas Aquinas", "cosmological")
    motion_premise3 = add_node(cursor, "Infinite regress of movers is impossible", "premise", "Thomas Aquinas", "cosmological")
    motion_conclusion = add_node(cursor, "Therefore, there must be a first unmoved mover (God)", "conclusion", "Thomas Aquinas", "cosmological")
    
    add_edge(cursor, motion_premise1, motion_conclusion, "supports", "Observation of change")
    add_edge(cursor, motion_premise2, motion_conclusion, "supports", "Causal principle for change")
    add_edge(cursor, motion_premise3, motion_conclusion, "supports", "Infinite regress impossibility")
    
    # Second Way: Efficient Cause
    cause_premise1 = add_node(cursor, "Some things are caused", "premise", "Thomas Aquinas", "cosmological")
    cause_premise2 = add_node(cursor, "Nothing can be the cause of itself", "premise", "Thomas Aquinas", "cosmological")
    cause_premise3 = add_node(cursor, "Infinite regress of efficient causes is impossible", "premise", "Thomas Aquinas", "cosmological")
    cause_conclusion = add_node(cursor, "Therefore, there must be a first efficient cause (God)", "conclusion", "Thomas Aquinas", "cosmological")
    
    add_edge(cursor, cause_premise1, cause_conclusion, "supports", "Observation of causation")
    add_edge(cursor, cause_premise2, cause_conclusion, "supports", "Self-causation impossibility")
    add_edge(cursor, cause_premise3, cause_conclusion, "supports", "Infinite regress impossibility")
    
    # Third Way: Contingency
    contingency_premise1 = add_node(cursor, "Things exist that are possible-to-be and possible-not-to-be", "premise", "Thomas Aquinas", "cosmological")
    contingency_premise2 = add_node(cursor, "If everything were contingent, nothing would exist now", "premise", "Thomas Aquinas", "cosmological")
    contingency_premise3 = add_node(cursor, "Things exist now", "premise", "Thomas Aquinas", "cosmological")
    contingency_conclusion = add_node(cursor, "Therefore, there must be a necessary being (God)", "conclusion", "Thomas Aquinas", "cosmological")
    
    add_edge(cursor, contingency_premise1, contingency_conclusion, "supports", "Observation of contingent beings")
    add_edge(cursor, contingency_premise2, contingency_conclusion, "supports", "Contingency leads to nothing")
    add_edge(cursor, contingency_premise3, contingency_conclusion, "supports", "Something exists")
    
    # Fourth Way: Degrees of Perfection
    degree_premise1 = add_node(cursor, "Things have degrees of goodness, truth, and nobility", "premise", "Thomas Aquinas", "moral")
    degree_premise2 = add_node(cursor, "Degrees imply a maximum standard", "premise", "Thomas Aquinas", "moral")
    degree_premise3 = add_node(cursor, "The maximum in a genus is the cause of all others in that genus", "premise", "Thomas Aquinas", "moral")
    degree_conclusion = add_node(cursor, "Therefore, there is a most perfect being (God)", "conclusion", "Thomas Aquinas", "moral")
    
    add_edge(cursor, degree_premise1, degree_conclusion, "supports", "Observation of gradations")
    add_edge(cursor, degree_premise2, degree_conclusion, "supports", "Degrees require maximum")
    add_edge(cursor, degree_premise3, degree_conclusion, "supports", "Maximum as cause")
    
    # Fifth Way: Teleological
    teleological_premise1 = add_node(cursor, "Non-intelligent things behave toward ends/goals", "premise", "Thomas Aquinas", "teleological")
    teleological_premise2 = add_node(cursor, "Goal-directed behavior requires intelligence to set the goal", "premise", "Thomas Aquinas", "teleological")
    teleological_premise3 = add_node(cursor, "Non-intelligent things cannot set their own goals", "premise", "Thomas Aquinas", "teleological")
    teleological_conclusion = add_node(cursor, "Therefore, there must be an intelligent designer (God)", "conclusion", "Thomas Aquinas", "teleological")
    
    add_edge(cursor, teleological_premise1, teleological_conclusion, "supports", "Observation of natural regularity")
    add_edge(cursor, teleological_premise2, teleological_conclusion, "supports", "Intelligence required for goals")
    add_edge(cursor, teleological_premise3, teleological_conclusion, "supports", "Non-intelligent can't self-direct")
    
    # Common objections to all Five Ways
    hume_objection = add_node(cursor, "Cannot infer causes beyond experience (Hume)", "objection", "David Hume", "cosmological")
    hume_response = add_node(cursor, "Arguments reason from effects to logically necessary causes", "response", "Thomistic defenders", "cosmological")
    
    kant_objection = add_node(cursor, "Cannot know noumenal realm beyond phenomena (Kant)", "objection", "Immanuel Kant", "cosmological")
    kant_response = add_node(cursor, "Thomistic metaphysics rejects Kantian phenomenal/noumenal distinction", "response", "Edward Feser", "cosmological")
    
    # Apply objections to multiple conclusions
    for conclusion in [motion_conclusion, cause_conclusion, contingency_conclusion]:
        add_edge(cursor, hume_objection, conclusion, "if_objection", "Challenges inference to transcendent cause")
        add_edge(cursor, conclusion, hume_response, "then_response", "Logical necessity defense")
        add_edge(cursor, kant_objection, conclusion, "if_objection", "Challenges knowability of God")
        add_edge(cursor, conclusion, kant_response, "then_response", "Metaphysical realism defense")
    
    return {
        'first_way': motion_conclusion,
        'second_way': cause_conclusion,
        'third_way': contingency_conclusion,
        'fourth_way': degree_conclusion,
        'fifth_way': teleological_conclusion
    }

def calculate_cyclomatic_complexity(cursor: sqlite3.Cursor) -> Dict[str, int]:
    """Calculate cyclomatic complexity and related metrics."""
    # Count nodes and edges
    cursor.execute("SELECT COUNT(*) FROM argument_nodes")
    nodes = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM argument_edges")
    edges = cursor.fetchone()[0]
    
    # Count objection-response pairs (escape hatches)
    cursor.execute("""
        SELECT COUNT(*) FROM argument_edges e1 
        JOIN argument_edges e2 ON e1.target_id = e2.source_id 
        WHERE e1.relation = 'if_objection' AND e2.relation = 'then_response'
    """)
    escape_hatches = cursor.fetchone()[0]
    
    # Count circular dependencies
    cursor.execute("SELECT COUNT(*) FROM argument_edges WHERE relation = 'circular_dep'")
    circular_dependencies = cursor.fetchone()[0]
    
    # Calculate branching factor (average outgoing edges per node)
    if nodes > 0:
        branching_factor = edges / nodes
    else:
        branching_factor = 0
    
    # Connected components (assuming the entire graph is connected for this analysis)
    connected_components = 1
    
    # Cyclomatic complexity: E - N + 2P
    cyclomatic_complexity = edges - nodes + 2 * connected_components
    
    # Calculate maximum depth (simplified - count longest path)
    # This is an approximation - true calculation would require graph traversal
    cursor.execute("""
        WITH RECURSIVE path_lengths AS (
            -- Base case: nodes with no incoming edges
            SELECT id, 0 as depth
            FROM argument_nodes 
            WHERE id NOT IN (SELECT DISTINCT target_id FROM argument_edges WHERE relation = 'supports')
            
            UNION ALL
            
            -- Recursive case: extend paths
            SELECT e.target_id, p.depth + 1
            FROM path_lengths p
            JOIN argument_edges e ON p.id = e.source_id
            WHERE e.relation = 'supports'
        )
        SELECT COALESCE(MAX(depth), 0) FROM path_lengths
    """)
    max_depth = cursor.fetchone()[0]
    
    return {
        'total_nodes': nodes,
        'total_edges': edges,
        'cyclomatic_complexity': cyclomatic_complexity,
        'branching_factor_avg': round(branching_factor, 2),
        'circular_dependencies': circular_dependencies,
        'max_depth': max_depth,
        'escape_hatches': escape_hatches
    }

def main():
    """Main function to populate the database."""
    db_path = "/Users/bunny/.openclaw/workspace/cashew/data/apologetics-graph.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Populating Kalam Cosmological Argument...")
        populate_kalam_argument(cursor)
        
        print("Populating Lewis's Trilemma...")
        populate_lewis_trilemma(cursor)
        
        print("Populating Moral Argument...")
        populate_moral_argument(cursor)
        
        print("Populating Plantinga's Reformed Epistemology...")
        populate_plantinga_reformed_epistemology(cursor)
        
        print("Populating Aquinas's Five Ways...")
        populate_aquinas_five_ways(cursor)
        
        print("Calculating metrics...")
        metrics = calculate_cyclomatic_complexity(cursor)
        
        print("\n=== APOLOGETICS ARGUMENT COMPLEXITY ANALYSIS ===")
        print(f"Total Nodes: {metrics['total_nodes']}")
        print(f"Total Edges: {metrics['total_edges']}")
        print(f"Cyclomatic Complexity: {metrics['cyclomatic_complexity']}")
        print(f"Average Branching Factor: {metrics['branching_factor_avg']}")
        print(f"Circular Dependencies: {metrics['circular_dependencies']}")
        print(f"Maximum Argument Depth: {metrics['max_depth']}")
        print(f"Escape Hatches (Objection→Response pairs): {metrics['escape_hatches']}")
        print("\nThe higher the cyclomatic complexity, the more branching paths and")
        print("exceptional cases the argument system contains.")
        
        conn.commit()
        print(f"\nDatabase populated successfully: {db_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()