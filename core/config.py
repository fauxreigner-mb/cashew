#!/usr/bin/env python3
"""
Cashew Configuration Module
Centralized configuration with environment variable overrides
"""

import os
from typing import Optional

# Default configuration values
DEFAULT_TOKEN_BUDGET = 2000
DEFAULT_TOP_K = 10
DEFAULT_WALK_DEPTH = 2
DEFAULT_EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
DEFAULT_THINK_CYCLE_NODES = 5
DEFAULT_ACCESS_WEIGHT = 0.2
DEFAULT_TEMPORAL_WEIGHT = 0.1
DEFAULT_SIMILARITY_THRESHOLD = 0.3

class CashewConfig:
    """Configuration class with environment variable support"""
    
    def __init__(self):
        self._load_config()
    
    def _load_config(self):
        """Load configuration from environment variables with fallbacks"""
        # Session context configuration
        self.token_budget = int(os.getenv('CASHEW_TOKEN_BUDGET', DEFAULT_TOKEN_BUDGET))
        self.top_k = int(os.getenv('CASHEW_TOP_K', DEFAULT_TOP_K))
        self.walk_depth = int(os.getenv('CASHEW_WALK_DEPTH', DEFAULT_WALK_DEPTH))
        
        # Embedding configuration
        self.embedding_model = os.getenv('CASHEW_EMBEDDING_MODEL', DEFAULT_EMBEDDING_MODEL)
        
        # Think cycle configuration
        self.think_cycle_nodes = int(os.getenv('CASHEW_THINK_CYCLE_NODES', DEFAULT_THINK_CYCLE_NODES))
        
        # Scoring weights (should sum to ~1.0)
        self.access_weight = float(os.getenv('CASHEW_ACCESS_WEIGHT', DEFAULT_ACCESS_WEIGHT))
        self.temporal_weight = float(os.getenv('CASHEW_TEMPORAL_WEIGHT', DEFAULT_TEMPORAL_WEIGHT))
        self.similarity_threshold = float(os.getenv('CASHEW_SIMILARITY_THRESHOLD', DEFAULT_SIMILARITY_THRESHOLD))
        
        # Validation
        self._validate_config()
    
    def _validate_config(self):
        """Validate configuration values"""
        if self.token_budget <= 0:
            raise ValueError(f"Token budget must be positive, got {self.token_budget}")
        
        if self.top_k <= 0:
            raise ValueError(f"Top K must be positive, got {self.top_k}")
        
        if self.walk_depth < 0:
            raise ValueError(f"Walk depth must be non-negative, got {self.walk_depth}")
        
        if self.think_cycle_nodes <= 0:
            raise ValueError(f"Think cycle nodes must be positive, got {self.think_cycle_nodes}")
        
        if not 0 <= self.similarity_threshold <= 1:
            raise ValueError(f"Similarity threshold must be in [0,1], got {self.similarity_threshold}")
    
    def get_scoring_weights(self) -> dict:
        """Get the current scoring weights for hybrid retrieval"""
        # Calculate embedding weight as remainder to ensure weights sum to 1.0
        embedding_weight = 1.0 - self.access_weight - self.temporal_weight
        
        if embedding_weight < 0:
            raise ValueError(f"Access weight ({self.access_weight}) + temporal weight ({self.temporal_weight}) "
                           f"must not exceed 1.0")
        
        return {
            'embedding': embedding_weight,
            'access': self.access_weight,
            'temporal': self.temporal_weight
        }
    
    def to_dict(self) -> dict:
        """Export configuration as dictionary"""
        return {
            'token_budget': self.token_budget,
            'top_k': self.top_k,
            'walk_depth': self.walk_depth,
            'embedding_model': self.embedding_model,
            'think_cycle_nodes': self.think_cycle_nodes,
            'access_weight': self.access_weight,
            'temporal_weight': self.temporal_weight,
            'similarity_threshold': self.similarity_threshold,
            'scoring_weights': self.get_scoring_weights()
        }
    
    def __repr__(self) -> str:
        """String representation of configuration"""
        return f"CashewConfig({self.to_dict()})"

# Global configuration instance
config = CashewConfig()

# Convenience functions for accessing config values
def get_token_budget() -> int:
    """Get the current token budget for context injection"""
    return config.token_budget

def get_top_k() -> int:
    """Get the number of top results to retrieve"""
    return config.top_k

def get_walk_depth() -> int:
    """Get the graph walk depth for context expansion"""
    return config.walk_depth

def get_embedding_model() -> str:
    """Get the embedding model identifier"""
    return config.embedding_model

def get_think_cycle_nodes() -> int:
    """Get the number of nodes to use in think cycles"""
    return config.think_cycle_nodes

def get_scoring_weights() -> dict:
    """Get the current scoring weights for hybrid retrieval"""
    return config.get_scoring_weights()

def reload_config():
    """Reload configuration from environment variables"""
    global config
    config = CashewConfig()

if __name__ == "__main__":
    import json
    print("Cashew Configuration:")
    print(json.dumps(config.to_dict(), indent=2))