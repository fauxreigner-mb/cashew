#!/usr/bin/env python3
"""Tests for integration/session.py"""

import os
import pytest
from unittest.mock import patch, MagicMock

from integration.session import (
    generate_session_context,
    extract_from_conversation,
    run_think_cycle,
    run_tension_detection,
    integrate_with_openclaw,
)
from core.session import ExtractionResult, ThinkResult


class TestGenerateSessionContext:
    def test_missing_db(self, tmp_path):
        result = generate_session_context(str(tmp_path / "nonexistent.db"))
        assert result == ""

    def test_with_valid_db(self, temp_db_with_data):
        # May return empty if no embeddings/vec, but should not crash
        result = generate_session_context(temp_db_with_data)
        assert isinstance(result, str)

    def test_with_hints(self, temp_db_with_data):
        result = generate_session_context(temp_db_with_data, hints=["tech", "programming"])
        assert isinstance(result, str)

    def test_with_tags(self, temp_db_with_data):
        result = generate_session_context(temp_db_with_data, tags=["engineering"])
        assert isinstance(result, str)

    def test_with_exclude_tags(self, temp_db_with_data):
        result = generate_session_context(temp_db_with_data, exclude_tags=["vault:private"])
        assert isinstance(result, str)


class TestExtractFromConversation:
    def test_missing_db(self, tmp_path):
        result = extract_from_conversation(str(tmp_path / "nonexistent.db"), "some text")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_no_model_fn(self, temp_db_with_data):
        result = extract_from_conversation(temp_db_with_data, "Testing extraction", model_fn=None)
        assert isinstance(result, dict)
        assert "success" in result

    def test_with_model_fn(self, temp_db_with_data):
        mock_model = MagicMock(return_value='{"nodes": [], "edges": []}')
        result = extract_from_conversation(
            temp_db_with_data, "The sky is blue", model_fn=mock_model
        )
        assert isinstance(result, dict)
        assert "new_nodes" in result

    def test_with_session_id(self, temp_db_with_data):
        result = extract_from_conversation(
            temp_db_with_data, "Hello", session_id="test-session-123"
        )
        assert isinstance(result, dict)


class TestRunThinkCycle:
    def test_missing_db(self, tmp_path):
        result = run_think_cycle(str(tmp_path / "nonexistent.db"))
        assert result["success"] is False

    def test_no_model_fn(self, temp_db_with_data):
        result = run_think_cycle(temp_db_with_data)
        assert result["success"] is False
        assert "no model function" in result["error"].lower() or "No model" in result["error"]

    def test_with_focus_domain(self, temp_db_with_data):
        result = run_think_cycle(temp_db_with_data, focus_domain="tech")
        assert result["success"] is False  # no model_fn


class TestRunTensionDetection:
    def test_missing_db(self, tmp_path):
        result = run_tension_detection(str(tmp_path / "nonexistent.db"))
        assert result["success"] is False

    def test_no_model_fn(self, temp_db_with_data):
        result = run_tension_detection(temp_db_with_data)
        assert result["success"] is False


class TestIntegrateWithOpenclaw:
    def test_context_operation(self, temp_db_with_data):
        result = integrate_with_openclaw(temp_db_with_data, "context")
        assert result["success"] is True
        assert result["operation"] == "context"

    def test_context_with_hints(self, temp_db_with_data):
        result = integrate_with_openclaw(temp_db_with_data, "context", hints=["tech"])
        assert result["success"] is True

    def test_extract_operation(self, temp_db_with_data):
        result = integrate_with_openclaw(
            temp_db_with_data, "extract", conversation_text="Testing"
        )
        assert result["operation"] == "extract"

    def test_think_operation(self, temp_db_with_data):
        result = integrate_with_openclaw(temp_db_with_data, "think")
        assert result["operation"] == "think"

    def test_unknown_operation(self, temp_db_with_data):
        result = integrate_with_openclaw(temp_db_with_data, "foobar")
        assert result["success"] is False
        assert "Unknown" in result["error"]
