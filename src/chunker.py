"""
Text chunking module.
Splits documents into sections and chunks with semantic awareness.
"""

import json
import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def is_header(line: str) -> bool:
    """
    Check if a line is a header.
    
    Headers are identified by:
    - Numbered format (1., 1.1, 2.0, etc.)
    - ALL CAPS text
    - Common header patterns
    
    Args:
        line: Line of text to check
        
    Returns:
        True if line is a header
    """
    line = line.strip()
    
    if len(line) < 3:
        return False
    
    # Matches: "1.", "1.1", "2.0", etc.
    if re.match(r"^\d+(\.\d+)*\.?\s+", line):
        return True
    
    # ALL CAPS headings (not too long)
    if line.isupper() and 3 <= len(line) < 80:
        return True
    
    # Common header patterns
    header_keywords = ['chapter', 'section', 'introduction', 'conclusion', 'summary', 'overview']
    if any(line.lower().startswith(kw) for kw in header_keywords):
        return True
    
    return False


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences using regex patterns.
    
    Args:
        text: Text to split
        
    Returns:
        List of sentences
    """
    # Handle common abbreviations
    text = re.sub(r'\bDr\.', 'Dr<DOT>', text)
    text = re.sub(r'\bMr\.', 'Mr<DOT>', text)
    text = re.sub(r'\bMrs\.', 'Mrs<DOT>', text)
    text = re.sub(r'\bMs\.', 'Ms<DOT>', text)
    text = re.sub(r'\bi\.e\.', 'i<DOT>e<DOT>', text)
    text = re.sub(r'\be\.g\.', 'e<DOT>g<DOT>', text)
    
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    
    # Restore abbreviations
    sentences = [s.replace('<DOT>', '.') for s in sentences]
    
    return [s.strip() for s in sentences if s.strip()]


def split_into_sections(text: str) -> List[Dict[str, str]]:
    """
    Split text into sections based on headers.
    
    Args:
        text: Raw text content
        
    Returns:
        List of dicts with 'header' and 'content' keys
    """
    sections = []
    current_header = "Introduction"
    current_text = []
    
    lines = text.split("\n")
    
    for line in lines:
        line = line.strip()
        
        if is_header(line):
            # Save previous section
            if current_text:
                sections.append({
                    "header": current_header,
                    "content": "\n".join(current_text)
                })
                current_text = []
            
            current_header = line
        else:
            if line:
                current_text.append(line)
    
    # Save last section
    if current_text:
        sections.append({
            "header": current_header,
            "content": "\n".join(current_text)
        })
    
    logger.debug(f"Split text into {len(sections)} sections")
    return sections


def chunk_text_semantic(
    text: str, 
    chunk_size: int = 1024, 
    overlap: int = 200,
    min_chunk_size: int = 100
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Split text into semantic chunks with overlap and metadata.
    
    Args:
        text: Text to chunk
        chunk_size: Target number of characters per chunk
        overlap: Number of characters to overlap between chunks
        min_chunk_size: Minimum chunk size to avoid tiny fragments
        
    Returns:
        List of tuples (chunk_text, metadata)
    """
    # Split into sentences for semantic boundaries
    sentences = split_into_sentences(text)
    
    chunks = []
    current_chunk = []
    current_length = 0
    sentence_start_idx = 0
    
    for i, sentence in enumerate(sentences):
        sentence_len = len(sentence)
        
        # If adding this sentence exceeds chunk_size
        if current_length + sentence_len > chunk_size and current_chunk:
            # Save current chunk
            chunk_text = " ".join(current_chunk)
            if len(chunk_text) >= min_chunk_size:
                metadata = {
                    "char_count": len(chunk_text),
                    "word_count": len(chunk_text.split()),
                    "sentence_count": len(current_chunk),
                    "start_sentence": sentence_start_idx,
                    "end_sentence": i - 1
                }
                chunks.append((chunk_text, metadata))
            
            # Calculate overlap sentences
            overlap_chars = 0
            overlap_sentences = []
            for sent in reversed(current_chunk):
                overlap_chars += len(sent)
                overlap_sentences.insert(0, sent)
                if overlap_chars >= overlap:
                    break
            
            # Start new chunk with overlap
            current_chunk = overlap_sentences + [sentence]
            current_length = sum(len(s) for s in current_chunk)
            sentence_start_idx = i - len(overlap_sentences)
        else:
            current_chunk.append(sentence)
            current_length += sentence_len
    
    # Save last chunk
    if current_chunk:
        chunk_text = " ".join(current_chunk)
        if len(chunk_text) >= min_chunk_size:
            metadata = {
                "char_count": len(chunk_text),
                "word_count": len(chunk_text.split()),
                "sentence_count": len(current_chunk),
                "start_sentence": sentence_start_idx,
                "end_sentence": len(sentences) - 1
            }
            chunks.append((chunk_text, metadata))
    
    logger.debug(f"Created {len(chunks)} semantic chunks from {len(sentences)} sentences")
    return chunks


def create_chunks(
    docs: Dict[str, str], 
    chunk_size: int = 1024,
    overlap: int = 200,
    min_chunk_size: int = 100
) -> List[Dict[str, Any]]:
    """
    Create semantic chunks from documents with section information.
    
    Args:
        docs: Dictionary mapping document names to text content
        chunk_size: Target characters per chunk
        overlap: Character overlap between chunks
        min_chunk_size: Minimum chunk size
        
    Returns:
        List of chunk dictionaries with metadata
    """
    all_chunks = []
    chunk_global_id = 0
    
    for doc_name, text in docs.items():
        logger.info(f"Processing document: {doc_name}")
        sections = split_into_sections(text)
        
        for section_idx, section in enumerate(sections):
            section_chunks = chunk_text_semantic(
                section["content"], 
                chunk_size, 
                overlap,
                min_chunk_size
            )
            
            for chunk_idx, (chunk_text, metadata) in enumerate(section_chunks):
                all_chunks.append({
                    "chunk_id": chunk_global_id,
                    "document": doc_name,
                    "section": section["header"],
                    "section_index": section_idx,
                    "chunk_index": chunk_idx,
                    "text": chunk_text,
                    "metadata": metadata
                })
                chunk_global_id += 1
    
    logger.info(f"Created {len(all_chunks)} total chunks from {len(docs)} documents")
    return all_chunks


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from src.config import config
    from src.pdf_loader import load_all_pdfs
    
    try:
        logger.info(f"Loading PDFs from {config.PDF_DIR}")
        docs = load_all_pdfs(str(config.PDF_DIR))
        
        chunks = create_chunks(
            docs,
            chunk_size=config.CHUNK_SIZE,
            overlap=config.CHUNK_OVERLAP,
            min_chunk_size=config.MIN_CHUNK_SIZE
        )
        
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(config.CHUNKS_FILE, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Saved {len(chunks)} semantic chunks to {config.CHUNKS_FILE}")
    except Exception as e:
        logger.error(f"Failed to create chunks: {e}", exc_info=True)
