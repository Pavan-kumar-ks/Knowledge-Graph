"""
Main pipeline orchestrator.
Coordinates the entire policy knowledge graph pipeline:
PDF loading → Chunking → Entity extraction → Neo4j loading
"""

from dotenv import load_dotenv

load_dotenv()

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

from src.chunker import create_chunks
from src.entity_extractor import SpacyEntityExtractor
from src.neo4j_loader import load_graph
from src.pdf_loader import PDFLoader
from src.utils import setup_logging

# Paths and files
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
CHUNKS_FILE = OUTPUT_DIR / "chunks.json"
CHUNKS_ENTITIES_FILE = OUTPUT_DIR / "chunks_with_entities.json"
LOG_FILE = LOGS_DIR / "pipeline.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Load settings from environment
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "chandan01245")
NEO4J_TIMEOUT = int(os.getenv("NEO4J_TIMEOUT", "30"))

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1024"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "100"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.1"))
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "2000"))
GROQ_MAX_RETRIES = int(os.getenv("GROQ_MAX_RETRIES", "3"))
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", "60"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Setup logging
setup_logging(
    log_level=LOG_LEVEL,
    log_file=LOG_FILE,
    log_format=LOG_FORMAT
)

logger = logging.getLogger(__name__)


class PolicyGraphPipeline:
    """Orchestrates the entire pipeline."""
    
    def __init__(self):
        self.pdf_loader = PDFLoader(PDF_DIR)
        
        # Use spaCy-based entity extractor
        self.entity_extractor = SpacyEntityExtractor()
        
        self.stats = {}
    
    def run(self, pdf_filename: str = None) -> Dict[str, Any]:
        """
        Execute full pipeline.
        
        Args:
            pdf_filename: Specific PDF to process (all PDFs if None)
            
        Returns:
            Pipeline statistics
        """
        logger.info("=" * 60)
        logger.info("Starting Policy Knowledge Graph Pipeline")
        logger.info("=" * 60)
        
        try:
            # Step 1: Load PDFs
            docs = self._load_pdfs(pdf_filename)
            if not docs:
                logger.error("No documents loaded")
                return {"status": "failed", "reason": "No documents loaded"}
            
            # Step 2: Create chunks
            chunks = self._create_chunks(docs)
            if not chunks:
                logger.error("No chunks created")
                return {"status": "failed", "reason": "No chunks created"}
            
            # Step 3: Extract entities
            chunks_with_entities = self._extract_entities(chunks)
            
            # Step 4: Load to Neo4j
            self._load_to_neo4j(chunks_with_entities)
            
            logger.info("=" * 60)
            logger.info("Pipeline completed successfully")
            logger.info("=" * 60)
            
            return {
                "status": "success",
                "documents_loaded": len(docs),
                "chunks_created": len(chunks),
                "chunks_with_entities": len(chunks_with_entities),
                "entity_stats": self.entity_extractor.get_statistics()
            }
        
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}
    
    def _load_pdfs(self, pdf_filename: str = None) -> Dict[str, str]:
        """Load PDFs from directory."""
        logger.info("Step 1: Loading PDFs...")
        if pdf_filename:
            text = self.pdf_loader.load_pdf_text(PDF_DIR / pdf_filename)
            docs = {pdf_filename: text}
        else:
            docs = self.pdf_loader.load_all_pdfs()
        return docs
    
    def _create_chunks(self, docs: Dict[str, str]) -> list:
        """Create chunks from documents."""
        logger.info("Step 2: Creating semantic chunks...")
        chunks = create_chunks(
            docs,
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
            min_chunk_size=MIN_CHUNK_SIZE
        )
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        import json
        with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(chunks)} chunks to {CHUNKS_FILE}")
        return chunks
    
    def _extract_entities(self, chunks: list) -> list:
        """Extract entities from chunks."""
        logger.info("Step 3: Extracting entities and relationships with Groq...")
        chunks_with_entities = self.entity_extractor.enrich_chunks(chunks)
        import json
        with open(CHUNKS_ENTITIES_FILE, "w", encoding="utf-8") as f:
            json.dump(chunks_with_entities, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved enriched chunks to {CHUNKS_ENTITIES_FILE}")
        return chunks_with_entities
    
    def _load_to_neo4j(self, chunks: list) -> None:
        """Load chunks to Neo4j."""
        logger.info("Step 4: Loading to Neo4j...")
        result = load_graph(
            NEO4J_URI,
            NEO4J_USER,
            NEO4J_PASSWORD,
            chunks,
            chunk_size=BATCH_SIZE
        )
        if result["status"] != "success":
            raise RuntimeError("Failed to load graph to Neo4j")


if __name__ == "__main__":
    # Optional: specify PDF filename as command-line argument
    pdf_filename = sys.argv[1] if len(sys.argv) > 1 else None
    
    pipeline = PolicyGraphPipeline()
    result = pipeline.run(pdf_filename)
    
    print("\n📊 Pipeline Result:")
    for key, value in result.items():
        print(f"  {key}: {value}")
