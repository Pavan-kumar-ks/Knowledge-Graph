"""
Quick test script to validate improvements.
Run this to check if everything is working correctly.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.chunker import split_into_sentences, chunk_text_semantic, is_header

def test_config():
    """Test configuration loading."""
    print("=" * 60)
    print("🧪 Testing Configuration")
    print("=" * 60)
    
    assert config.CHUNK_SIZE > 0, "Invalid chunk size"
    assert config.CHUNK_OVERLAP >= 0, "Invalid overlap"
    assert config.MIN_CHUNK_SIZE > 0, "Invalid min chunk size"
    assert config.GROQ_MODEL, "Groq model not set"
    
    print(f"✅ Chunk size: {config.CHUNK_SIZE}")
    print(f"✅ Chunk overlap: {config.CHUNK_OVERLAP}")
    print(f"✅ Min chunk size: {config.MIN_CHUNK_SIZE}")
    print(f"✅ Groq model: {config.GROQ_MODEL}")
    print(f"✅ Groq temperature: {config.GROQ_TEMPERATURE}")
    
    if config.GROQ_API_KEY:
        print(f"✅ Groq API key: {'*' * 20}{config.GROQ_API_KEY[-4:]}")
    else:
        print("⚠️  Groq API key: Not set (required for entity extraction)")
    
    print("\n✅ Configuration test passed!\n")


def test_sentence_splitting():
    """Test sentence splitting."""
    print("=" * 60)
    print("🧪 Testing Sentence Splitting")
    print("=" * 60)
    
    test_text = (
        "This is a test. Dr. Smith works at MIT. "
        "The U.S. government passed a new policy. "
        "This is another sentence!"
    )
    
    sentences = split_into_sentences(test_text)
    
    print(f"Input text: {test_text}")
    print(f"\n✅ Split into {len(sentences)} sentences:")
    for i, sent in enumerate(sentences, 1):
        print(f"  {i}. {sent}")
    
    assert len(sentences) >= 3, "Sentence splitting failed"
    print("\n✅ Sentence splitting test passed!\n")


def test_header_detection():
    """Test header detection."""
    print("=" * 60)
    print("🧪 Testing Header Detection")
    print("=" * 60)
    
    test_cases = [
        ("1. Introduction", True),
        ("1.1 Background", True),
        ("CHAPTER 1: OVERVIEW", True),
        ("Regular text here", False),
        ("Introduction to Policy", True),
        ("This is just a sentence.", False),
    ]
    
    for text, expected in test_cases:
        result = is_header(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{text}' -> {result} (expected: {expected})")
        assert result == expected, f"Header detection failed for: {text}"
    
    print("\n✅ Header detection test passed!\n")


def test_semantic_chunking():
    """Test semantic chunking."""
    print("=" * 60)
    print("🧪 Testing Semantic Chunking")
    print("=" * 60)
    
    test_text = (
        "This is the first sentence. This is the second sentence. "
        "This is the third sentence. This is the fourth sentence. "
        "This is the fifth sentence. This is the sixth sentence. "
        "This is the seventh sentence. This is the eighth sentence."
    )
    
    chunks = chunk_text_semantic(test_text, chunk_size=100, overlap=30, min_chunk_size=20)
    
    print(f"Input text length: {len(test_text)} chars")
    print(f"✅ Created {len(chunks)} chunks:")
    
    for i, (chunk_text, metadata) in enumerate(chunks, 1):
        print(f"\n  Chunk {i}:")
        print(f"    Char count: {metadata['char_count']}")
        print(f"    Word count: {metadata['word_count']}")
        print(f"    Sentence count: {metadata['sentence_count']}")
        print(f"    Text preview: {chunk_text[:80]}...")
    
    assert len(chunks) > 0, "No chunks created"
    print("\n✅ Semantic chunking test passed!\n")


def test_groq_import():
    """Test Groq library import."""
    print("=" * 60)
    print("🧪 Testing Groq Import")
    print("=" * 60)
    
    try:
        from groq import Groq
        print("✅ Groq library imported successfully")
        
        from src.entity_extractor import GroqEntityExtractor
        print("✅ GroqEntityExtractor imported successfully")
        
        print("\n✅ Groq import test passed!\n")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("Run: pip install groq")
        raise


def test_data_structure():
    """Test if chunks.json exists and has new structure."""
    print("=" * 60)
    print("🧪 Testing Data Structure")
    print("=" * 60)
    
    chunks_file = config.CHUNKS_FILE
    
    if not chunks_file.exists():
        print(f"⚠️  Chunks file not found: {chunks_file}")
        print("   Run the pipeline to generate chunks")
        return
    
    with open(chunks_file, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    
    print(f"✅ Loaded {len(chunks)} chunks from {chunks_file}")
    
    if chunks:
        sample = chunks[0]
        print(f"\n  Sample chunk structure:")
        print(f"    Keys: {list(sample.keys())}")
        
        if 'metadata' in sample:
            print(f"    ✅ Has metadata: {list(sample['metadata'].keys())}")
        else:
            print(f"    ⚠️  No metadata (old format)")
        
        if 'entities' in sample:
            print(f"    ✅ Has entities field")
        
        if 'relationships' in sample:
            print(f"    ✅ Has relationships field")
    
    print("\n✅ Data structure test passed!\n")


def main():
    """Run all tests."""
    print("\n")
    print("🚀 " + "=" * 56 + " 🚀")
    print("🚀  TESTING IMPROVED PIPELINE                            🚀")
    print("🚀 " + "=" * 56 + " 🚀")
    print("\n")
    
    tests = [
        ("Configuration", test_config),
        ("Sentence Splitting", test_sentence_splitting),
        ("Header Detection", test_header_detection),
        ("Semantic Chunking", test_semantic_chunking),
        ("Groq Import", test_groq_import),
        ("Data Structure", test_data_structure),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name} test failed: {e}\n")
    
    print("\n")
    print("=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Ready to run the pipeline.")
        print("\nNext steps:")
        print("  1. Set GROQ_API_KEY in .env file")
        print("  2. Run: python -m src.pipeline")
    else:
        print("\n⚠️  Some tests failed. Please fix issues before running pipeline.")
    
    print("=" * 60)
    print("\n")


if __name__ == "__main__":
    main()
