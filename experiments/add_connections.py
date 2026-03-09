#!/usr/bin/env python3

import sqlite3
import hashlib
from datetime import datetime

# Database connection
def get_db():
    return sqlite3.connect('/Users/bunny/.openclaw/workspace/cashew/data/apologetics-graph.db')

def add_edge(source_id, target_id, relation, reasoning):
    """Add an edge between two nodes"""
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO argument_edges 
            (source_id, target_id, relation, reasoning)
            VALUES (?, ?, ?, ?)
        """, (source_id, target_id, relation, reasoning))
        db.commit()
        return True
    except Exception as e:
        print(f"Error adding edge: {e}")
        return False
    finally:
        db.close()

def find_node_by_content_fragment(fragment):
    """Find nodes containing a specific content fragment"""
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute("""
            SELECT id, content FROM argument_nodes 
            WHERE content LIKE ?
            LIMIT 5
        """, (f'%{fragment}%',))
        results = cursor.fetchall()
        return results
    except Exception as e:
        print(f"Error finding nodes: {e}")
        return []
    finally:
        db.close()

def add_cross_connections():
    """Add connections between related arguments to increase cyclomatic complexity"""
    print("Adding cross-connections to increase cyclomatic complexity...")
    
    # Connect resurrection to prophecy (Jesus fulfills Isaiah 53)
    resurrection_nodes = find_node_by_content_fragment("Jesus Christ rose bodily")
    isaiah53_nodes = find_node_by_content_fragment("Isaiah 53 describes suffering servant")
    
    if resurrection_nodes and isaiah53_nodes:
        add_edge(isaiah53_nodes[0][0], resurrection_nodes[0][0], "supports", 
                "Suffering servant prophecy predicts death and resurrection")
    
    # Connect problem of evil to divine hiddenness
    evil_nodes = find_node_by_content_fragment("evil should not exist")
    hiddenness_nodes = find_node_by_content_fragment("God would make His existence obvious")
    
    if evil_nodes and hiddenness_nodes:
        add_edge(evil_nodes[0][0], hiddenness_nodes[0][0], "supports", 
                "If evil exists, God's hiddenness is even more problematic")
    
    # Connect free will defense to multiple areas
    freewill_nodes = find_node_by_content_fragment("free will is so valuable")
    hell_choice_nodes = find_node_by_content_fragment("natural consequence of free choice")
    epistemic_distance_nodes = find_node_by_content_fragment("epistemic distance to preserve")
    
    if freewill_nodes:
        if hell_choice_nodes:
            add_edge(freewill_nodes[0][0], hell_choice_nodes[0][0], "supports",
                    "Free will defense applies to hell as chosen consequence")
        if epistemic_distance_nodes:
            add_edge(freewill_nodes[0][0], epistemic_distance_nodes[0][0], "supports",
                    "Free will requires epistemic distance from God")
    
    # Connect natural revelation to design arguments (find cosmological args)
    natural_rev_nodes = find_node_by_content_fragment("revealed Himself through creation")
    
    # Look for existing cosmological arguments to connect to
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, content FROM argument_nodes WHERE category = 'cosmological' LIMIT 3")
    cosmo_args = cursor.fetchall()
    db.close()
    
    if natural_rev_nodes and cosmo_args:
        for cosmo_arg in cosmo_args:
            add_edge(cosmo_arg[0], natural_rev_nodes[0][0], "supports",
                    "Cosmological evidence supports natural revelation")
    
    # Connect Trinity to incarnation more explicitly
    trinity_nodes = find_node_by_content_fragment("three persons")
    incarnation_nodes = find_node_by_content_fragment("fully God and fully human")
    
    if trinity_nodes and incarnation_nodes:
        add_edge(trinity_nodes[0][0], incarnation_nodes[0][0], "requires",
                "Trinity doctrine necessary for incarnation doctrine")
    
    # Connect atonement theories to each other (competing explanations)
    penal_sub_nodes = find_node_by_content_fragment("penal substitute")
    moral_influence_nodes = find_node_by_content_fragment("demonstrates God's love")
    christus_victor_nodes = find_node_by_content_fragment("defeats Satan")
    
    if penal_sub_nodes and moral_influence_nodes:
        add_edge(moral_influence_nodes[0][0], penal_sub_nodes[0][0], "if_objection",
                "Moral influence challenges necessity of penal substitution")
    
    if penal_sub_nodes and christus_victor_nodes:
        add_edge(christus_victor_nodes[0][0], penal_sub_nodes[0][0], "supports",
                "Victory over Satan complements penal satisfaction")
    
    # Connect resurrection to atonement
    if resurrection_nodes and penal_sub_nodes:
        add_edge(resurrection_nodes[0][0], penal_sub_nodes[0][0], "supports",
                "Resurrection vindicates atoning sacrifice")
    
    # Connect hell doctrines to problem of evil
    eternal_torment_nodes = find_node_by_content_fragment("eternal conscious torment")
    if eternal_torment_nodes and evil_nodes:
        add_edge(eternal_torment_nodes[0][0], evil_nodes[0][0], "supports",
                "Eternal punishment adds to problem of evil")
    
    # Connect young earth to problem of evil (natural disasters in short timeframe)
    yec_nodes = find_node_by_content_fragment("6,000 years old")
    natural_evil_nodes = find_node_by_content_fragment("Natural disasters")
    
    if yec_nodes and natural_evil_nodes:
        add_edge(yec_nodes[0][0], natural_evil_nodes[0][0], "if_objection", 
                "Young earth makes natural evil timeline more problematic")
    
    # Create some circular dependencies for complexity
    
    # Connect skeptical arguments to each other
    hallucination_nodes = find_node_by_content_fragment("experienced hallucinations")
    legend_nodes = find_node_by_content_fragment("developed as legends")
    
    if hallucination_nodes and legend_nodes:
        add_edge(hallucination_nodes[0][0], legend_nodes[0][0], "supports",
                "Hallucinations could lead to legendary development")
        add_edge(legend_nodes[0][0], hallucination_nodes[0][0], "supports", 
                "Legends could create expectation leading to hallucinations")
    
    # Connect biblical reliability to multiple arguments
    manuscript_nodes = find_node_by_content_fragment("manuscript attestation")
    eyewitness_nodes = find_node_by_content_fragment("based on eyewitness testimony")
    
    if manuscript_nodes:
        # Connect to resurrection evidence
        if resurrection_nodes:
            add_edge(manuscript_nodes[0][0], resurrection_nodes[0][0], "supports",
                    "Manuscript reliability supports resurrection accounts")
        # Connect to prophecy fulfillment
        prophecy_nodes = find_node_by_content_fragment("prophecies were fulfilled")
        if prophecy_nodes:
            add_edge(manuscript_nodes[0][0], prophecy_nodes[0][0], "supports",
                    "Textual reliability supports prophecy accounts")
    
    # Connect cherry-picking objection to multiple apologetic arguments
    cherry_pick_nodes = find_node_by_content_fragment("only cite conservative scholars")
    
    if cherry_pick_nodes:
        if resurrection_nodes:
            add_edge(cherry_pick_nodes[0][0], resurrection_nodes[0][0], "if_objection",
                    "Scholar selection bias questions resurrection argument")
        if prophecy_nodes:
            add_edge(cherry_pick_nodes[0][0], prophecy_nodes[0][0], "if_objection",
                    "Scholar selection bias questions prophecy fulfillment")
    
    # Add some assumption dependencies
    biblical_inerrancy_nodes = find_node_by_content_fragment("literal")
    
    if biblical_inerrancy_nodes:
        # YEC assumes biblical literalism
        if yec_nodes:
            add_edge(yec_nodes[0][0], biblical_inerrancy_nodes[0][0], "assumes",
                    "Young earth creationism assumes literal biblical interpretation")
        
        # Prophecy fulfillment may assume inerrancy
        if prophecy_nodes:
            add_edge(prophecy_nodes[0][0], biblical_inerrancy_nodes[0][0], "assumes",
                    "Prophecy argument assumes reliable biblical text")
    
    # Connect good/evil standard to moral argument (find moral arguments)
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, content FROM argument_nodes WHERE category = 'moral' LIMIT 3")
    moral_args = cursor.fetchall()
    db.close()
    
    if moral_args and evil_nodes:
        for moral_arg in moral_args:
            add_edge(evil_nodes[0][0], moral_arg[0], "if_objection",
                    "Problem of evil challenges objective moral standard")
    
    print("Cross-connections added!")

def calculate_cyclomatic_complexity():
    """Calculate the cyclomatic complexity of the argument graph"""
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Count nodes and edges
        cursor.execute("SELECT COUNT(*) FROM argument_nodes")
        N = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM argument_edges")  
        E = cursor.fetchone()[0]
        
        # For argument graphs, we can treat it as one connected component
        P = 1
        
        # Cyclomatic complexity = E - N + 2P
        CC = E - N + 2*P
        
        print(f"Updated graph statistics:")
        print(f"  Nodes (N): {N}")
        print(f"  Edges (E): {E}")
        print(f"  Components (P): {P}")
        print(f"  Cyclomatic Complexity: {CC}")
        
        return CC
        
    except Exception as e:
        print(f"Error calculating complexity: {e}")
        return None
    finally:
        db.close()

if __name__ == "__main__":
    add_cross_connections()
    final_cc = calculate_cyclomatic_complexity()
    
    if final_cc and final_cc > 16:
        print(f"✅ SUCCESS! Cyclomatic complexity increased to {final_cc}")
    else:
        print(f"Need more cycles. Current CC: {final_cc}")