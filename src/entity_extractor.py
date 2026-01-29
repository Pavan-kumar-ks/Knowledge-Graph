# Add missing typing imports for Dict, Any, List
from typing import Any, Dict, List


# --- spaCy-based Entity and Relationship Extractor ---
class SpacyEntityExtractor:
    """Entity and relationship extractor using spaCy NLP."""
    def __init__(self):
        self.stats = {
            "chunks_processed": 0,
            "chunks_with_entities": 0,
            "total_entities": 0,
            "total_relationships": 0,
            "unique_entities": {
                "policies": set(),
                "institutions": set(),
                "sectors": set(),
                "strategies": set(),
                "countries": set(),
                "people": set(),
                "locations": set(),
                "other": set(),
            }
        }

    def enrich_chunk(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        chunk_id = chunk.get("chunk_id", "unknown")
        text = chunk.get("text", "")
        if not text:
            chunk["entities"] = []
            chunk["relationships"] = []
            return chunk
        entities = spacy_extract_entities(text)
        relationships = spacy_extract_relationships(text, entities)
        chunk["entities"] = entities
        chunk["relationships"] = relationships
        # Update statistics
        self.stats["chunks_processed"] += 1
        if entities or relationships:
            self.stats["chunks_with_entities"] += 1
        self.stats["total_entities"] += len(entities)
        self.stats["total_relationships"] += len(relationships)
        for entity in entities:
            entity_type = entity.get("type", "other")
            entity_text = entity.get("text", "")
            if entity_type in self.stats["unique_entities"] and entity_text:
                self.stats["unique_entities"][entity_type].add(entity_text.lower())
        return chunk

    def enrich_chunks(self, chunks: List[Dict[str, Any]], batch_size: int = 1, delay: float = 0.0) -> List[Dict[str, Any]]:
        import time
        enriched = []
        for i, chunk in enumerate(chunks):
            enriched_chunk = self.enrich_chunk(chunk)
            enriched.append(enriched_chunk)
            if delay > 0:
                time.sleep(delay)
            if (i + 1) % batch_size == 0 or (i + 1) == len(chunks):
                logger.info(f"[spaCy] Progress: {i + 1}/{len(chunks)} chunks processed")
        return enriched

    def get_statistics(self):
        """Return extraction statistics for reporting."""
        return self.stats
def spacy_extract_relationships(text: str, entities: list) -> list:
    """
    Extract relationships between entities using spaCy dependency parsing and pattern matching.
    Returns a list of dicts: {"source": ..., "target": ..., "type": ..., "context": ...}
    """
    doc = _SPACY_NLP(text)
    rels = []
    # Build lookup by type for schema node types
    by_type = {}
    for ent in entities:
        by_type.setdefault(ent["type"], []).append(ent)

    # Core Relationships (simple co-occurrence and keyword rules)
    # (Country)-[:HAS_POLICY]->(Policy)
    for country in by_type.get("Country", []):
        for policy in by_type.get("Policy", []):
            if country["name"] in text and policy["title"] in text:
                rels.append({"source": country["name"], "target": policy["title"], "type": "HAS_POLICY", "context": text})

    # (Policy)-[:APPLIES_TO_DOMAIN]->(TechDomain)
    for policy in by_type.get("Policy", []):
        for domain in by_type.get("TechDomain", []):
            rels.append({"source": policy["title"], "target": domain["name"], "type": "APPLIES_TO_DOMAIN", "context": text})

    # (Policy)-[:APPLIES_TO_EQUIPMENT]->(Equipment)
    for policy in by_type.get("Policy", []):
        for equip in by_type.get("Equipment", []):
            rels.append({"source": policy["title"], "target": equip["name"], "type": "APPLIES_TO_EQUIPMENT", "context": text})

    # (Policy)-[:REQUIRES]->(Requirement)
    for policy in by_type.get("Policy", []):
        for req in by_type.get("Requirement", []):
            rels.append({"source": policy["title"], "target": req.get("type_label", "Requirement"), "type": "REQUIRES", "context": text})

    # (Requirement)-[:REQUIRES_DOCUMENT]->(Document)
    for req in by_type.get("Requirement", []):
        for docu in by_type.get("Document", []):
            rels.append({"source": req.get("type_label", "Requirement"), "target": docu["name"], "type": "REQUIRES_DOCUMENT", "context": text})

    # (Requirement)-[:SUBMITTED_TO]->(Authority)
    for req in by_type.get("Requirement", []):
        for auth in by_type.get("Authority", []):
            rels.append({"source": req.get("type_label", "Requirement"), "target": auth["name"], "type": "SUBMITTED_TO", "context": text})

    # (Equipment)-[:BELONGS_TO_DOMAIN]->(TechDomain)
    for equip in by_type.get("Equipment", []):
        for domain in by_type.get("TechDomain", []):
            rels.append({"source": equip["name"], "target": domain["name"], "type": "BELONGS_TO_DOMAIN", "context": text})

    # (Equipment)-[:CLASSIFIED_UNDER]->(Policy)
    for equip in by_type.get("Equipment", []):
        for policy in by_type.get("Policy", []):
            rels.append({"source": equip["name"], "target": policy["title"], "type": "CLASSIFIED_UNDER", "context": text})

    return rels
import spacy

# Load spaCy model globally for efficiency
_SPACY_NLP = spacy.load("en_core_web_sm")

def spacy_extract_entities(text: str) -> list:
    """
    Extract entities from text using spaCy NER and map to schema node types and attributes.
    Returns a list of dicts: {"type": ..., ...attributes...}
    """
    doc = _SPACY_NLP(text)
    results = []
    # Country extraction (GPE, LOC)
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC"]:
            results.append({
                "type": "Country",
                "name": ent.text,
                # iso_code and region could be added with external lookup if needed
            })
    # Authority (ORG, with keywords)
    for ent in doc.ents:
        if ent.label_ == "ORG" and any(k in ent.text.lower() for k in ["authority", "agency", "ministry", "cdsco", "board", "commission", "council"]):
            results.append({
                "type": "Authority",
                "name": ent.text,
                # level/website could be added with more context or rules
            })
    # Policy (LAW, or ORG with 'policy', 'act', 'regulation', 'rule')
    for ent in doc.ents:
        if ent.label_ == "LAW" or (ent.label_ == "ORG" and any(k in ent.text.lower() for k in ["policy", "act", "regulation", "rule"])):
            results.append({
                "type": "Policy",
                "title": ent.text,
                # policy_id, summary, effective_date, version could be extracted with more advanced rules
            })
    # Equipment (PRODUCT, or ORG with device keywords)
    for ent in doc.ents:
        if ent.label_ == "PRODUCT" or (ent.label_ == "ORG" and any(k in ent.text.lower() for k in ["device", "equipment", "system", "machine", "scanner", "imaging"])):
            results.append({
                "type": "Equipment",
                "name": ent.text,
                # category, risk_class could be extracted with more advanced rules
            })
    # TechDomain (custom: look for keywords in text)
    tech_keywords = ["ai", "artificial intelligence", "medical device", "health it", "imaging", "software"]
    for kw in tech_keywords:
        if kw in text.lower():
            results.append({
                "type": "TechDomain",
                "name": kw.title(),
            })
    # Requirement (look for keywords in text)
    req_keywords = ["registration", "approval", "reporting", "requirement", "mandatory", "submission"]
    for kw in req_keywords:
        if kw in text.lower():
            results.append({
                "type": "Requirement",
                "type_label": kw.title(),
                # requirement_id, description, mandatory could be extracted with more advanced rules
            })
    # Document (look for keywords in text)
    doc_keywords = ["pdf", "form", "document", "submission"]
    for kw in doc_keywords:
        if kw in text.lower():
            results.append({
                "type": "Document",
                "name": kw.title(),
                # format, submission_mode could be extracted with more advanced rules
            })
    return results
"""
Entity and relationship extraction module using Groq LLM.
Extracts named entities and their relationships from text chunks.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """You are an expert at extracting structured information from policy and governance documents.

Extract the following from the text:

1. **Entities**: Identify and categorize entities into these types:
     - policies: Policy names, acts, regulations
     - institutions: Government bodies, ministries, organizations
     - sectors: Industry sectors, domains
     - strategies: Strategic initiatives, programs
     - countries: Nations, regions
     - people: Named individuals, officials
     - locations: Cities, states, specific places

2. **Relationships**: Identify relationships between entities with these types:
     - IMPLEMENTS: An institution implements a policy
     - GOVERNS: An institution governs a sector
     - RELATED_TO: General relationship between entities
     - MENTIONED_IN: Entity mentioned in context of another
     - COLLABORATES_WITH: Entities working together

Return ONLY valid JSON in this exact format:
{{
    "entities": [
        {{"text": "entity name", "type": "entity_type", "confidence": 0.95}}
    ],
    "relationships": [
        {{"source": "entity1", "target": "entity2", "type": "relationship_type", "context": "brief context"}}
    ]
}}

Text to analyze:
---
{text}
---

JSON Output:"""


class GroqEntityExtractor:
    """Entity and relationship extractor using Groq LLM."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        max_retries: int = 3,
        timeout: int = 60,
        max_total_timeout: int = 120
    ):
        """
        Initialize Groq entity extractor.
        
        Args:
            api_key: Groq API key
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            max_retries: Maximum retry attempts
            timeout: Request timeout in seconds
        """
        if not api_key:
            raise ValueError("Groq API key is required")
        
        self.client = Groq(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.timeout = timeout
        
        self.max_total_timeout = max_total_timeout
        self.stats = {
                "chunks_processed": 0,
                "chunks_with_entities": 0,
                "total_entities": 0,
                "total_relationships": 0,
                "api_calls": 0,
                "api_errors": 0,
                "unique_entities": {
                    "policies": set(),
                    "institutions": set(),
                    "sectors": set(),
                    "strategies": set(),
                    "countries": set(),
                    "people": set(),
                    "locations": set()
            }
        }
        
        def enrich_chunks(self, chunks: List[Dict[str, Any]], batch_size: int = 1, delay: float = 0.0) -> List[Dict[str, Any]]:
            """Enrich chunks with extracted entities and relationships."""
            enriched = []
            for i, chunk in enumerate(chunks):
                enriched_chunk = self.enrich_chunk(chunk)
                enriched.append(enriched_chunk)
                if delay > 0:
                    time.sleep(delay)  # Add delay after each API call to avoid rate limits
                # Progress logging
                if (i + 1) % batch_size == 0 or (i + 1) == len(chunks):
                    logger.info(f"Progress: {i + 1}/{len(chunks)} chunks processed")
            
            self._log_statistics()
            
            return enriched
    
    def _log_statistics(self) -> None:
        """Log extraction statistics."""
        logger.info("=" * 60)
        logger.info("📊 Extraction Statistics")
        logger.info("=" * 60)
        logger.info(f"✅ Chunks processed: {self.stats['chunks_processed']}")
        logger.info(f"   Chunks with entities: {self.stats['chunks_with_entities']}")
        logger.info(f"   Total entities extracted: {self.stats['total_entities']}")
        logger.info(f"   Total relationships: {self.stats['total_relationships']}")
        logger.info(f"   API calls made: {self.stats['api_calls']}")
        logger.info(f"   API errors: {self.stats['api_errors']}")
        
        logger.info("\n📋 Unique Entities by Type:")
        total_unique = 0
        for entity_type, entities in self.stats["unique_entities"].items():
            count = len(entities)
            logger.info(f"   - {entity_type}: {count}")
            total_unique += count
        
        logger.info(f"   Total unique entities: {total_unique}")
        logger.info("=" * 60)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        return {
            "chunks_processed": self.stats["chunks_processed"],
            "chunks_with_entities": self.stats["chunks_with_entities"],
            "total_entities": self.stats["total_entities"],
            "total_relationships": self.stats["total_relationships"],
            "api_calls": self.stats["api_calls"],
            "api_errors": self.stats["api_errors"],
            "unique_entity_counts": {
                k: len(v) for k, v in self.stats["unique_entities"].items()
            }
        }


def process_chunks(
    input_path: str,
    output_path: str,
    api_key: str,
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.1,
    max_tokens: int = 2000
) -> Dict[str, Any]:
    """
    Process chunks file and extract entities using Groq.
    
    Args:
        input_path: Path to input chunks.json
        output_path: Path to output chunks_with_entities.json
        api_key: Groq API key
        model: Groq model to use
        temperature: Sampling temperature
        max_tokens: Maximum tokens
        
    Returns:
        Extraction statistics
    """
    input_file = Path(input_path)
    output_file = Path(output_path)
    
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    logger.info(f"Loading chunks from {input_file}")
    
    with open(input_file, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    logger.info(f"Loaded {len(chunks)} chunks")
    
    # Extract entities and relationships
    extractor = GroqEntityExtractor(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    chunks_with_entities = extractor.enrich_chunks(chunks)
    
    # Save output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(chunks_with_entities, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ Saved enriched chunks to {output_file}")
    
    return extractor.get_statistics()


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from src.config import config
    
    try:
        if not config.GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY not found. Please set it in your .env file or environment."
            )
        
        stats = process_chunks(
            str(config.CHUNKS_FILE),
            str(config.CHUNKS_ENTITIES_FILE),
            config.GROQ_API_KEY,
            config.GROQ_MODEL,
            config.GROQ_TEMPERATURE,
            config.GROQ_MAX_TOKENS
        )
        
        print("\n📊 Final Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
            
    except Exception as e:
        logger.error(f"Failed to process chunks: {e}", exc_info=True)



