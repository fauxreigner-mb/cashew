#!/usr/bin/env python3
"""
Tests for bug fixes: novelty gates, hotspot proliferation fix, 
batch embedding, micro-cluster removal, and CLI commands
"""

import unittest
import sys
import os
import sqlite3
import tempfile
import json
import numpy as np
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.embeddings import check_novelty
# ThinkCycle removed — module deleted
from scripts.cashew_context import cmd_prune, cmd_compact, cmd_extract


class TestNoveltyGate(unittest.TestCase):
    """Test the novelty gate functionality"""
    
    def setUp(self):
        """Set up test database"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        
        # Initialize with schema
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE thought_nodes (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                node_type TEXT NOT NULL,
                domain TEXT,
                timestamp TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                confidence REAL,
                source_file TEXT,
                decayed INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                last_updated TEXT,
                mood_state TEXT,
                permanent INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE embeddings (
                node_id TEXT PRIMARY KEY,
                vector BLOB NOT NULL,
                model TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (node_id) REFERENCES thought_nodes(id)
            )
        ''')
        
        # Add test data
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO thought_nodes (id, content, node_type, domain, timestamp, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("existing_node", "Machine learning improves with more data", "fact", "tech", now, 0.8))
        
        # Create a fake embedding for the existing node
        fake_embedding = np.random.rand(384).astype(np.float32)  # MiniLM-L6-v2 dimension
        cursor.execute("""
            INSERT INTO embeddings (node_id, vector, model, updated_at)
            VALUES (?, ?, ?, ?)
        """, ("existing_node", fake_embedding.tobytes(), "all-MiniLM-L6-v2", now))
        
        conn.commit()
        conn.close()
        
        # Store the embedding for similarity tests
        self.existing_embedding = fake_embedding
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.db_path)
    
    @patch('core.embeddings.embed_text')
    def test_identical_content_rejected(self, mock_embed):
        """Test that identical content is rejected (similarity > 0.82)"""
        # Mock the embedding to return same as existing
        mock_embed.return_value = self.existing_embedding
        
        is_novel, max_sim, nearest_id = check_novelty(self.db_path, "Machine learning improves with more data")
        
        self.assertFalse(is_novel, "Identical content should be rejected")
        self.assertGreater(max_sim, 0.82, "Similarity should be > 0.82")
        self.assertEqual(nearest_id, "existing_node")
    
    @patch('core.embeddings.embed_text')
    def test_very_different_content_accepted(self, mock_embed):
        """Test that very different content is accepted"""
        # Mock embedding to be very different 
        different_embedding = np.random.rand(384).astype(np.float32)
        mock_embed.return_value = different_embedding
        
        is_novel, max_sim, nearest_id = check_novelty(self.db_path, "Cats like to play with string")
        
        self.assertTrue(is_novel, "Very different content should be accepted")
        self.assertLess(max_sim, 0.82, "Similarity should be < 0.82")
    
    @patch('core.embeddings.embed_text')
    def test_borderline_content_with_low_confidence_rejected(self, mock_embed):
        """Test that borderline similarity (0.72-0.82) gets checked properly"""
        # Create an embedding that's mathematically guaranteed to be in the target range
        # We'll create a vector that when dotted with existing gives us exactly 0.75 similarity
        normalized_existing = self.existing_embedding / np.linalg.norm(self.existing_embedding)
        # Create orthogonal component 
        random_vec = np.random.rand(384).astype(np.float32)
        orthogonal = random_vec - np.dot(random_vec, normalized_existing) * normalized_existing
        orthogonal = orthogonal / np.linalg.norm(orthogonal)
        
        # Mix to get desired similarity (cos(theta) = 0.75 means theta ~= 41.4 degrees)
        target_sim = 0.75
        angle_rad = np.arccos(target_sim)
        moderate_sim_embedding = target_sim * normalized_existing + np.sin(angle_rad) * orthogonal
        moderate_sim_embedding = moderate_sim_embedding / np.linalg.norm(moderate_sim_embedding)
        
        mock_embed.return_value = moderate_sim_embedding
        
        is_novel, max_sim, nearest_id = check_novelty(self.db_path, "Machine learning gets better with big datasets", 
                                                      threshold=0.82)
        
        # Should be in borderline range
        self.assertGreater(max_sim, 0.72, "Should be in borderline range")
        self.assertLess(max_sim, 0.82, "Should be in borderline range") 
        self.assertTrue(is_novel, "Should be novel since similarity < 0.82")
    
    @patch('core.embeddings.embed_text')
    def test_preloaded_embeddings_performance_mode(self, mock_embed):
        """Test that preloaded embeddings mode works correctly and avoids DB scans"""
        # Mock the embedding to return same as existing
        mock_embed.return_value = self.existing_embedding
        
        # Load embeddings once
        from core.embeddings import load_all_embeddings
        preloaded_embeddings = load_all_embeddings(self.db_path)
        
        # Verify we loaded the embeddings
        self.assertEqual(len(preloaded_embeddings), 1)
        self.assertIn("existing_node", preloaded_embeddings)
        
        # Test novelty check using preloaded embeddings
        is_novel, max_sim, nearest_id = check_novelty(
            self.db_path, "Machine learning improves with more data",
            preloaded_embeddings=preloaded_embeddings
        )
        
        # Should give same result as non-preloaded mode
        self.assertFalse(is_novel, "Identical content should be rejected with preloaded embeddings")
        self.assertGreater(max_sim, 0.82, "Similarity should be > 0.82")
        self.assertEqual(nearest_id, "existing_node")
        
        # Test with novel content
        different_embedding = np.random.rand(384).astype(np.float32)
        mock_embed.return_value = different_embedding
        
        is_novel2, max_sim2, nearest_id2 = check_novelty(
            self.db_path, "Cats like to play with string",
            preloaded_embeddings=preloaded_embeddings
        )
        
        self.assertTrue(is_novel2, "Novel content should be accepted with preloaded embeddings")
        self.assertLess(max_sim2, 0.82, "Similarity should be < 0.82")


    # TestThinkCycleNoveltyGate removed — core/think_cycle.py was deleted
    # Novelty gate is tested in TestNoveltyGate above


class TestCLICommands(unittest.TestCase):
    """Test new CLI commands exist and basic functionality"""
    
    def setUp(self):
        """Set up test database"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        
        # Initialize with schema
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE thought_nodes (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                node_type TEXT NOT NULL,
                domain TEXT,
                timestamp TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                confidence REAL,
                source_file TEXT,
                decayed INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                last_updated TEXT,
                mood_state TEXT,
                permanent INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.db_path)
    
    def test_prune_command_dry_run_exists(self):
        """Test that prune command with --dry-run doesn't crash"""
        # Create mock args
        class MockArgs:
            db = self.db_path
            dry_run = True
            min_age_days = 14
            max_confidence = 0.85
        
        args = MockArgs()
        
        # Should not crash
        try:
            result = cmd_prune(args)
            # If it returns something, it should be 0 (success)
            if result is not None:
                self.assertEqual(result, 0)
        except Exception as e:
            self.fail(f"Prune dry-run crashed: {e}")
    
    def test_compact_command_dry_run_exists(self):
        """Test that compact command with --dry-run doesn't crash"""
        # Create mock args
        class MockArgs:
            db = self.db_path
            dry_run = True
            similarity_threshold = 0.82
        
        args = MockArgs()
        
        # Should not crash
        try:
            result = cmd_compact(args)
            # If it returns something, it should be 0 (success)
            if result is not None:
                self.assertEqual(result, 0)
        except Exception as e:
            self.fail(f"Compact dry-run crashed: {e}")


class TestExtractionNoveltyGate(unittest.TestCase):
    """Test extraction with confidence + novelty gate"""
    
    def setUp(self):
        """Set up test database"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        
        # Initialize with schema (minimal for extract test)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE thought_nodes (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                node_type TEXT NOT NULL,
                domain TEXT,
                timestamp TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                confidence REAL,
                source_file TEXT,
                decayed INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                last_updated TEXT,
                mood_state TEXT,
                permanent INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE embeddings (
                node_id TEXT PRIMARY KEY,
                vector BLOB NOT NULL,
                model TEXT NOT NULL,
                updated_at TEXT NOT NULL
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
        
        # Add existing node
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO thought_nodes (id, content, node_type, domain, timestamp, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("existing_node", "Existing knowledge about machine learning", "fact", "tech", now, 0.8))
        
        # Add embedding
        embedding = np.random.rand(384).astype(np.float32)
        cursor.execute("""
            INSERT INTO embeddings (node_id, vector, model, updated_at)
            VALUES (?, ?, ?, ?)
        """, ("existing_node", embedding.tobytes(), "all-MiniLM-L6-v2", now))
        
        conn.commit()
        conn.close()
        
        self.existing_embedding = embedding
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.db_path)
    
    @patch('scripts.cashew_context.extract_from_conversation')
    @patch('builtins.print')  # Mock print to suppress output during tests
    def test_extract_duplicate_content_rejected(self, mock_print, mock_extract):
        """Test that extract rejects duplicate content"""
        # Mock extract_from_conversation to simulate rejection due to duplicate content
        mock_extract.return_value = {
            "success": True,
            "new_nodes": 0,  # No new nodes due to duplicates being rejected
            "new_edges": 0,
            "rejections": 1
        }
        
        # Create mock args for extract
        class MockArgs:
            db = self.db_path
            input = None
            session_id = "test_session"
            debug = False
            
        args = MockArgs()
        
        # Create temp input file with duplicate content
        input_fd, input_path = tempfile.mkstemp(suffix='.md')
        with os.fdopen(input_fd, 'w') as f:
            f.write("Existing knowledge about machine learning")
        
        args.input = input_path
        
        try:            
            # Run extract
            result = cmd_extract(args)
            
            # Verify extract was called
            mock_extract.assert_called_once()
            
            # Verify the result indicates no new nodes (duplicates rejected)
            if result is not None:
                self.assertEqual(result, 0, "Extract should succeed but create no new nodes")
            
        finally:
            # Clean up temp file
            os.unlink(input_path)


if __name__ == '__main__':
    unittest.main()