#!/usr/bin/env python3
"""
Tests for pattern extraction module
"""

import unittest
import sys
import os
import sqlite3
import tempfile
import json
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.patterns import PatternExtractor

class TestPatternExtraction(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a temporary database for testing
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        
        # Initialize with proper schema and test data
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create the schema
        cursor.execute('''
            CREATE TABLE thought_nodes (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                node_type TEXT NOT NULL,
                domain TEXT,
                timestamp TEXT,
                confidence REAL,
                source_file TEXT,
                decayed INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                mood_state TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE derivation_edges (
                parent_id TEXT,
                child_id TEXT,
                relation TEXT,
                weight REAL,
                reasoning TEXT,
                confidence REAL,
                timestamp TEXT,
                PRIMARY KEY (parent_id, child_id, relation)
            )
        ''')
        
        # Add test data for pattern analysis
        now = datetime.now(timezone.utc).isoformat()
        test_nodes = [
            ("belief1", "Exercise improves mental health", "belief", "health", 0.8),
            ("observation1", "I felt better after running", "observation", "health", 0.7),
            ("question1", "What is the best workout routine?", "question", "health", 0.5),
            ("insight1", "Mind and body are interconnected systems", "insight", "meta", 0.9),
            ("contradiction1", "Sometimes rest is better than exercise", "belief", "health", 0.6)
        ]
        
        for node_id, content, node_type, domain, confidence in test_nodes:
            cursor.execute("""
                INSERT INTO thought_nodes 
                (id, content, node_type, domain, timestamp, confidence, source_file, metadata)
                VALUES (?, ?, ?, ?, ?, ?, 'test', '{}')
            """, (node_id, content, node_type, domain, now, confidence))
        
        # Add test edges with different relation types
        test_edges = [
            ("belief1", "observation1", "supports", 0.8),
            ("observation1", "insight1", "derived_from", 0.7),
            ("belief1", "contradiction1", "contradicts", 0.6),
            ("question1", "insight1", "questions", 0.5)
        ]
        
        for parent_id, child_id, relation, confidence in test_edges:
            cursor.execute("""
                INSERT INTO derivation_edges 
                (parent_id, child_id, relation, confidence, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (parent_id, child_id, relation, confidence, now))
        
        conn.commit()
        conn.close()
        
        self.extractor = PatternExtractor(self.db_path)
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.db_path)
    def test_branching_factor_calculation(self):
        """Test branching factor analysis"""
        branching = self.extractor.calculate_branching_factor()
        
        # Should return branching metrics
        self.assertIn("avg_branching", branching)
        self.assertIn("max_branching", branching)
        
        # Values should be non-negative
        self.assertGreaterEqual(branching["avg_branching"], 0)
        self.assertGreaterEqual(branching["max_branching"], 0)
    
    def test_question_pattern_analysis(self):
        """Test question pattern extraction"""
        questions = self.extractor.analyze_question_patterns()
        
        # Should return question metrics
        self.assertIn("total_questions", questions)
        self.assertIn("question_type_distribution", questions)
        self.assertIn("gap_type_distribution", questions)
        
        # Total questions should be non-negative
        self.assertGreaterEqual(questions["total_questions"], 0)
        
        # If there are questions, should have type distribution
        if questions["total_questions"] > 0:
            type_dist = questions["question_type_distribution"]
            self.assertIsInstance(type_dist, dict)
    
    def test_contradiction_tolerance(self):
        """Test contradiction tolerance analysis"""
        contradictions = self.extractor.calculate_contradiction_tolerance()
        
        # Should return contradiction metrics
        self.assertIn("contradiction_ratio", contradictions)
        self.assertIn("total_contradictions", contradictions)
        self.assertIn("total_edges", contradictions)
        
        # Ratio should be between 0-100
        ratio = contradictions["contradiction_ratio"]
        self.assertGreaterEqual(ratio, 0)
        self.assertLessEqual(ratio, 100)
    
    def test_confidence_patterns(self):
        """Test confidence pattern analysis"""
        confidence = self.extractor.analyze_confidence_patterns()
        
        # Should return confidence metrics
        self.assertIn("by_type", confidence)
        self.assertIn("overall_avg", confidence)
        
        # Overall average should be between 0-1
        overall = confidence["overall_avg"]
        self.assertGreaterEqual(overall, 0)
        self.assertLessEqual(overall, 1)
    
    def test_full_pattern_extraction(self):
        """Test complete pattern extraction"""
        patterns = self.extractor.extract_patterns()
        
        # Should contain all major pattern categories
        expected_keys = [
            "chain_depths", "branching", 
            "questions", "contradictions", "confidence", 
            "temporal", "composite"
        ]
        
        for key in expected_keys:
            self.assertIn(key, patterns, f"Missing pattern category: {key}")
    
    def test_pattern_description(self):
        """Test human-readable pattern description"""
        description = self.extractor.describe_patterns()
        
        # Should return a non-empty string
        self.assertIsInstance(description, str)
        self.assertGreater(len(description), 0)
        
        # Should contain key headers
        self.assertIn("REASONING PATTERNS", description)
        self.assertIn("Primary Style", description)
    
    def test_composite_metrics(self):
        """Test composite metric calculation"""
        patterns = self.extractor.extract_patterns()
        composite = patterns.get("composite", {})
        
        # Should have composite reasoning style
        self.assertIn("primary_reasoning_style", composite)
        self.assertIn("exploration_style", composite)
        self.assertIn("inquiry_style", composite)
        self.assertIn("confidence_level", composite)
        
        # Values should be from expected sets
        valid_styles = ["derivational", "supportive", "critical", "exploratory", "highly_connected", "moderately_connected"]
        self.assertIn(composite.get("primary_reasoning_style"), valid_styles)
        
        valid_exploration = ["depth-focused", "breadth-focused", "balanced"]
        self.assertIn(composite.get("exploration_style"), valid_exploration)


if __name__ == "__main__":
    unittest.main()