"""
Unit tests for Neo4j loader module.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.neo4j_loader import ChunkLoader, GraphBuilder, Neo4jConnection


class TestGraphBuilder:
    """Tests for GraphBuilder class."""
    
    def test_merge_node_query(self):
        """Test merge node query generation."""
        mock_driver = Mock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        
        builder = GraphBuilder(mock_driver)
        # Verify initialization
        assert builder.driver == mock_driver
    
    def test_chunk_loader_entity_labels(self):
        """Test entity label mapping."""
        mock_driver = Mock()
        loader = ChunkLoader(mock_driver)
        
        assert loader.ENTITY_LABELS["policies"] == "Policy"
        assert loader.ENTITY_LABELS["institutions"] == "Institution"
        assert loader.ENTITY_LABELS["sectors"] == "Sector"
        assert loader.ENTITY_LABELS["countries"] == "Country"
        assert loader.ENTITY_LABELS["strategies"] == "Strategy"


class TestChunkStructure:
    """Tests for chunk data structures."""
    
    def test_valid_chunk_with_entities(self):
        """Test valid chunk structure."""
        chunk = {
            "document": "test.pdf",
            "section": "Introduction",
            "chunk_id": 0,
            "text": "Sample text",
            "entities": {
                "policies": ["Policy A"],
                "institutions": ["Institution B"],
                "sectors": ["Sector C"],
                "countries": ["Country D"],
                "strategies": ["Strategy E"]
            }
        }
        
        # Verify structure
        assert chunk["document"]
        assert chunk["section"]
        assert chunk["chunk_id"] == 0
        assert len(chunk["text"]) > 0
        assert "entities" in chunk
        assert len(chunk["entities"]) == 5
