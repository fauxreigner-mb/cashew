#!/usr/bin/env python3

import sqlite3
import hashlib
import json
from datetime import datetime

# Database connection
def get_db():
    return sqlite3.connect('/Users/bunny/.openclaw/workspace/cashew/data/apologetics-graph.db')

def generate_id(content):
    """Generate SHA256 hash of content, first 12 characters"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]

def add_node(content, node_type, source, category):
    """Add a node to the database"""
    db = get_db()
    cursor = db.cursor()
    
    node_id = generate_id(content)
    timestamp = datetime.now().isoformat()
    
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO argument_nodes 
            (id, content, node_type, source, category, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (node_id, content, node_type, source, category, timestamp))
        db.commit()
        return node_id
    except Exception as e:
        print(f"Error adding node: {e}")
        return None
    finally:
        db.close()

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
        """, (f'%{fragment}%',))
        results = cursor.fetchall()
        return results
    except Exception as e:
        print(f"Error finding nodes: {e}")
        return []
    finally:
        db.close()

# =============================================================================
# 1. RESURRECTION ARGUMENT
# =============================================================================

def add_resurrection_arguments():
    """Add William Lane Craig's resurrection argument"""
    print("Adding Resurrection Arguments...")
    
    # Main conclusion
    resurrection_conclusion = add_node(
        "Jesus Christ rose bodily from the dead",
        "conclusion",
        "William Lane Craig",
        "resurrection"
    )
    
    # The four facts
    fact1 = add_node(
        "Jesus died by crucifixion",
        "premise", 
        "Craig/Historical consensus",
        "resurrection"
    )
    
    fact2 = add_node(
        "Jesus was buried in a tomb by Joseph of Arimathea and the tomb was found empty",
        "premise",
        "Craig/Gospel accounts", 
        "resurrection"
    )
    
    fact3 = add_node(
        "Multiple groups and individuals experienced post-mortem appearances of Jesus",
        "premise",
        "Craig/1 Cor 15:3-8",
        "resurrection"
    )
    
    fact4 = add_node(
        "The Christian faith originated and exploded in first-century Jerusalem",
        "premise", 
        "Craig/Historical evidence",
        "resurrection"
    )
    
    # Connect facts to conclusion
    add_edge(fact1, resurrection_conclusion, "supports", "Death prerequisite for resurrection")
    add_edge(fact2, resurrection_conclusion, "supports", "Empty tomb indicates body was raised")  
    add_edge(fact3, resurrection_conclusion, "supports", "Appearances indicate Jesus was alive again")
    add_edge(fact4, resurrection_conclusion, "supports", "Origin of Christianity requires adequate explanation")
    
    # OBJECTIONS AND RESPONSES
    
    # Swoon theory
    swoon_objection = add_node(
        "Jesus didn't actually die but merely swooned and revived in the tomb",
        "objection",
        "Skeptics",
        "resurrection"
    )
    
    add_edge(swoon_objection, fact1, "if_objection", "Challenges the death of Jesus")
    
    swoon_response1 = add_node(
        "Medical evidence shows crucifixion causes death; impossible to survive",
        "response", 
        "Journal of American Medical Association",
        "resurrection"
    )
    
    swoon_response2 = add_node(
        "A half-dead Jesus could not inspire belief in glorious resurrection",
        "response",
        "David Friedrich Strauss", 
        "resurrection"
    )
    
    add_edge(swoon_response1, swoon_objection, "then_response", "Medical impossibility refutes swoon theory")
    add_edge(swoon_response2, swoon_objection, "then_response", "Psychological implausibility refutes swoon theory")
    
    # Stolen body theory  
    stolen_objection = add_node(
        "The disciples stole Jesus' body and fabricated the resurrection story",
        "objection",
        "Jewish authorities/Matthew 28:11-15",
        "resurrection"
    )
    
    add_edge(stolen_objection, fact2, "if_objection", "Alternative explanation for empty tomb")
    
    stolen_response1 = add_node(
        "Disciples died as martyrs for resurrection belief; liars make poor martyrs",
        "response",
        "Historical evidence/Craig",
        "resurrection" 
    )
    
    stolen_response2 = add_node(
        "No expectation of individual resurrection before general resurrection in Jewish thought",
        "response",
        "N.T. Wright/Craig",
        "resurrection"
    )
    
    add_edge(stolen_response1, stolen_objection, "then_response", "Martyrdom incompatible with conscious deception")
    add_edge(stolen_response2, stolen_objection, "then_response", "Culturally implausible motivation")
    
    # Hallucination theory
    hallucination_objection = add_node(
        "The disciples experienced hallucinations, not real appearances of Jesus",
        "objection",
        "Gerd Lüdemann/Skeptics",
        "resurrection"
    )
    
    add_edge(hallucination_objection, fact3, "if_objection", "Alternative explanation for appearances")
    
    hallucination_response1 = add_node(
        "Hallucinations are private experiences, cannot explain group appearances",
        "response",
        "Craig/Psychology",
        "resurrection"
    )
    
    hallucination_response2 = add_node(
        "Hallucinations cannot explain the empty tomb or converted skeptics",
        "response", 
        "Craig/Kreeft",
        "resurrection"
    )
    
    hallucination_response3 = add_node(
        "Jewish expectation would be visions of Jesus in heaven, not resurrection",
        "response",
        "Craig/Jewish beliefs",
        "resurrection"
    )
    
    add_edge(hallucination_response1, hallucination_objection, "then_response", "Group experiences rule out hallucinations")
    add_edge(hallucination_response2, hallucination_objection, "then_response", "Insufficient explanatory scope")
    add_edge(hallucination_response3, hallucination_objection, "then_response", "Wrong conceptual framework")
    
    # Wrong tomb theory
    wrong_tomb_objection = add_node(
        "The women went to the wrong tomb and found it empty",
        "objection",
        "Kirsopp Lake",
        "resurrection"
    )
    
    add_edge(wrong_tomb_objection, fact2, "if_objection", "Alternative explanation for empty tomb")
    
    wrong_tomb_response = add_node(
        "Jewish and Roman authorities could have produced the body from the correct tomb",
        "response",
        "Craig/Logic",
        "resurrection"
    )
    
    add_edge(wrong_tomb_response, wrong_tomb_objection, "then_response", "Authorities had motivation and means to correct error")
    
    # Legend development theory
    legend_objection = add_node(
        "The resurrection stories developed as legends over time",
        "objection", 
        "Mythicist scholars",
        "resurrection"
    )
    
    add_edge(legend_objection, fact3, "if_objection", "Alternative explanation for appearance accounts")
    
    legend_response = add_node(
        "1 Cor 15:3-8 creed dates to within 2-3 years of crucifixion; insufficient time for legend",
        "response",
        "Gerd Lüdemann/Early dating",
        "resurrection"
    )
    
    add_edge(legend_response, legend_objection, "then_response", "Early dating precludes legendary development")
    
    return resurrection_conclusion

# =============================================================================
# 2. FULFILLED PROPHECY
# =============================================================================

def add_prophecy_arguments():
    """Add fulfilled prophecy arguments"""
    print("Adding Fulfilled Prophecy Arguments...")
    
    # Main conclusion
    prophecy_conclusion = add_node(
        "Old Testament prophecies were fulfilled in Jesus Christ, demonstrating divine foreknowledge",
        "conclusion",
        "Christian apologetics",
        "prophecy"
    )
    
    # Specific prophecies
    psalm22_premise = add_node(
        "Psalm 22 describes crucifixion details: pierced hands/feet, casting lots for clothes, mocking",
        "premise",
        "Psalm 22/Gospel accounts", 
        "prophecy"
    )
    
    isaiah53_premise = add_node(
        "Isaiah 53 describes suffering servant: pierced for transgressions, silent before accusers, buried with rich",
        "premise",
        "Isaiah 53/Gospel accounts",
        "prophecy"
    )
    
    micah52_premise = add_node(
        "Micah 5:2 prophesies Messiah born in Bethlehem",
        "premise",
        "Micah 5:2/Matthew 2:1",
        "prophecy"
    )
    
    daniel_premise = add_node(
        "Daniel 9:24-27 prophesies timing of Messiah's coming and death",
        "premise",
        "Daniel 9/Historical calculation",
        "prophecy"
    )
    
    # Connect to conclusion
    add_edge(psalm22_premise, prophecy_conclusion, "supports", "Detailed prediction fulfilled precisely")
    add_edge(isaiah53_premise, prophecy_conclusion, "supports", "Suffering servant prophecy fulfilled") 
    add_edge(micah52_premise, prophecy_conclusion, "supports", "Birthplace correctly prophesied")
    add_edge(daniel_premise, prophecy_conclusion, "supports", "Timing prophecy fulfilled")
    
    # OBJECTIONS AND RESPONSES
    
    # Post-hoc writing objection
    posthoc_objection = add_node(
        "Prophecies were written after the events they claim to predict (vaticinium ex eventu)",
        "objection",
        "Critical scholars",
        "prophecy"
    )
    
    add_edge(posthoc_objection, isaiah53_premise, "if_objection", "Questions dating of Isaiah")
    add_edge(posthoc_objection, daniel_premise, "if_objection", "Questions dating of Daniel")
    
    posthoc_response1 = add_node(
        "Dead Sea Scrolls confirm pre-Christian dating of Isaiah and other prophetic texts",
        "response",
        "Archaeological evidence",
        "prophecy"
    )
    
    posthoc_response2 = add_node(
        "Even late dating still predates Jesus for most prophecies",
        "response", 
        "Textual criticism",
        "prophecy"
    )
    
    add_edge(posthoc_response1, posthoc_objection, "then_response", "Manuscript evidence confirms early dating")
    add_edge(posthoc_response2, posthoc_objection, "then_response", "Sufficient time gap remains")
    
    # Vague predictions objection
    vague_objection = add_node(
        "Prophecies are too vague and could apply to many people or situations",
        "objection",
        "Skeptics",
        "prophecy"
    )
    
    add_edge(vague_objection, psalm22_premise, "if_objection", "Questions specificity")
    add_edge(vague_objection, isaiah53_premise, "if_objection", "Questions specificity")
    
    vague_response = add_node(
        "Many prophecies contain highly specific details that match Jesus precisely",
        "response",
        "Statistical analysis",
        "prophecy" 
    )
    
    add_edge(vague_response, vague_objection, "then_response", "Specificity argues against coincidence")
    
    # Selective reading objection
    selective_objection = add_node(
        "Christians cherry-pick verses while ignoring context and failed predictions",
        "objection",
        "Critical scholars",
        "prophecy"
    )
    
    add_edge(selective_objection, prophecy_conclusion, "if_objection", "Questions methodology")
    
    selective_response = add_node(
        "Multiple independent prophecies from different authors and time periods converge on Jesus",
        "response",
        "Biblical scholars",
        "prophecy"
    )
    
    add_edge(selective_response, selective_objection, "then_response", "Pattern across multiple sources argues against cherry-picking")
    
    # Translation objection (almah vs bethulah)
    translation_objection = add_node(
        "Isaiah 7:14 uses 'almah' (young woman) not 'bethulah' (virgin); prophecy mistranslated",
        "objection",
        "Hebrew scholars",
        "prophecy"
    )
    
    virgin_premise = add_node(
        "Isaiah 7:14 prophesies virgin birth: 'almah' will conceive and bear son called Immanuel",
        "premise",
        "Isaiah 7:14/Matthew 1:23",
        "prophecy"
    )
    
    add_edge(virgin_premise, prophecy_conclusion, "supports", "Miraculous sign of divine intervention")
    add_edge(translation_objection, virgin_premise, "if_objection", "Questions Hebrew translation")
    
    translation_response = add_node(
        "Septuagint translators used 'parthenos' (virgin); contemporary Jewish understanding supported virgin birth",
        "response",
        "Septuagint/Hebrew lexicons",
        "prophecy"
    )
    
    add_edge(translation_response, translation_objection, "then_response", "Ancient translation supports virgin interpretation")
    
    return prophecy_conclusion

# =============================================================================
# 3. PROBLEM OF EVIL 
# =============================================================================

def add_evil_arguments():
    """Add problem of evil arguments and theodicies"""
    print("Adding Problem of Evil Arguments...")
    
    # The main objection
    evil_objection = add_node(
        "If God is all-powerful, all-knowing, and perfectly good, evil should not exist",
        "objection",
        "Epicurus/Problem of Evil",
        "evil"
    )
    
    # Premise for theism that evil challenges
    god_premise = add_node(
        "God exists as perfectly good, omnipotent, and omniscient being", 
        "premise",
        "Classical theism",
        "theism"
    )
    
    add_edge(evil_objection, god_premise, "if_objection", "Evil appears incompatible with perfect God")
    
    # Logical vs evidential forms
    logical_evil = add_node(
        "The existence of any evil is logically incompatible with an omnipotent, omniscient, perfectly good God",
        "objection",
        "J.L. Mackie/Logical argument",
        "evil"
    )
    
    evidential_evil = add_node(
        "The amount and types of evil in the world provide strong evidence against God's existence",
        "objection", 
        "William Rowe/Evidential argument",
        "evil"
    )
    
    add_edge(logical_evil, evil_objection, "supports", "Stronger form of the argument")
    add_edge(evidential_evil, evil_objection, "supports", "Probabilistic form of the argument")
    
    # Specific examples of problematic evil
    natural_evil = add_node(
        "Natural disasters, diseases, and animal suffering occur without human moral agency",
        "premise",
        "Evidential problem/Rowe",
        "evil"
    )
    
    innocent_suffering = add_node(
        "Innocent children and animals suffer intensely without apparent greater good",
        "premise", 
        "Evidential problem/Rowe",
        "evil"
    )
    
    add_edge(natural_evil, evidential_evil, "supports", "Evil not caused by free will")
    add_edge(innocent_suffering, evidential_evil, "supports", "Suffering without moral agency or growth")
    
    # THEODICIES AND RESPONSES
    
    # Free Will Defense (Plantinga)
    freewill_response = add_node(
        "God permits evil because free will is so valuable that a world with free creatures is better than a world without them, even if free creatures sometimes choose evil",
        "response",
        "Alvin Plantinga/Free Will Defense", 
        "evil"
    )
    
    add_edge(freewill_response, logical_evil, "then_response", "Logical compatibility established")
    
    # Objection to free will defense
    freewill_objection = add_node(
        "God could have created free creatures who always freely choose good",
        "objection",
        "Critics of free will defense",
        "evil"
    )
    
    add_edge(freewill_objection, freewill_response, "if_objection", "Questions necessity of evil for free will")
    
    freewill_counter = add_node(
        "It may be logically impossible for God to create creatures who are truly free but always choose good",
        "response",
        "Plantinga/Transworld depravity",
        "evil"
    )
    
    add_edge(freewill_counter, freewill_objection, "then_response", "Logical impossibility argument")
    
    # Soul-making theodicy (Hick)
    soulmaking_response = add_node(
        "Evil and suffering are necessary for spiritual growth and character development; this world is a 'soul-making' environment",
        "response",
        "John Hick/Irenaean theodicy",
        "evil"
    )
    
    add_edge(soulmaking_response, evidential_evil, "then_response", "Evil serves greater purpose of spiritual development")
    
    # Objections to soul-making
    soulmaking_objection1 = add_node(
        "Many people are crushed rather than improved by suffering",
        "objection",
        "Critics of Hick",
        "evil"
    )
    
    soulmaking_objection2 = add_node(
        "Excessive suffering exceeds what is necessary for character development",
        "objection",
        "Critics of Hick", 
        "evil"
    )
    
    add_edge(soulmaking_objection1, soulmaking_response, "if_objection", "Empirical counterexamples")
    add_edge(soulmaking_objection2, soulmaking_response, "if_objection", "Proportionality problem")
    
    soulmaking_counter1 = add_node(
        "Character development may continue in afterlife; present suffering not final word",
        "response",
        "Hick/Eschatological verification",
        "evil"
    )
    
    soulmaking_counter2 = add_node(
        "Epistemic distance requires genuine uncertainty and risk for meaningful choice",
        "response", 
        "Hick/Epistemic distance",
        "evil"
    )
    
    add_edge(soulmaking_counter1, soulmaking_objection1, "then_response", "Afterlife completes development")
    add_edge(soulmaking_counter2, soulmaking_objection2, "then_response", "Uncertainty necessary for genuine choice")
    
    # Greater good defense
    greater_good_response = add_node(
        "God permits evil only when it serves a greater good that outweighs the evil",
        "response",
        "Traditional theodicy",
        "evil"
    )
    
    add_edge(greater_good_response, evidential_evil, "then_response", "Evil justified by greater goods")
    
    # Objection to greater good
    greater_good_objection = add_node(
        "No conceivable greater good could justify the worst instances of evil and suffering", 
        "objection",
        "Rowe/Ivan Karamazov",
        "evil"
    )
    
    add_edge(greater_good_objection, greater_good_response, "if_objection", "Some evils appear gratuitous")
    
    greater_good_counter = add_node(
        "Human cognitive limitations prevent us from seeing how all evils fit into God's greater plan",
        "response",
        "Skeptical theism/Divine inscrutability",
        "evil"
    )
    
    add_edge(greater_good_counter, greater_good_objection, "then_response", "Limited perspective argument")
    
    # Natural evil specific objection
    natural_evil_objection = add_node(
        "Natural evils (earthquakes, diseases) cannot be explained by free will since they don't result from human choices",
        "objection", 
        "Critics/Natural evil problem",
        "evil"
    )
    
    add_edge(natural_evil_objection, freewill_response, "if_objection", "Free will defense insufficient for natural evil")
    
    natural_evil_response1 = add_node(
        "Natural evils may result from Satan's free choice or angelic rebellion",
        "response",
        "Christian theodicy",
        "evil"
    )
    
    natural_evil_response2 = add_node(
        "Natural processes that sometimes cause harm are necessary for a law-like, predictable world where moral choices matter",
        "response",
        "Natural law theodicy",
        "evil"
    )
    
    add_edge(natural_evil_response1, natural_evil_objection, "then_response", "Supernatural agency explanation")
    add_edge(natural_evil_response2, natural_evil_objection, "then_response", "Natural law necessity argument")
    
    return evil_objection

# =============================================================================
# 4. DIVINE HIDDENNESS
# =============================================================================

def add_hiddenness_arguments():
    """Add divine hiddenness argument and responses"""
    print("Adding Divine Hiddenness Arguments...")
    
    # Main objection
    hiddenness_objection = add_node(
        "If God exists and loves all people, He would make His existence obvious to everyone",
        "objection",
        "J.L. Schellenberg/Divine hiddenness",
        "hiddenness"
    )
    
    # Supporting premise
    nonbelief_premise = add_node(
        "Many reasonable, sincere people do not believe in God despite searching",
        "premise",
        "Schellenberg/Nonresistant nonbelief",
        "hiddenness"
    )
    
    add_edge(nonbelief_premise, hiddenness_objection, "supports", "Evidence that God is hidden")
    
    theism_premise = add_node(
        "God exists as perfectly loving, omnipotent, and omniscient being",
        "premise", 
        "Classical theism",
        "hiddenness"
    )
    
    add_edge(hiddenness_objection, theism_premise, "if_objection", "Hiddenness incompatible with loving God")
    
    # RESPONSES TO HIDDENNESS
    
    # Epistemic distance response
    epistemic_response = add_node(
        "God maintains epistemic distance to preserve human freedom and enable authentic faith",
        "response",
        "John Hick/Reformed epistemology",
        "hiddenness"
    )
    
    add_edge(epistemic_response, hiddenness_objection, "then_response", "Hiddenness serves greater good of freedom")
    
    # Greater good response
    hiddenness_greater_good = add_node(
        "God has morally sufficient reasons for remaining hidden that we cannot fully comprehend",
        "response",
        "Skeptical theism",
        "hiddenness"
    )
    
    add_edge(hiddenness_greater_good, hiddenness_objection, "then_response", "Divine inscrutability argument")
    
    # Free will response
    hiddenness_freewill = add_node(
        "If God's existence were obvious, it would compromise genuine free choice and authentic relationship",
        "response",
        "C.S. Lewis/Free will theodicy",
        "hiddenness"
    )
    
    add_edge(hiddenness_freewill, hiddenness_objection, "then_response", "Coercion vs. freedom concern")
    
    # Natural revelation response
    natural_revelation = add_node(
        "God has revealed Himself through creation, conscience, and religious experience; hiddenness is not complete",
        "response",
        "Natural theology/Sensus divinitatis", 
        "hiddenness"
    )
    
    add_edge(natural_revelation, hiddenness_objection, "then_response", "God is revealed, not hidden")
    
    # Objections to responses
    epistemic_objection = add_node(
        "Some degree of evidence would not compromise freedom; complete hiddenness is excessive",
        "objection",
        "Schellenberg/Proportionality",
        "hiddenness"
    )
    
    add_edge(epistemic_objection, epistemic_response, "if_objection", "Questions necessity of complete hiddenness")
    
    epistemic_counter = add_node(
        "Any degree of divine evidence might compromise the kind of freedom God desires",
        "response",
        "Michael Murray/Reformed response",
        "hiddenness"
    )
    
    add_edge(epistemic_counter, epistemic_objection, "then_response", "Binary nature of freedom argument")
    
    return hiddenness_objection

# =============================================================================
# 5. YOUNG EARTH CREATIONISM
# =============================================================================

def add_yec_arguments():
    """Add Young Earth Creationism arguments"""
    print("Adding Young Earth Creationism Arguments...")
    
    # Main conclusion
    yec_conclusion = add_node(
        "The earth is approximately 6,000 years old and was created in six literal days",
        "conclusion",
        "Ken Ham/Answers in Genesis",
        "young_earth"
    )
    
    # Biblical premises
    genesis_literal = add_node(
        "Genesis 1-11 should be interpreted literally as historical narrative",
        "premise",
        "Biblical literalism/YEC",
        "young_earth"
    )
    
    genealogies_premise = add_node(
        "Biblical genealogies from Adam to Abraham span approximately 2,000 years",
        "premise",
        "Genesis 5 & 11/Chronology",
        "young_earth"
    )
    
    abraham_date = add_node(
        "Abraham lived approximately 2000 BC according to archaeological evidence",
        "premise",
        "Historical/Archaeological consensus",
        "young_earth"
    )
    
    add_edge(genesis_literal, yec_conclusion, "supports", "Literal interpretation supports young earth")
    add_edge(genealogies_premise, yec_conclusion, "supports", "Chronological calculation")
    add_edge(abraham_date, yec_conclusion, "supports", "Fixed historical reference point")
    
    # Global flood premise
    global_flood = add_node(
        "A global flood occurred approximately 4,400 years ago in Noah's time",
        "premise",
        "Genesis 6-9/Flood geology",
        "young_earth"
    )
    
    add_edge(global_flood, yec_conclusion, "supports", "Explains geological formations rapidly")
    
    # "Were you there?" argument
    were_you_there = add_node(
        "Scientific claims about the ancient past cannot be observed directly and rely on unprovable assumptions",
        "premise",
        "Ken Ham/Observational vs. historical science",
        "young_earth"
    )
    
    add_edge(were_you_there, yec_conclusion, "supports", "Questions reliability of old-earth evidence")
    
    # OBJECTIONS TO YEC
    
    # Radiometric dating objection
    radiometric_objection = add_node(
        "Radiometric dating consistently shows rocks millions and billions of years old",
        "objection",
        "Geological science",
        "young_earth"
    )
    
    add_edge(radiometric_objection, yec_conclusion, "if_objection", "Physical evidence contradicts young earth")
    
    # YEC responses to radiometric dating
    decay_rate_response = add_node(
        "Radioactive decay rates may have varied in the past due to different physical conditions",
        "response",
        "RATE project/AiG",
        "young_earth"
    )
    
    initial_conditions_response = add_node(
        "Radiometric dating makes unprovable assumptions about initial conditions",
        "response",
        "YEC scientists",
        "young_earth"
    )
    
    add_edge(decay_rate_response, radiometric_objection, "then_response", "Physical constants may not be constant")
    add_edge(initial_conditions_response, radiometric_objection, "then_response", "Assumption-dependent measurements")
    
    # Fossil record objection
    fossil_objection = add_node(
        "The fossil record shows progressive development over millions of years",
        "objection",
        "Paleontology",
        "young_earth"
    )
    
    add_edge(fossil_objection, yec_conclusion, "if_objection", "Biological evidence contradicts young earth")
    
    # Flood geology response
    flood_geology_response = add_node(
        "The fossil record was laid down rapidly during Noah's flood, not over millions of years", 
        "response",
        "Henry Morris/Flood geology",
        "young_earth"
    )
    
    add_edge(flood_geology_response, fossil_objection, "then_response", "Catastrophic formation explanation")
    
    # Plate tectonics objection
    plate_tectonics_objection = add_node(
        "Continental drift and plate tectonics require millions of years",
        "objection", 
        "Geology",
        "young_earth"
    )
    
    add_edge(plate_tectonics_objection, yec_conclusion, "if_objection", "Geological processes require vast time")
    
    catastrophic_plates_response = add_node(
        "Catastrophic plate tectonics during the flood could accomplish continental drift rapidly",
        "response",
        "John Baumgardner/CPT",
        "young_earth"
    )
    
    add_edge(catastrophic_plates_response, plate_tectonics_objection, "then_response", "Rapid geological processes")
    
    # Genetics objection
    genetics_objection = add_node(
        "Genetic diversity and mutation rates require much longer than 6,000 years",
        "objection",
        "Population genetics",
        "young_earth"
    )
    
    add_edge(genetics_objection, yec_conclusion, "if_objection", "Biological evidence contradicts timeline")
    
    # Created with age response
    created_age_response = add_node(
        "God created the world with apparent age, just as Adam was created as a mature adult",
        "response",
        "Philip Gosse/Appearance of age",
        "young_earth"
    )
    
    add_edge(created_age_response, genetics_objection, "then_response", "Supernatural creation explanation")
    
    # Objection to created age
    deceptive_god_objection = add_node(
        "Creating with false appearance of age would make God deceptive",
        "objection",
        "Critics of appearance of age",
        "young_earth"
    )
    
    add_edge(deceptive_god_objection, created_age_response, "if_objection", "Questions God's truthfulness")
    
    functional_age_response = add_node(
        "Created age is functional maturity, not deception; like wine from water at Cana",
        "response",
        "YEC apologists",
        "young_earth"
    )
    
    add_edge(functional_age_response, deceptive_god_objection, "then_response", "Functional vs. deceptive distinction")
    
    return yec_conclusion

# =============================================================================
# 6. HELL AND ETERNAL PUNISHMENT
# =============================================================================

def add_hell_arguments():
    """Add arguments about hell and eternal punishment"""
    print("Adding Hell/Eternal Punishment Arguments...")
    
    # Different views of hell
    eternal_conscious_torment = add_node(
        "Hell is eternal conscious torment for the unrepentant wicked",
        "conclusion",
        "Traditional Christian doctrine",
        "hell"
    )
    
    annihilationism = add_node(
        "The wicked are ultimately destroyed/annihilated rather than eternally tormented",
        "conclusion",
        "Annihilationist theology",
        "hell"
    )
    
    universalism = add_node(
        "All people will eventually be saved and reconciled to God",
        "conclusion", 
        "Universalist theology",
        "hell"
    )
    
    # Biblical premises for traditional view
    biblical_hell = add_node(
        "Jesus spoke more about hell than heaven and described it as eternal punishment",
        "premise",
        "Matthew 25:46/Mark 9:43-48",
        "hell"
    )
    
    add_edge(biblical_hell, eternal_conscious_torment, "supports", "Jesus' teaching supports traditional view")
    
    # MORAL OBJECTIONS TO HELL
    
    # Finite/infinite objection
    finite_infinite_objection = add_node(
        "Finite sins cannot deserve infinite punishment; eternal torment is unjust",
        "objection",
        "Moral objections to hell",
        "hell"
    )
    
    add_edge(finite_infinite_objection, eternal_conscious_torment, "if_objection", "Proportionality problem")
    
    # Response to finite/infinite
    infinite_being_response = add_node(
        "Sins against an infinite being (God) deserve infinite punishment",
        "response",
        "Anselm/Traditional theology",
        "hell"
    )
    
    ongoing_rebellion_response = add_node(
        "Hell may involve ongoing rebellion rather than punishment for past finite sins",
        "response",
        "C.S. Lewis/The Great Divorce",
        "hell"
    )
    
    add_edge(infinite_being_response, finite_infinite_objection, "then_response", "Magnitude based on target of offense")
    add_edge(ongoing_rebellion_response, finite_infinite_objection, "then_response", "Continuing rather than finished sin")
    
    # Arbitrary punishment objection
    arbitrary_objection = add_node(
        "Eternal punishment for simple unbelief seems arbitrary and excessive",
        "objection",
        "Critics of traditional hell",
        "hell"
    )
    
    add_edge(arbitrary_objection, eternal_conscious_torment, "if_objection", "Questions justice of punishment")
    
    free_choice_response = add_node(
        "Hell is the natural consequence of free choice to reject God; God respects that choice",
        "response",
        "C.S. Lewis/Free will",
        "hell"
    )
    
    add_edge(free_choice_response, arbitrary_objection, "then_response", "Self-chosen consequence")
    
    # Divine mercy objection
    mercy_objection = add_node(
        "A loving God would not allow anyone to suffer eternally",
        "objection",
        "Critics/Appeal to divine love",
        "hell"
    )
    
    add_edge(mercy_objection, eternal_conscious_torment, "if_objection", "Incompatible with divine love")
    
    # Responses supporting universalism
    mercy_universalist_response = add_node(
        "Divine love ultimately wins and all will be reconciled to God",
        "response",
        "Universalist theology",
        "hell"
    )
    
    add_edge(mercy_universalist_response, mercy_objection, "then_response", "Love triumphs over judgment")
    add_edge(mercy_universalist_response, universalism, "supports", "Love requires universal salvation")
    
    # Traditional response to mercy objection
    justice_mercy_balance = add_node(
        "God's love is balanced by His justice; mercy is offered but can be rejected",
        "response",
        "Traditional theology",
        "hell"
    )
    
    add_edge(justice_mercy_balance, mercy_objection, "then_response", "Divine attributes in balance")
    
    # Annihilationist responses
    destruction_not_torment = add_node(
        "Biblical language of 'destruction' and 'perishing' supports annihilation",
        "response",
        "Edward Fudge/Conditionalism",
        "hell"
    )
    
    add_edge(destruction_not_torment, finite_infinite_objection, "then_response", "Proportionate punishment through annihilation")
    add_edge(destruction_not_torment, annihilationism, "supports", "Biblical language supports conditional immortality")
    
    # Objections to annihilationism
    eternal_punishment_objection = add_node(
        "Matthew 25:46 contrasts eternal punishment with eternal life; punishment must be ongoing",
        "objection",
        "Traditional theologians",
        "hell"
    )
    
    add_edge(eternal_punishment_objection, annihilationism, "if_objection", "Biblical evidence for ongoing punishment")
    
    eternal_result_response = add_node(
        "'Eternal punishment' refers to eternal result, not eternal process",
        "response",
        "Annihilationist interpretation",
        "hell"
    )
    
    add_edge(eternal_result_response, eternal_punishment_objection, "then_response", "Eternal consequences vs. eternal process")
    
    return eternal_conscious_torment

# =============================================================================
# 7. ATONEMENT AND SALVATION
# =============================================================================

def add_atonement_arguments():
    """Add arguments about atonement theories"""
    print("Adding Atonement/Salvation Arguments...")
    
    # Different atonement theories
    penal_substitution = add_node(
        "Jesus died as penal substitute, bearing God's wrath for human sin",
        "conclusion",
        "Reformed theology/Anselm",
        "atonement"
    )
    
    moral_influence = add_node(
        "Jesus' death demonstrates God's love and influences moral transformation",
        "conclusion",
        "Peter Abelard/Liberal theology",
        "atonement"
    )
    
    christus_victor = add_node(
        "Jesus' death defeats Satan and the powers of evil",
        "conclusion",
        "Gustaf Aulén/Early church",
        "atonement"
    )
    
    # Biblical support for penal substitution
    isaiah_substitution = add_node(
        "Isaiah 53:5 says 'he was pierced for our transgressions' and 'by his wounds we are healed'",
        "premise",
        "Isaiah 53/Biblical text",
        "atonement"
    )
    
    paul_substitution = add_node(
        "2 Corinthians 5:21 says 'God made him who had no sin to be sin for us'",
        "premise",
        "2 Cor 5:21/Pauline theology",
        "atonement"
    )
    
    add_edge(isaiah_substitution, penal_substitution, "supports", "Prophetic prediction of substitution")
    add_edge(paul_substitution, penal_substitution, "supports", "Apostolic teaching of substitution")
    
    # OBJECTIONS TO PENAL SUBSTITUTION
    
    # Divine child abuse objection
    child_abuse_objection = add_node(
        "God punishing Jesus for others' sins resembles cosmic child abuse",
        "objection",
        "Feminist theology/Critics",
        "atonement"
    )
    
    add_edge(child_abuse_objection, penal_substitution, "if_objection", "Questions morality of substitutionary punishment")
    
    voluntary_sacrifice_response = add_node(
        "Jesus voluntarily offered himself; it was not imposed punishment but willing sacrifice",
        "response",
        "Traditional theology",
        "atonement"
    )
    
    trinity_response = add_node(
        "The Trinity means God sacrificed himself, not that the Father punished a separate person",
        "response",
        "Trinitarian theology",
        "atonement"
    )
    
    add_edge(voluntary_sacrifice_response, child_abuse_objection, "then_response", "Voluntary vs. imposed suffering")
    add_edge(trinity_response, child_abuse_objection, "then_response", "Divine self-sacrifice, not external punishment")
    
    # Arbitrary transfer objection
    transfer_objection = add_node(
        "Why does God need to punish someone for forgiveness? Why not simply forgive?",
        "objection",
        "Critics of substitution",
        "atonement"
    )
    
    add_edge(transfer_objection, penal_substitution, "if_objection", "Questions necessity of substitution")
    
    justice_satisfied_response = add_node(
        "God's justice requires satisfaction; sin cannot simply be overlooked without consequence",
        "response",
        "Anselmian theology",
        "atonement"
    )
    
    add_edge(justice_satisfied_response, transfer_objection, "then_response", "Divine justice requires satisfaction")
    
    # Moral influence theory support
    moral_transformation = add_node(
        "Christ's self-sacrificial love inspires moral transformation and response",
        "premise",
        "Abelardian theology",
        "atonement"
    )
    
    add_edge(moral_transformation, moral_influence, "supports", "Love motivates moral change")
    
    # Objection to moral influence alone
    insufficient_objection = add_node(
        "Moral example alone is insufficient to deal with objective guilt and divine wrath",
        "objection",
        "Critics of moral influence theory",
        "atonement"
    )
    
    add_edge(insufficient_objection, moral_influence, "if_objection", "Inadequate for objective problem of sin")
    
    objective_atonement_response = add_node(
        "True transformation requires objective forgiveness, not just subjective inspiration",
        "response",
        "Evangelical theology",
        "atonement"
    )
    
    add_edge(objective_atonement_response, insufficient_objection, "then_response", "Objective reality needed for subjective change")
    
    return penal_substitution

# =============================================================================
# 8. TRINITY AND INCARNATION
# =============================================================================

def add_trinity_arguments():
    """Add arguments about Trinity and Incarnation"""
    print("Adding Trinity/Incarnation Arguments...")
    
    # Trinity doctrine
    trinity_doctrine = add_node(
        "God exists as three persons (Father, Son, Spirit) in one essence",
        "conclusion",
        "Nicene Creed/Christian orthodoxy",
        "trinity"
    )
    
    incarnation_doctrine = add_node(
        "Jesus Christ is both fully God and fully human in one person",
        "conclusion",
        "Chalcedonian Creed/Christology",
        "trinity"
    )
    
    # Biblical premises for Trinity
    three_persons = add_node(
        "Scripture speaks of Father, Son, and Holy Spirit as distinct persons",
        "premise",
        "Matthew 28:19/2 Cor 13:14",
        "trinity"
    )
    
    one_god = add_node(
        "Scripture affirms there is only one God",
        "premise",
        "Deuteronomy 6:4/1 Cor 8:6",
        "trinity"
    )
    
    jesus_deity = add_node(
        "Scripture affirms Jesus is God",
        "premise",
        "John 1:1/John 20:28/Philippians 2:6",
        "trinity"
    )
    
    add_edge(three_persons, trinity_doctrine, "supports", "Distinct persons evidenced in Scripture")
    add_edge(one_god, trinity_doctrine, "supports", "Monotheism maintained")
    add_edge(jesus_deity, trinity_doctrine, "supports", "Christ's divinity established")
    add_edge(jesus_deity, incarnation_doctrine, "supports", "Divine nature of Christ")
    
    # OBJECTIONS TO TRINITY
    
    # Logical contradiction objection
    logical_contradiction_objection = add_node(
        "One cannot be three; the Trinity is a logical contradiction",
        "objection",
        "Critics/Muslims/Unitarians",
        "trinity"
    )
    
    add_edge(logical_contradiction_objection, trinity_doctrine, "if_objection", "Mathematical impossibility claim")
    
    different_relations_response = add_node(
        "God is one in essence but three in relations/persons; no contradiction",
        "response",
        "Cappadocian Fathers/Orthodox theology",
        "trinity"
    )
    
    mystery_not_contradiction = add_node(
        "The Trinity is beyond human logic but not contrary to logic",
        "response",
        "Christian theology/Apophatic tradition",
        "trinity"
    )
    
    add_edge(different_relations_response, logical_contradiction_objection, "then_response", "Different aspects avoid contradiction")
    add_edge(mystery_not_contradiction, logical_contradiction_objection, "then_response", "Trans-logical vs. illogical")
    
    # Analogies for Trinity
    water_analogy = add_node(
        "Like water exists as ice, liquid, and vapor, God exists in three forms",
        "premise",
        "Popular apologetics",
        "trinity"
    )
    
    add_edge(water_analogy, trinity_doctrine, "supports", "Analogy aids understanding")
    
    # Objection to analogies
    modalism_objection = add_node(
        "Water analogies promote modalism heresy (God changing modes rather than three persons)",
        "objection",
        "Orthodox theologians",
        "trinity"
    )
    
    add_edge(modalism_objection, water_analogy, "if_objection", "Analogy misleads about distinct persons")
    
    imperfect_analogy_response = add_node(
        "All analogies are imperfect; they illuminate aspects while failing in others",
        "response",
        "Theological methodology",
        "trinity"
    )
    
    add_edge(imperfect_analogy_response, modalism_objection, "then_response", "Analogy limitations acknowledged")
    
    # Arianism objection
    arianism_objection = add_node(
        "Jesus is subordinate to the Father and therefore not equal God",
        "objection",
        "Arian theology/Jehovah's Witnesses",
        "trinity"
    )
    
    add_edge(arianism_objection, jesus_deity, "if_objection", "Questions full divinity of Christ")
    
    economic_immanent_distinction = add_node(
        "Jesus is economically subordinate in role but ontologically equal in essence",
        "response",
        "Nicene theology",
        "trinity"
    )
    
    add_edge(economic_immanent_distinction, arianism_objection, "then_response", "Functional vs. essential distinction")
    
    # Incarnation objections
    two_natures_objection = add_node(
        "How can one person have both divine and human natures without contradiction?",
        "objection",
        "Philosophical critics",
        "trinity"
    )
    
    add_edge(two_natures_objection, incarnation_doctrine, "if_objection", "Questions possibility of dual natures")
    
    chalcedon_response = add_node(
        "Two natures united in one person 'without confusion, without change, without division, without separation'",
        "response",
        "Council of Chalcedon",
        "trinity"
    )
    
    add_edge(chalcedon_response, two_natures_objection, "then_response", "Orthodox christological formulation")
    
    return trinity_doctrine

# =============================================================================
# 9. POPULAR APOLOGETICS (STROBEL, MCDOWELL)
# =============================================================================

def add_popular_apologetics():
    """Add popular apologetics arguments"""
    print("Adding Popular Apologetics Arguments...")
    
    # Case for Christ arguments
    case_for_christ = add_node(
        "Historical and legal evidence demonstrates Jesus' death and resurrection",
        "conclusion",
        "Lee Strobel/The Case for Christ",
        "popular"
    )
    
    medical_death = add_node(
        "Medical evidence confirms Jesus actually died from crucifixion trauma",
        "premise",
        "Alexander Metherell/Medical analysis",
        "popular"
    )
    
    eyewitness_gospels = add_node(
        "The Gospels are based on eyewitness testimony from apostles",
        "premise",
        "Craig Blomberg/Gospel reliability",
        "popular"
    )
    
    add_edge(medical_death, case_for_christ, "supports", "Medical expertise confirms death")
    add_edge(eyewitness_gospels, case_for_christ, "supports", "Eyewitness testimony foundation")
    
    # Evidence That Demands a Verdict
    evidence_demands_verdict = add_node(
        "Multiple lines of evidence converge to support Christian truth claims",
        "conclusion",
        "Josh McDowell/Evidence That Demands a Verdict",
        "popular"
    )
    
    manuscript_evidence = add_node(
        "New Testament has superior manuscript attestation compared to other ancient works",
        "premise",
        "F.F. Bruce/Textual criticism",
        "popular"
    )
    
    archaeological_confirmation = add_node(
        "Archaeological discoveries consistently confirm biblical accounts",
        "premise",
        "William Albright/Biblical archaeology",
        "popular"
    )
    
    add_edge(manuscript_evidence, evidence_demands_verdict, "supports", "Textual reliability established")
    add_edge(archaeological_confirmation, evidence_demands_verdict, "supports", "External confirmation of biblical claims")
    
    # OBJECTIONS TO POPULAR APOLOGETICS
    
    # Cherry-picked experts objection
    cherry_picking_objection = add_node(
        "Popular apologists only cite conservative scholars who agree with predetermined conclusions",
        "objection",
        "Critical scholars",
        "popular"
    )
    
    add_edge(cherry_picking_objection, case_for_christ, "if_objection", "Selection bias in expert testimony")
    add_edge(cherry_picking_objection, evidence_demands_verdict, "if_objection", "Biased scholarship selection")
    
    broad_scholarly_response = add_node(
        "Many cited scholars are mainstream academics, not just conservative Christians",
        "response",
        "Popular apologists",
        "popular"
    )
    
    add_edge(broad_scholarly_response, cherry_picking_objection, "then_response", "Diverse scholarly representation")
    
    # Confirmation bias objection
    confirmation_bias_objection = add_node(
        "Popular apologetics starts with conclusions and finds evidence to support them",
        "objection",
        "Methodological critics",
        "popular"
    )
    
    add_edge(confirmation_bias_objection, evidence_demands_verdict, "if_objection", "Questions objectivity of investigation")
    
    historical_method_response = add_node(
        "Standard historical methods are applied; conclusions follow from evidence",
        "response",
        "Christian historians",
        "popular"
    )
    
    add_edge(historical_method_response, confirmation_bias_objection, "then_response", "Proper methodology defended")
    
    # Ignoring contradictions objection
    contradictions_objection = add_node(
        "Popular apologetics ignores or minimizes biblical contradictions and difficulties",
        "objection",
        "Critical scholars",
        "popular"
    )
    
    add_edge(contradictions_objection, eyewitness_gospels, "if_objection", "Questions reliability of sources")
    
    harmonization_response = add_node(
        "Apparent contradictions can be resolved through careful exegesis and historical context",
        "response",
        "Conservative scholarship",
        "popular"
    )
    
    add_edge(harmonization_response, contradictions_objection, "then_response", "Resolution through scholarship")
    
    # Alternative manuscript objection
    late_manuscripts_objection = add_node(
        "Early manuscripts show significant textual variants; later manuscripts are harmonized",
        "objection",
        "Bart Ehrman/Textual criticism",
        "popular"
    )
    
    add_edge(late_manuscripts_objection, manuscript_evidence, "if_objection", "Early variants question reliability")
    
    essential_message_response = add_node(
        "Textual variants do not affect essential Christian doctrines or historical claims",
        "response",
        "Daniel Wallace/Textual scholarship",
        "popular"
    )
    
    add_edge(essential_message_response, late_manuscripts_objection, "then_response", "Core message unaffected by variants")
    
    return case_for_christ

# =============================================================================
# MAIN EXECUTION
# =============================================================================

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
        
        print(f"Graph statistics:")
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

def export_to_dashboard():
    """Export the updated graph to dashboard JSON format"""
    print("Exporting to dashboard format...")
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Get all nodes
        cursor.execute("""
            SELECT id, content, node_type, source, category 
            FROM argument_nodes
        """)
        nodes_data = cursor.fetchall()
        
        # Get all edges  
        cursor.execute("""
            SELECT source_id, target_id, relation, reasoning
            FROM argument_edges
        """)
        edges_data = cursor.fetchall()
        
        # Format for dashboard
        nodes = []
        for node in nodes_data:
            nodes.append({
                "id": node[0],
                "label": node[1][:100] + ("..." if len(node[1]) > 100 else ""),
                "title": node[1],  # Full content on hover
                "group": node[4],   # category
                "type": node[2],    # node_type
                "source": node[3]   # source
            })
        
        edges = []
        for edge in edges_data:
            edges.append({
                "from": edge[0],    # source_id  
                "to": edge[1],      # target_id
                "label": edge[2],   # relation
                "title": edge[3]    # reasoning
            })
        
        # Create dashboard JSON
        dashboard_data = {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "title": "Expanded Christian Apologetics Argument Graph",
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "categories": list(set(node[4] for node in nodes_data)),
                "export_date": datetime.now().isoformat()
            }
        }
        
        # Write to dashboard file
        output_path = "/Users/bunny/.openclaw/workspace/cashew/dashboard/data/apologetics-graph.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(nodes)} nodes and {len(edges)} edges to {output_path}")
        return True
        
    except Exception as e:
        print(f"Error exporting to dashboard: {e}")
        return False
    finally:
        db.close()

# Run the expansion
if __name__ == "__main__":
    print("Expanding apologetics database with all missing topics...")
    
    # Add all argument categories
    resurrection_conclusion = add_resurrection_arguments()
    prophecy_conclusion = add_prophecy_arguments()  
    evil_objection = add_evil_arguments()
    hiddenness_objection = add_hiddenness_arguments()
    yec_conclusion = add_yec_arguments()
    hell_conclusion = add_hell_arguments()
    atonement_conclusion = add_atonement_arguments()
    trinity_conclusion = add_trinity_arguments()
    popular_conclusion = add_popular_apologetics()
    
    print("\nAll topics added! Calculating final statistics...")
    
    # Calculate final cyclomatic complexity
    final_cc = calculate_cyclomatic_complexity()
    
    # Export to dashboard
    export_success = export_to_dashboard()
    
    print(f"\nExpansion complete!")
    print(f"Final cyclomatic complexity: {final_cc}")
    print(f"Dashboard export: {'SUCCESS' if export_success else 'FAILED'}")
    
    if final_cc and final_cc > 16:
        print(f"✅ Target achieved! CC increased from 16 to {final_cc}")
    else:
        print(f"⚠️ Need more complexity. Current CC: {final_cc}")
        
    print("\n🎯 Database expansion complete with comprehensive objection-response chains!")