"""
Unit tests for text chunking module.
"""

import pytest

from src.chunker import (chunk_text, create_chunks, is_header,
                         split_into_sections)


class TestIsHeader:
    """Tests for header detection."""
    
    def test_numbered_header(self):
        """Test numbered header detection."""
        assert is_header("1. Introduction")
        assert is_header("1.2.3 Subsection")
        assert is_header("2.0 Section")
    
    def test_caps_header(self):
        """Test all-caps header detection."""
        assert is_header("INTRODUCTION")
        assert is_header("METHODS AND ANALYSIS")
        assert not is_header("VERY LONG HEADER THAT EXCEEDS THE LENGTH LIMIT FOR CAPS HEADINGS IN THE SYSTEM")
    
    def test_non_header(self):
        """Test non-header text."""
        assert not is_header("This is normal text")
        assert not is_header("Hello world")
        assert not is_header("")
        assert not is_header("Hi")


class TestSplitIntoSections:
    """Tests for section splitting."""
    
    def test_single_section(self):
        """Test text with single section."""
        text = "Introduction\nThis is content."
        sections = split_into_sections(text)
        assert len(sections) == 1
        assert sections[0]["header"] == "Introduction"
    
    def test_multiple_sections(self):
        """Test text with multiple sections."""
        text = "1. Section One\nContent one\n2. Section Two\nContent two"
        sections = split_into_sections(text)
        assert len(sections) == 2
        assert sections[0]["header"] == "1. Section One"
        assert sections[1]["header"] == "2. Section Two"
    
    def test_empty_text(self):
        """Test empty text."""
        sections = split_into_sections("")
        assert len(sections) == 0


class TestChunkText:
    """Tests for text chunking."""
    
    def test_chunk_size(self):
        """Test chunk size enforcement."""
        text = " ".join(["word"] * 100)
        chunks = chunk_text(text, chunk_size=50)
        assert len(chunks) == 2
        assert len(chunks[0].split()) == 50
    
    def test_small_text(self):
        """Test chunking small text."""
        text = "one two three"
        chunks = chunk_text(text, chunk_size=10)
        assert len(chunks) == 1
        assert chunks[0] == text


class TestCreateChunks:
    """Tests for full chunk creation."""
    
    def test_create_chunks_basic(self):
        """Test basic chunk creation."""
        docs = {
            "doc1.pdf": "1. Section\n" + " ".join(["word"] * 100)
        }
        chunks = create_chunks(docs)
        assert len(chunks) > 0
        assert all("document" in c for c in chunks)
        assert all("section" in c for c in chunks)
        assert all("chunk_id" in c for c in chunks)
        assert all("text" in c for c in chunks)
    
    def test_document_name_preserved(self):
        """Test document name is preserved."""
        docs = {"test.pdf": "1. Section\nContent"}
        chunks = create_chunks(docs)
        assert all(c["document"] == "test.pdf" for c in chunks)
