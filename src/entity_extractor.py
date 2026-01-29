# Add missing typing imports for Dict, Any, List
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


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
        document = chunk.get("document", None)
        section = chunk.get("section", None)
        if not text:
            chunk["entities"] = []
            chunk["relationships"] = []
            return chunk
        entities = spacy_extract_entities(text)
        # Pass chunk context for provenance
        relationships = spacy_extract_relationships(text, entities, document=document, section=section)
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
def spacy_extract_relationships(text: str, entities: list, document=None, section=None) -> list:
    """
    Extract relationships between entities using spaCy dependency parsing and pattern matching.
    Returns a list of dicts: {"source": ..., "target": ..., "type": ..., provenance...}
    """
    import datetime
    import re
    rels = []
    by_type = {}
    for ent in entities:
        by_type.setdefault(ent["type"], []).append(ent)

    today = datetime.date.today().isoformat()
    def provenance(confidence):
        return {
            "confidence": confidence,
            "extracted_from": document,
            "section": section,
            "extracted_on": today
        }

    # Helper: confidence scoring
    def score_relation(phrase_match, dep_match, type_certainty, same_sentence):
        score = 0.0
        if phrase_match: score += 0.4
        if dep_match: score += 0.3
        if type_certainty: score += 0.2
        if same_sentence: score += 0.1
        return score

    # Helper: get entity by type
    def get_entity_id(ent, t):
        if t == "Policy": return ent.get("policy_id")
        if t == "Country": return ent.get("country_id")
        if t == "Authority": return ent.get("authority_id")
        if t == "TechDomain": return ent.get("domain_id")
        if t == "Equipment": return ent.get("equipment_id")
        if t == "Requirement": return ent.get("requirement_id")
        if t == "Document": return ent.get("document_id")
        return None

    import spacy
    doc = _SPACY_NLP(text)
    # --- Layered rule-based extraction ---
    candidate_rels = []
    for sent in doc.sents:
        sent_text = sent.text.lower()
        sent_ents = [e for e in entities if e.get("name", "").lower() in sent_text or e.get("description", "").lower() in sent_text]
        # APPLIES_IN (Policy → Country)
        for policy in by_type.get("Policy", []):
            for country in by_type.get("Country", []):
                phrase = any(p in sent_text for p in ["applies in", "applicable in", "within", "in accordance with"])
                dep = policy["name"].lower() in sent_text and country["name"].lower() in sent_text
                type_cert = True
                same_sent = True
                conf = score_relation(phrase, dep, type_cert, same_sent)
                if conf >= 0.6:
                    candidate_rels.append({
                        "source": get_entity_id(policy, "Policy"),
                        "target": get_entity_id(country, "Country"),
                        "type": "APPLIES_IN",
                        **provenance(conf)
                    })
        # ISSUED_BY (Policy → Authority)
        for policy in by_type.get("Policy", []):
            for authority in by_type.get("Authority", []):
                phrase = any(p in sent_text for p in ["issued by", "published by", "enacted by", "introduced by"])
                dep = policy["name"].lower() in sent_text and authority["name"].lower() in sent_text
                type_cert = True
                same_sent = True
                conf = score_relation(phrase, dep, type_cert, same_sent)
                if conf >= 0.6:
                    candidate_rels.append({
                        "source": get_entity_id(policy, "Policy"),
                        "target": get_entity_id(authority, "Authority"),
                        "type": "ISSUED_BY",
                        **provenance(conf)
                    })
        # REGULATED_BY (Equipment → Policy)
        for equip in by_type.get("Equipment", []):
            for policy in by_type.get("Policy", []):
                phrase = any(p in sent_text for p in ["regulated under", "governed by", "subject to", "in accordance with"])
                dep = equip["name"].lower() in sent_text and policy["name"].lower() in sent_text
                type_cert = True
                same_sent = True
                conf = score_relation(phrase, dep, type_cert, same_sent)
                if conf >= 0.6:
                    candidate_rels.append({
                        "source": get_entity_id(equip, "Equipment"),
                        "target": get_entity_id(policy, "Policy"),
                        "type": "REGULATED_BY",
                        **provenance(conf)
                    })
        # REQUIRES (Equipment → Requirement)
        for equip in by_type.get("Equipment", []):
            for req in by_type.get("Requirement", []):
                phrase = any(p in sent_text for p in ["must", "shall", "is required to", "mandatory"])
                dep = equip["name"].lower() in sent_text and req["description"].lower() in sent_text
                type_cert = True
                same_sent = True
                conf = score_relation(phrase, dep, type_cert, same_sent)
                if conf >= 0.6:
                    candidate_rels.append({
                        "source": get_entity_id(equip, "Equipment"),
                        "target": get_entity_id(req, "Requirement"),
                        "type": "REQUIRES",
                        **provenance(conf)
                    })
        # DEFINED_IN (Requirement → Policy)
        for req in by_type.get("Requirement", []):
            for policy in by_type.get("Policy", []):
                # If both appear in same sentence or paragraph
                dep = req["description"].lower() in sent_text and policy["name"].lower() in sent_text
                type_cert = True
                same_sent = True
                conf = score_relation(False, dep, type_cert, same_sent)
                if conf >= 0.6:
                    candidate_rels.append({
                        "source": get_entity_id(req, "Requirement"),
                        "target": get_entity_id(policy, "Policy"),
                        "type": "DEFINED_IN",
                        **provenance(conf)
                    })
        # ENFORCED_BY (Requirement → Authority)
        for req in by_type.get("Requirement", []):
            for authority in by_type.get("Authority", []):
                phrase = any(p in sent_text for p in ["enforced by", "overseen by", "administered by"])
                dep = req["description"].lower() in sent_text and authority["name"].lower() in sent_text
                type_cert = True
                same_sent = True
                conf = score_relation(phrase, dep, type_cert, same_sent)
                if conf >= 0.6:
                    candidate_rels.append({
                        "source": get_entity_id(req, "Requirement"),
                        "target": get_entity_id(authority, "Authority"),
                        "type": "ENFORCED_BY",
                        **provenance(conf)
                    })
        # BELONGS_TO_DOMAIN (Policy → TechDomain)
        for policy in by_type.get("Policy", []):
            for domain in by_type.get("TechDomain", []):
                phrase = any(kw in sent_text for kw in ["artificial intelligence", "medical device", "cybersecurity", "ai", "software", "imaging"])
                dep = policy["name"].lower() in sent_text and domain["name"].lower() in sent_text
                type_cert = True
                same_sent = True
                conf = score_relation(phrase, dep, type_cert, same_sent)
                if conf >= 0.7:  # domain: medium confidence
                    candidate_rels.append({
                        "source": get_entity_id(policy, "Policy"),
                        "target": get_entity_id(domain, "TechDomain"),
                        "type": "BELONGS_TO_DOMAIN",
                        **provenance(conf)
                    })
        # SOURCED_FROM (Requirement → Document) - always attach
        for req in by_type.get("Requirement", []):
            for docu in by_type.get("Document", []):
                candidate_rels.append({
                    "source": get_entity_id(req, "Requirement"),
                    "target": get_entity_id(docu, "Document"),
                    "type": "SOURCED_FROM",
                    **provenance(1.0)
                })

    # --- Conflict resolution and filtering ---
    # Priority: REQUIRES > REGULATED_BY > ISSUED_BY > APPLIES_IN > BELONGS_TO_DOMAIN
    priority = ["REQUIRES", "REGULATED_BY", "ISSUED_BY", "APPLIES_IN", "BELONGS_TO_DOMAIN"]
    seen_pairs = set()
    final_rels = []
    for reltype in priority + ["DEFINED_IN", "ENFORCED_BY", "SOURCED_FROM"]:
        for rel in [r for r in candidate_rels if r["type"] == reltype]:
            pair = (rel["source"], rel["target"], rel["type"])
            if pair in seen_pairs:
                continue
            # Type validation: must match schema
            if not rel["source"] or not rel["target"]:
                continue
            if rel["confidence"] < 0.6:
                continue
            final_rels.append(rel)
            seen_pairs.add(pair)
    return final_rels
import spacy

# Load spaCy model globally for efficiency
_SPACY_NLP = spacy.load("en_core_web_sm")

def spacy_extract_entities(text: str) -> list:
    """
    Extract entities from text using spaCy NER and map to schema node types and attributes.
    Returns a list of dicts: {"type": ..., ...attributes...}
    """
    import hashlib
    doc = _SPACY_NLP(text)
    results = []
    seen = set()

    def make_id(prefix, value):
        # Deterministic hash for unique IDs
        return f"{prefix}_" + hashlib.md5(value.strip().lower().encode()).hexdigest()[:8]

    # ISO 3166-1 alpha-2 country code lookup
    ISO_COUNTRY_CODES = {
        "india": "IN", "usa": "US", "united states": "US", "china": "CN", 
        "japan": "JP", "germany": "DE", "france": "FR", "uk": "GB", 
        "united kingdom": "GB", "canada": "CA", "australia": "AU", 
        "brazil": "BR", "russia": "RU", "south korea": "KR", "italy": "IT", 
        "spain": "ES", "mexico": "MX", "indonesia": "ID", "netherlands": "NL",
        "saudi arabia": "SA", "turkey": "TR", "switzerland": "CH", 
        "poland": "PL", "sweden": "SE", "belgium": "BE", "thailand": "TH", 
        "austria": "AT", "norway": "NO", "israel": "IL", "ireland": "IE", 
        "singapore": "SG", "malaysia": "MY", "philippines": "PH", 
        "pakistan": "PK", "bangladesh": "BD", "vietnam": "VN", "egypt": "EG",
        "south africa": "ZA", "nigeria": "NG", "kenya": "KE", "uae": "AE",
        "european union": "EU", "eu": "EU"
    }

    # Known country names for validation
    KNOWN_COUNTRIES = set(ISO_COUNTRY_CODES.keys())
    
    # Filter out common false positives (cities, abbreviations, names)
    FALSE_POSITIVE_GPES = {
        "new delhi", "delhi", "london", "boston", "new york", "new jersey",
        "florida", "washington", "washington d.c.", "oxford", "cambridge",
        "b.p.", "j.e.", "c.l.", "r.k.", "m.e.", "houghton", "baghel", "kumar",
        "yogendra", "birkland", "hogwood", "sapru", "commonwealth secretariat"
    }

    # Country extraction (GPE, LOC) - with validation and ISO code
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC"]:
            ent_lower = ent.text.strip().lower()
            # Skip false positives
            if ent_lower in FALSE_POSITIVE_GPES:
                continue
            # Only include if it's a known country OR has "country" context
            if ent_lower not in KNOWN_COUNTRIES and len(ent.text) < 4:
                continue  # Skip short abbreviations
            country_id = make_id("country", ent.text)
            key = ("Country", country_id)
            if key not in seen:
                seen.add(key)
                iso_code = ISO_COUNTRY_CODES.get(ent_lower, None)
                results.append({
                    "type": "Country",
                    "country_id": country_id,
                    "name": ent.text,
                    "iso_code": iso_code,
                })

    # Authority (ORG, with keywords)
    for ent in doc.ents:
        if ent.label_ == "ORG" and any(k in ent.text.lower() for k in ["authority", "agency", "ministry", "cdsco", "board", "commission", "council"]):
            authority_id = make_id("authority", ent.text)
            key = ("Authority", authority_id)
            if key not in seen:
                seen.add(key)
                # Infer authority level based on keywords
                level = "national"
                if any(k in ent.text.lower() for k in ["state", "provincial", "regional"]):
                    level = "state"
                elif any(k in ent.text.lower() for k in ["local", "municipal", "city"]):
                    level = "local"
                elif any(k in ent.text.lower() for k in ["international", "global", "world"]):
                    level = "international"
                results.append({
                    "type": "Authority",
                    "authority_id": authority_id,
                    "name": ent.text,
                    "level": level,
                })

    # Legal document patterns for improved Policy detection
    POLICY_PATTERNS = [
        "policy", "act", "regulation", "rule", "law", "statute", "ordinance",
        "directive", "decree", "order", "code", "standard", "guideline",
        "framework", "protocol", "convention", "treaty", "agreement",
        "amendment", "bill", "charter", "constitution", "resolution"
    ]
    
    # Policy type inference
    def infer_policy_type(name: str) -> str:
        name_lower = name.lower()
        if any(k in name_lower for k in ["act", "statute", "law", "bill"]):
            return "legislation"
        elif any(k in name_lower for k in ["regulation", "rule", "order"]):
            return "regulation"
        elif any(k in name_lower for k in ["guideline", "standard", "protocol"]):
            return "guideline"
        elif any(k in name_lower for k in ["policy", "framework"]):
            return "policy"
        elif any(k in name_lower for k in ["treaty", "convention", "agreement"]):
            return "international_agreement"
        return "other"

    # Policy (LAW, or ORG/WORK_OF_ART with legal patterns)
    for ent in doc.ents:
        if ent.label_ == "LAW" or (ent.label_ in ["ORG", "WORK_OF_ART"] and any(k in ent.text.lower() for k in POLICY_PATTERNS)):
            policy_id = make_id("policy", ent.text)
            key = ("Policy", policy_id)
            if key not in seen:
                seen.add(key)
                results.append({
                    "type": "Policy",
                    "policy_id": policy_id,
                    "name": ent.text,
                    "policy_type": infer_policy_type(ent.text),
                })

    # Equipment (PRODUCT, or ORG with device keywords)
    for ent in doc.ents:
        if ent.label_ == "PRODUCT" or (ent.label_ == "ORG" and any(k in ent.text.lower() for k in ["device", "equipment", "system", "machine", "scanner", "imaging"])):
            equipment_id = make_id("equipment", ent.text)
            key = ("Equipment", equipment_id)
            if key not in seen:
                seen.add(key)
                results.append({
                    "type": "Equipment",
                    "equipment_id": equipment_id,
                    "name": ent.text,
                    # "risk_level": infer_risk(ent.text, text),
                    # "ai_enabled": infer_ai_enabled(ent.text, text),
                })

    # TechDomain (custom: look for keywords in text)
    tech_keywords = ["ai", "artificial intelligence", "medical device", "health it", "imaging", "software"]
    for kw in tech_keywords:
        if kw in text.lower():
            domain_id = make_id("domain", kw)
            key = ("TechDomain", domain_id)
            if key not in seen:
                seen.add(key)
                results.append({
                    "type": "TechDomain",
                    "domain_id": domain_id,
                    "name": kw.title(),
                })

    # Requirement (look for keywords in text)
    req_keywords = ["registration", "approval", "reporting", "requirement", "mandatory", "submission"]
    for kw in req_keywords:
        if kw in text.lower():
            requirement_id = make_id("requirement", kw)
            key = ("Requirement", requirement_id)
            if key not in seen:
                seen.add(key)
                results.append({
                    "type": "Requirement",
                    "requirement_id": requirement_id,
                    "description": kw.title(),
                })

    # Document (look for keywords in text)
    doc_keywords = ["pdf", "form", "document", "submission"]
    for kw in doc_keywords:
        if kw in text.lower():
            document_id = make_id("document", kw)
            key = ("Document", document_id)
            if key not in seen:
                seen.add(key)
                results.append({
                    "type": "Document",
                    "document_id": document_id,
                    "title": kw.title(),
                })

    return results



