"""
Unit tests for entity extraction module.
"""

import pytest

from src.entity_extractor import (EntityExtractor, extract_entities_from_text,
                                  normalize_text)


class TestNormalizeText:
    """Tests for text normalization."""
    
    def test_lowercase_conversion(self):
        """Test conversion to lowercase."""
        text = "HELLO World"
        normalized = normalize_text(text)
        assert normalized == normalized.lower()
    
    def test_punctuation_removal(self):
        """Test punctuation removal."""
        text = "Hello, World! How are you?"
        normalized = normalize_text(text)
        assert "," not in normalized
        assert "!" not in normalized
    
    def test_whitespace_normalization(self):
        """Test multiple spaces normalized to single space."""
        text = "Hello    World"
        normalized = normalize_text(text)
        assert "    " not in normalized


class TestExtractEntitiesFromText:
    """Tests for entity extraction."""
    
    def test_extract_policy(self):
        """Test policy extraction."""
        text = "The tariff policy was established."
        entities = extract_entities_from_text(text)
        assert len(entities["policies"]) > 0
    
    def test_extract_institution(self):
        """Test institution extraction."""
        text = "The Ministry of Power announced changes."
        entities = extract_entities_from_text(text)
        assert len(entities["institutions"]) > 0
    
    def test_extract_multiple_entities(self):
        """Test extracting multiple entity types."""
        text = "The Government of India implements the tariff policy in the energy sector."
        entities = extract_entities_from_text(text)
        assert len(entities["institutions"]) > 0
        assert len(entities["policies"]) > 0
        assert len(entities["sectors"]) > 0
    
    def test_no_entities(self):
        """Test text with no entities."""
        text = "This is random text with nothing."
        entities = extract_entities_from_text(text)
        total_entities = sum(len(v) for v in entities.values())
        assert total_entities == 0


class TestEntityExtractor:
    """Tests for EntityExtractor class."""
    
    def test_enrich_chunk(self):
        """Test enriching a single chunk."""
        extractor = EntityExtractor()
        chunk = {
            "document": "test.pdf",
            "section": "Introduction",
            "chunk_id": 0,
            "text": "The Government of India policy"
        }
        enriched = extractor.enrich_chunk(chunk)
        assert "entities" in enriched
        assert len(enriched["entities"]) > 0
    
    def test_enrich_chunks(self):
        """Test enriching multiple chunks."""
        extractor = EntityExtractor()
        chunks = [
            {
                "document": "test.pdf",
                "section": "Intro",
                "chunk_id": 0,
                "text": "Government of India policy"
            },
            {
                "document": "test.pdf",
                "section": "Methods",
                "chunk_id": 1,
                "text": "Energy sector analysis"
            }
        ]
        enriched = extractor.enrich_chunks(chunks)
        assert len(enriched) == 2
        stats = extractor.get_statistics()
        assert stats["chunks_processed"] == 2
    
    def test_statistics(self):
        """Test statistics collection."""
        extractor = EntityExtractor()
        chunk = {
            "document": "test.pdf",
            "section": "Intro",
            "chunk_id": 0,
            "text": "Government of India and Ministry of Power"
        }
        extractor.enrich_chunk(chunk)
        stats = extractor.get_statistics()
        assert "chunks_processed" in stats
        assert "total_mentions" in stats
