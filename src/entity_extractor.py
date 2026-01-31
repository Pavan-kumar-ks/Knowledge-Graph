"""
Entity extraction module using spaCy NLP with EntityRuler and DependencyMatcher.

Features:
- EntityRuler: Pattern-based entity recognition for domain-specific entities
- DependencyMatcher: Syntactic dependency patterns for relationship extraction
- Normalization: Canonical forms to prevent duplicates (AI = Artificial Intelligence)
"""

import datetime
import hashlib
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import spacy
from spacy.language import Language
from spacy.matcher import DependencyMatcher
from spacy.tokens import Doc, Span

logger = logging.getLogger(__name__)


# =============================================================================
# EntityRuler Patterns - Domain-Specific Entity Recognition
# =============================================================================

# Equipment patterns for EntityRuler
EQUIPMENT_PATTERNS = [
    # Medical Imaging
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "mri"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "mri"}, {"LOWER": "scanner"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "magnetic"}, {"LOWER": "resonance"}, {"LOWER": "imaging"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "ct"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "ct"}, {"LOWER": "scanner"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "computed"}, {"LOWER": "tomography"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "x-ray"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "xray"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "x"}, {"LOWER": "-"}, {"LOWER": "ray"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "ultrasound"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "ultrasound"}, {"LOWER": "machine"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "sonography"}]},
    # Life Support
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "ventilator"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "mechanical"}, {"LOWER": "ventilator"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "respirator"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "defibrillator"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "aed"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "pacemaker"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "cardiac"}, {"LOWER": "pacemaker"}]},
    # Other Medical Devices
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "infusion"}, {"LOWER": "pump"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "iv"}, {"LOWER": "pump"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "dialysis"}, {"LOWER": "machine"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "hemodialysis"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "patient"}, {"LOWER": "monitor"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "vital"}, {"LOWER": "signs"}, {"LOWER": "monitor"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "ecg"}, {"LOWER": "monitor"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "medical"}, {"LOWER": "device"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "medical"}, {"LOWER": "devices"}]},
    {"label": "EQUIPMENT", "pattern": [{"LOWER": "medical"}, {"LOWER": "equipment"}]},
]

# Tech Domain patterns for EntityRuler (normalized to canonical forms)
TECH_DOMAIN_PATTERNS = [
    # AI / Machine Learning (all map to "Artificial Intelligence")
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "ai"}], "id": "artificial_intelligence"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "a.i."}], "id": "artificial_intelligence"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "artificial"}, {"LOWER": "intelligence"}], "id": "artificial_intelligence"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "machine"}, {"LOWER": "learning"}], "id": "artificial_intelligence"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "ml"}], "id": "artificial_intelligence"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "deep"}, {"LOWER": "learning"}], "id": "artificial_intelligence"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "neural"}, {"LOWER": "network"}], "id": "artificial_intelligence"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "neural"}, {"LOWER": "networks"}], "id": "artificial_intelligence"},
    # Medical Imaging
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "medical"}, {"LOWER": "imaging"}], "id": "medical_imaging"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "diagnostic"}, {"LOWER": "imaging"}], "id": "medical_imaging"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "radiology"}], "id": "medical_imaging"},
    # Health IT
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "health"}, {"LOWER": "it"}], "id": "health_it"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "healthcare"}, {"LOWER": "it"}], "id": "health_it"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "hit"}], "id": "health_it"},
    # Software
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "samd"}], "id": "software"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "software"}, {"LOWER": "as"}, {"LOWER": "a"}, {"LOWER": "medical"}, {"LOWER": "device"}], "id": "software"},
    # IoT
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "iot"}], "id": "iot"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "internet"}, {"LOWER": "of"}, {"LOWER": "things"}], "id": "iot"},
    # Robotics
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "robotics"}], "id": "robotics"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "surgical"}, {"LOWER": "robot"}], "id": "robotics"},
    # Diagnostics
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "ivd"}], "id": "diagnostics"},
    {"label": "TECH_DOMAIN", "pattern": [{"LOWER": "in-vitro"}, {"LOWER": "diagnostics"}], "id": "diagnostics"},
]

# Authority patterns
AUTHORITY_PATTERNS = [
    # US
    {"label": "AUTHORITY", "pattern": [{"LOWER": "fda"}]},
    {"label": "AUTHORITY", "pattern": [{"LOWER": "food"}, {"LOWER": "and"}, {"LOWER": "drug"}, {"LOWER": "administration"}]},
    # EU
    {"label": "AUTHORITY", "pattern": [{"LOWER": "ema"}]},
    {"label": "AUTHORITY", "pattern": [{"LOWER": "european"}, {"LOWER": "medicines"}, {"LOWER": "agency"}]},
    # UK
    {"label": "AUTHORITY", "pattern": [{"LOWER": "mhra"}]},
    {"label": "AUTHORITY", "pattern": [{"LOWER": "medicines"}, {"LOWER": "and"}, {"LOWER": "healthcare"}, {"LOWER": "products"}, {"LOWER": "regulatory"}, {"LOWER": "agency"}]},
    # India
    {"label": "AUTHORITY", "pattern": [{"LOWER": "cdsco"}]},
    {"label": "AUTHORITY", "pattern": [{"LOWER": "central"}, {"LOWER": "drugs"}, {"LOWER": "standard"}, {"LOWER": "control"}, {"LOWER": "organization"}]},
    # Australia
    {"label": "AUTHORITY", "pattern": [{"LOWER": "tga"}]},
    {"label": "AUTHORITY", "pattern": [{"LOWER": "therapeutic"}, {"LOWER": "goods"}, {"LOWER": "administration"}]},
    # Japan
    {"label": "AUTHORITY", "pattern": [{"LOWER": "pmda"}]},
    {"label": "AUTHORITY", "pattern": [{"LOWER": "pharmaceuticals"}, {"LOWER": "and"}, {"LOWER": "medical"}, {"LOWER": "devices"}, {"LOWER": "agency"}]},
    # China
    {"label": "AUTHORITY", "pattern": [{"LOWER": "nmpa"}]},
    {"label": "AUTHORITY", "pattern": [{"LOWER": "national"}, {"LOWER": "medical"}, {"LOWER": "products"}, {"LOWER": "administration"}]},
    # Brazil
    {"label": "AUTHORITY", "pattern": [{"LOWER": "anvisa"}]},
    # Generic authority patterns
    {"label": "AUTHORITY", "pattern": [{"LOWER": "ministry"}, {"LOWER": "of"}, {"LOWER": "health"}]},
    {"label": "AUTHORITY", "pattern": [{"LOWER": "health"}, {"LOWER": "ministry"}]},
    {"label": "AUTHORITY", "pattern": [{"LOWER": "regulatory"}, {"LOWER": "authority"}]},
    {"label": "AUTHORITY", "pattern": [{"LOWER": "regulatory"}, {"LOWER": "agency"}]},
]

# Policy patterns
POLICY_PATTERNS = [
    # Document-level policies (governance documents)
    {"label": "POLICY", "pattern": [{"LOWER": "national"}, {"LOWER": "security"}, {"LOWER": "strategy"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "strategic"}, {"LOWER": "concept"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "tariff"}, {"LOWER": "policy"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "electricity"}, {"LOWER": "act"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "public"}, {"LOWER": "policy"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "strategy"}, {"LOWER": "for"}, {"LOWER": "new"}, {"LOWER": "india"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "north"}, {"LOWER": "atlantic"}, {"LOWER": "treaty"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "nato"}, {"LOWER": "treaty"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "nato"}, {"LOWER": "strategic"}, {"LOWER": "concept"}]},
    # Medical device regulations
    {"label": "POLICY", "pattern": [{"LOWER": "medical"}, {"LOWER": "device"}, {"LOWER": "regulation"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "mdr"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "eu"}, {"LOWER": "mdr"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "ivdr"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "fda"}, {"LOWER": "approval"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "ce"}, {"LOWER": "marking"}]},
    {"label": "POLICY", "pattern": [{"LOWER": "iso"}, {"IS_DIGIT": True}]},
    {"label": "POLICY", "pattern": [{"LOWER": "iec"}, {"IS_DIGIT": True}]},
]

# Requirement patterns
REQUIREMENT_PATTERNS = [
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "registration"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "device"}, {"LOWER": "registration"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "market"}, {"LOWER": "authorization"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "premarket"}, {"LOWER": "approval"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "510k"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "510"}, {"TEXT": "("}, {"LOWER": "k"}, {"TEXT": ")"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "pma"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "clinical"}, {"LOWER": "trial"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "clinical"}, {"LOWER": "trials"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "clinical"}, {"LOWER": "evaluation"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "risk"}, {"LOWER": "assessment"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "post-market"}, {"LOWER": "surveillance"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "quality"}, {"LOWER": "management"}, {"LOWER": "system"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "qms"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "technical"}, {"LOWER": "documentation"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "technical"}, {"LOWER": "file"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "labeling"}]},
    {"label": "REQUIREMENT", "pattern": [{"LOWER": "labelling"}]},
]

# Country patterns (with ISO codes in id)
COUNTRY_PATTERNS = [
    {"label": "COUNTRY", "pattern": [{"LOWER": "india"}], "id": "IN"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "indian"}], "id": "IN"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "usa"}], "id": "US"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "united"}, {"LOWER": "states"}], "id": "US"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "america"}], "id": "US"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "american"}], "id": "US"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "uk"}], "id": "GB"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "united"}, {"LOWER": "kingdom"}], "id": "GB"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "britain"}], "id": "GB"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "british"}], "id": "GB"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "germany"}], "id": "DE"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "german"}], "id": "DE"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "france"}], "id": "FR"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "french"}], "id": "FR"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "japan"}], "id": "JP"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "japanese"}], "id": "JP"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "china"}], "id": "CN"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "chinese"}], "id": "CN"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "australia"}], "id": "AU"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "australian"}], "id": "AU"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "canada"}], "id": "CA"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "canadian"}], "id": "CA"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "brazil"}], "id": "BR"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "brazilian"}], "id": "BR"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "singapore"}], "id": "SG"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "south"}, {"LOWER": "korea"}], "id": "KR"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "korea"}], "id": "KR"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "european"}, {"LOWER": "union"}], "id": "EU"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "eu"}], "id": "EU"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "italy"}], "id": "IT"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "spain"}], "id": "ES"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "netherlands"}], "id": "NL"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "switzerland"}], "id": "CH"},
    {"label": "COUNTRY", "pattern": [{"LOWER": "russia"}], "id": "RU"},
]


# =============================================================================
# DependencyMatcher Patterns - Relationship Extraction
# =============================================================================

# Pattern: EQUIPMENT regulated by POLICY
# e.g., "MRI scanners are regulated by the Medical Device Regulation"
REGULATED_BY_PATTERN = [
    {
        "RIGHT_ID": "verb",
        "RIGHT_ATTRS": {"LEMMA": {"IN": ["regulate", "govern", "cover", "control"]}}
    },
    {
        "LEFT_ID": "verb",
        "REL_OP": ">",
        "RIGHT_ID": "equipment",
        "RIGHT_ATTRS": {"DEP": {"IN": ["nsubjpass", "nsubj", "dobj"]}}
    },
    {
        "LEFT_ID": "verb",
        "REL_OP": ">",
        "RIGHT_ID": "policy",
        "RIGHT_ATTRS": {"DEP": {"IN": ["agent", "pobj", "obl"]}}
    }
]

# Pattern: POLICY applies in COUNTRY
# e.g., "The regulation applies in India"
APPLIES_IN_PATTERN = [
    {
        "RIGHT_ID": "verb",
        "RIGHT_ATTRS": {"LEMMA": {"IN": ["apply", "enforce", "implement", "operate"]}}
    },
    {
        "LEFT_ID": "verb",
        "REL_OP": ">",
        "RIGHT_ID": "subject",
        "RIGHT_ATTRS": {"DEP": {"IN": ["nsubj", "nsubjpass"]}}
    },
    {
        "LEFT_ID": "verb",
        "REL_OP": ">>",
        "RIGHT_ID": "country",
        "RIGHT_ATTRS": {"DEP": {"IN": ["pobj", "obl", "prep"]}}
    }
]

# Pattern: POLICY issued by AUTHORITY
# e.g., "The regulation was issued by FDA"
ISSUED_BY_PATTERN = [
    {
        "RIGHT_ID": "verb",
        "RIGHT_ATTRS": {"LEMMA": {"IN": ["issue", "publish", "enact", "introduce", "release"]}}
    },
    {
        "LEFT_ID": "verb",
        "REL_OP": ">",
        "RIGHT_ID": "policy",
        "RIGHT_ATTRS": {"DEP": {"IN": ["nsubj", "nsubjpass", "dobj"]}}
    },
    {
        "LEFT_ID": "verb",
        "REL_OP": ">",
        "RIGHT_ID": "authority",
        "RIGHT_ATTRS": {"DEP": {"IN": ["agent", "pobj", "obl"]}}
    }
]

# Pattern: POLICY requires REQUIREMENT
# e.g., "The regulation requires clinical trials"
REQUIRES_PATTERN = [
    {
        "RIGHT_ID": "verb",
        "RIGHT_ATTRS": {"LEMMA": {"IN": ["require", "mandate", "need", "demand", "necessitate"]}}
    },
    {
        "LEFT_ID": "verb",
        "REL_OP": ">",
        "RIGHT_ID": "subject",
        "RIGHT_ATTRS": {"DEP": {"IN": ["nsubj"]}}
    },
    {
        "LEFT_ID": "verb",
        "REL_OP": ">",
        "RIGHT_ID": "requirement",
        "RIGHT_ATTRS": {"DEP": {"IN": ["dobj", "obj"]}}
    }
]

# Pattern: AUTHORITY enforces POLICY
# e.g., "FDA enforces the regulation"
ENFORCES_PATTERN = [
    {
        "RIGHT_ID": "verb",
        "RIGHT_ATTRS": {"LEMMA": {"IN": ["enforce", "administer", "oversee", "regulate"]}}
    },
    {
        "LEFT_ID": "verb",
        "REL_OP": ">",
        "RIGHT_ID": "authority",
        "RIGHT_ATTRS": {"DEP": {"IN": ["nsubj"]}}
    },
    {
        "LEFT_ID": "verb",
        "REL_OP": ">",
        "RIGHT_ID": "policy",
        "RIGHT_ATTRS": {"DEP": {"IN": ["dobj", "obj"]}}
    }
]


# =============================================================================
# Enhanced spaCy NLP Pipeline with EntityRuler
# =============================================================================

def create_enhanced_nlp():
    """Create enhanced spaCy pipeline with EntityRuler for domain entities."""
    # Load base model
    nlp = spacy.load("en_core_web_sm")
    
    # Create EntityRuler and add patterns
    # Add before NER to let our patterns take precedence
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    
    # Combine all patterns
    all_patterns = (
        EQUIPMENT_PATTERNS + 
        TECH_DOMAIN_PATTERNS + 
        AUTHORITY_PATTERNS + 
        POLICY_PATTERNS + 
        REQUIREMENT_PATTERNS +
        COUNTRY_PATTERNS
    )
    
    ruler.add_patterns(all_patterns)
    
    logger.info(f"EntityRuler initialized with {len(all_patterns)} patterns")
    
    return nlp


# Global enhanced NLP instance
_ENHANCED_NLP = None

def get_enhanced_nlp():
    """Get or create the enhanced NLP pipeline."""
    global _ENHANCED_NLP
    if _ENHANCED_NLP is None:
        _ENHANCED_NLP = create_enhanced_nlp()
    return _ENHANCED_NLP


# =============================================================================
# Entity Normalization
# =============================================================================

class EntityNormalizer:
    """Normalize entities to canonical forms."""
    
    # Canonical names for tech domains
    TECH_DOMAIN_CANONICAL = {
        "artificial_intelligence": "Artificial Intelligence",
        "medical_imaging": "Medical Imaging",
        "health_it": "Health IT",
        "software": "Software as Medical Device",
        "iot": "Internet of Things",
        "robotics": "Robotics",
        "diagnostics": "In-Vitro Diagnostics",
    }
    
    # Equipment normalization
    EQUIPMENT_CANONICAL = {
        "mri": "MRI Scanner",
        "ct": "CT Scanner",
        "x-ray": "X-Ray Machine",
        "xray": "X-Ray Machine",
        "ultrasound": "Ultrasound",
        "ventilator": "Ventilator",
        "defibrillator": "Defibrillator",
        "aed": "Defibrillator",
        "pacemaker": "Pacemaker",
        "dialysis": "Dialysis Machine",
        "infusion pump": "Infusion Pump",
        "patient monitor": "Patient Monitor",
    }
    
    # Country ISO codes
    COUNTRY_ISO = {
        "IN": "India", "US": "United States", "GB": "United Kingdom",
        "DE": "Germany", "FR": "France", "JP": "Japan", "CN": "China",
        "AU": "Australia", "CA": "Canada", "BR": "Brazil", "SG": "Singapore",
        "KR": "South Korea", "EU": "European Union", "IT": "Italy",
        "ES": "Spain", "NL": "Netherlands", "CH": "Switzerland", "RU": "Russia",
    }
    
    @classmethod
    def normalize_tech_domain(cls, ent_id: str, text: str) -> Tuple[str, str]:
        """Get canonical name and ID for tech domain."""
        canonical = cls.TECH_DOMAIN_CANONICAL.get(ent_id, text.title())
        domain_id = "domain_" + hashlib.md5(ent_id.encode() if ent_id else text.lower().encode()).hexdigest()[:8]
        return canonical, domain_id
    
    @classmethod
    def normalize_equipment(cls, text: str) -> Tuple[str, str]:
        """Get canonical name and ID for equipment."""
        text_lower = text.lower().strip()
        for key, canonical in cls.EQUIPMENT_CANONICAL.items():
            if key in text_lower:
                equip_id = "equipment_" + hashlib.md5(canonical.lower().encode()).hexdigest()[:8]
                return canonical, equip_id
        equip_id = "equipment_" + hashlib.md5(text_lower.encode()).hexdigest()[:8]
        return text.title(), equip_id
    
    @classmethod
    def normalize_country(cls, ent_id: str, text: str) -> Tuple[str, str, Optional[str]]:
        """Get canonical name, ID, and ISO code for country."""
        iso_code = ent_id if ent_id and len(ent_id) == 2 else None
        if iso_code and iso_code in cls.COUNTRY_ISO:
            canonical = cls.COUNTRY_ISO[iso_code]
        else:
            canonical = text.title()
        country_id = "country_" + hashlib.md5((iso_code or text.lower()).encode()).hexdigest()[:8]
        return canonical, country_id, iso_code


# =============================================================================
# Main Entity Extraction
# =============================================================================

def make_id(prefix: str, value: str) -> str:
    """Create deterministic hash ID for entities."""
    return f"{prefix}_" + hashlib.md5(value.strip().lower().encode()).hexdigest()[:8]


def extract_entities_with_ruler(text: str) -> List[Dict[str, Any]]:
    """
    Extract entities using EntityRuler-enhanced spaCy pipeline.
    """
    nlp = get_enhanced_nlp()
    doc = nlp(text)
    
    results = []
    seen: Set[Tuple[str, str]] = set()
    
    for ent in doc.ents:
        entity_data = None
        
        if ent.label_ == "EQUIPMENT":
            canonical, equip_id = EntityNormalizer.normalize_equipment(ent.text)
            key = ("Equipment", equip_id)
            if key not in seen:
                seen.add(key)
                entity_data = {
                    "type": "Equipment",
                    "equipment_id": equip_id,
                    "name": canonical,
                    "span_start": ent.start_char,
                    "span_end": ent.end_char,
                }
        
        elif ent.label_ == "TECH_DOMAIN":
            canonical, domain_id = EntityNormalizer.normalize_tech_domain(ent.ent_id_, ent.text)
            key = ("TechDomain", domain_id)
            if key not in seen:
                seen.add(key)
                entity_data = {
                    "type": "TechDomain",
                    "domain_id": domain_id,
                    "name": canonical,
                    "span_start": ent.start_char,
                    "span_end": ent.end_char,
                }
        
        elif ent.label_ == "AUTHORITY":
            auth_id = make_id("authority", ent.text)
            key = ("Authority", auth_id)
            if key not in seen:
                seen.add(key)
                # Infer level
                level = "national"
                text_lower = ent.text.lower()
                if any(k in text_lower for k in ["state", "provincial", "regional"]):
                    level = "state"
                elif any(k in text_lower for k in ["local", "municipal"]):
                    level = "local"
                elif any(k in text_lower for k in ["international", "global", "world"]):
                    level = "international"
                entity_data = {
                    "type": "Authority",
                    "authority_id": auth_id,
                    "name": ent.text,
                    "level": level,
                    "span_start": ent.start_char,
                    "span_end": ent.end_char,
                }
        
        elif ent.label_ == "POLICY" or ent.label_ == "LAW":
            policy_id = make_id("policy", ent.text)
            key = ("Policy", policy_id)
            if key not in seen:
                seen.add(key)
                # Infer policy type
                text_lower = ent.text.lower()
                if any(k in text_lower for k in ["act", "statute", "law", "bill"]):
                    policy_type = "legislation"
                elif any(k in text_lower for k in ["regulation", "rule", "order", "mdr", "ivdr"]):
                    policy_type = "regulation"
                elif any(k in text_lower for k in ["guideline", "standard", "protocol", "iso", "iec"]):
                    policy_type = "guideline"
                elif any(k in text_lower for k in ["treaty", "convention", "agreement"]):
                    policy_type = "international_agreement"
                else:
                    policy_type = "policy"
                entity_data = {
                    "type": "Policy",
                    "policy_id": policy_id,
                    "name": ent.text,
                    "policy_type": policy_type,
                    "span_start": ent.start_char,
                    "span_end": ent.end_char,
                }
        
        elif ent.label_ == "REQUIREMENT":
            req_id = make_id("requirement", ent.text)
            key = ("Requirement", req_id)
            if key not in seen:
                seen.add(key)
                entity_data = {
                    "type": "Requirement",
                    "requirement_id": req_id,
                    "description": ent.text.title(),
                    "span_start": ent.start_char,
                    "span_end": ent.end_char,
                }
        
        elif ent.label_ == "COUNTRY":
            canonical, country_id, iso_code = EntityNormalizer.normalize_country(ent.ent_id_, ent.text)
            key = ("Country", country_id)
            if key not in seen:
                seen.add(key)
                entity_data = {
                    "type": "Country",
                    "country_id": country_id,
                    "name": canonical,
                    "iso_code": iso_code,
                    "span_start": ent.start_char,
                    "span_end": ent.end_char,
                }
        
        # Also handle fallback to spaCy's built-in NER for ORG/GPE
        elif ent.label_ == "ORG":
            # Check if it might be an authority
            text_lower = ent.text.lower()
            authority_kw = ["authority", "agency", "ministry", "board", "commission", 
                          "council", "department", "bureau", "office", "administration"]
            if any(k in text_lower for k in authority_kw):
                auth_id = make_id("authority", ent.text)
                key = ("Authority", auth_id)
                if key not in seen:
                    seen.add(key)
                    entity_data = {
                        "type": "Authority",
                        "authority_id": auth_id,
                        "name": ent.text,
                        "level": "national",
                        "span_start": ent.start_char,
                        "span_end": ent.end_char,
                    }
        
        elif ent.label_ == "GPE":
            # Validate it's a real country
            text_lower = ent.text.lower()
            # Check against our country list
            for pattern in COUNTRY_PATTERNS:
                pattern_text = " ".join([p.get("LOWER", "") for p in pattern.get("pattern", [])])
                if text_lower == pattern_text or text_lower in pattern_text:
                    iso_code = pattern.get("id", "")
                    canonical, country_id, _ = EntityNormalizer.normalize_country(iso_code, ent.text)
                    key = ("Country", country_id)
                    if key not in seen:
                        seen.add(key)
                        entity_data = {
                            "type": "Country",
                            "country_id": country_id,
                            "name": canonical,
                            "iso_code": iso_code,
                            "span_start": ent.start_char,
                            "span_end": ent.end_char,
                        }
                    break
        
        if entity_data:
            results.append(entity_data)
    
    return results


# =============================================================================
# Relationship Extraction with DependencyMatcher
# =============================================================================

def extract_relationships_with_matcher(
    text: str, 
    entities: List[Dict], 
    document: Optional[str] = None, 
    section: Optional[str] = None
) -> List[Dict]:
    """
    Extract relationships using DependencyMatcher patterns.
    """
    nlp = get_enhanced_nlp()
    doc = nlp(text)
    
    # Create DependencyMatcher
    matcher = DependencyMatcher(nlp.vocab)
    
    # Add patterns
    try:
        matcher.add("REGULATED_BY", [REGULATED_BY_PATTERN])
        matcher.add("APPLIES_IN", [APPLIES_IN_PATTERN])
        matcher.add("ISSUED_BY", [ISSUED_BY_PATTERN])
        matcher.add("REQUIRES", [REQUIRES_PATTERN])
        matcher.add("ENFORCES", [ENFORCES_PATTERN])
    except Exception as e:
        logger.debug(f"DependencyMatcher pattern error (non-fatal): {e}")
    
    # Group entities by type for lookup
    by_type: Dict[str, List[Dict]] = {}
    for ent in entities:
        by_type.setdefault(ent["type"], []).append(ent)
    
    # Helper to find entity by span
    def find_entity_at_span(start: int, end: int, entity_type: Optional[str] = None):
        for ent in entities:
            if entity_type and ent["type"] != entity_type:
                continue
            ent_start = ent.get("span_start", -1)
            ent_end = ent.get("span_end", -1)
            # Check overlap
            if ent_start <= start <= ent_end or ent_start <= end <= ent_end:
                return ent
            # Also check by name
            if ent.get("name", "").lower() in text[start:end].lower():
                return ent
        return None
    
    today = datetime.date.today().isoformat()
    
    def provenance(confidence: float) -> Dict[str, Any]:
        return {
            "confidence": round(confidence, 2),
            "extracted_from": document,
            "section": section,
            "extracted_on": today,
            "method": "DependencyMatcher"
        }
    
    def get_entity_id(ent: Dict, t: str) -> str:
        id_map = {
            "Policy": "policy_id", "Country": "country_id", "Authority": "authority_id",
            "TechDomain": "domain_id", "Equipment": "equipment_id", 
            "Requirement": "requirement_id", "Document": "document_id"
        }
        return ent.get(id_map.get(t, ""), "")
    
    relationships: List[Dict] = []
    seen_pairs: Set[Tuple[str, str, str]] = set()
    
    # Run DependencyMatcher
    try:
        matches = matcher(doc)
        
        for match_id, token_ids in matches:
            pattern_name = nlp.vocab.strings[match_id]
            matched_tokens = [doc[token_id] for token_id in token_ids]
            
            # Extract relationship based on pattern
            if pattern_name == "REGULATED_BY":
                # Find equipment and policy from matched tokens
                for token in matched_tokens:
                    equip = find_entity_at_span(token.idx, token.idx + len(token.text), "Equipment")
                    policy = find_entity_at_span(token.idx, token.idx + len(token.text), "Policy")
                    if equip and policy:
                        rel = {
                            "source": get_entity_id(equip, "Equipment"),
                            "target": get_entity_id(policy, "Policy"),
                            "type": "REGULATED_BY",
                            **provenance(0.85)
                        }
                        pair = (rel["source"], rel["target"], rel["type"])
                        if pair not in seen_pairs and rel["source"] and rel["target"]:
                            seen_pairs.add(pair)
                            relationships.append(rel)
            
            elif pattern_name == "APPLIES_IN":
                for token in matched_tokens:
                    policy = find_entity_at_span(token.idx, token.idx + len(token.text), "Policy")
                    country = find_entity_at_span(token.idx, token.idx + len(token.text), "Country")
                    if policy and country:
                        rel = {
                            "source": get_entity_id(policy, "Policy"),
                            "target": get_entity_id(country, "Country"),
                            "type": "APPLIES_IN",
                            **provenance(0.85)
                        }
                        pair = (rel["source"], rel["target"], rel["type"])
                        if pair not in seen_pairs and rel["source"] and rel["target"]:
                            seen_pairs.add(pair)
                            relationships.append(rel)
            
            elif pattern_name == "ISSUED_BY":
                for token in matched_tokens:
                    policy = find_entity_at_span(token.idx, token.idx + len(token.text), "Policy")
                    authority = find_entity_at_span(token.idx, token.idx + len(token.text), "Authority")
                    if policy and authority:
                        rel = {
                            "source": get_entity_id(policy, "Policy"),
                            "target": get_entity_id(authority, "Authority"),
                            "type": "ISSUED_BY",
                            **provenance(0.85)
                        }
                        pair = (rel["source"], rel["target"], rel["type"])
                        if pair not in seen_pairs and rel["source"] and rel["target"]:
                            seen_pairs.add(pair)
                            relationships.append(rel)
            
            elif pattern_name == "REQUIRES":
                for token in matched_tokens:
                    policy = find_entity_at_span(token.idx, token.idx + len(token.text), "Policy")
                    req = find_entity_at_span(token.idx, token.idx + len(token.text), "Requirement")
                    if policy and req:
                        rel = {
                            "source": get_entity_id(policy, "Policy"),
                            "target": get_entity_id(req, "Requirement"),
                            "type": "REQUIRES",
                            **provenance(0.85)
                        }
                        pair = (rel["source"], rel["target"], rel["type"])
                        if pair not in seen_pairs and rel["source"] and rel["target"]:
                            seen_pairs.add(pair)
                            relationships.append(rel)
            
            elif pattern_name == "ENFORCES":
                for token in matched_tokens:
                    authority = find_entity_at_span(token.idx, token.idx + len(token.text), "Authority")
                    policy = find_entity_at_span(token.idx, token.idx + len(token.text), "Policy")
                    if authority and policy:
                        rel = {
                            "source": get_entity_id(authority, "Authority"),
                            "target": get_entity_id(policy, "Policy"),
                            "type": "ENFORCED_BY",
                            **provenance(0.85)
                        }
                        pair = (rel["source"], rel["target"], rel["type"])
                        if pair not in seen_pairs and rel["source"] and rel["target"]:
                            seen_pairs.add(pair)
                            relationships.append(rel)
    except Exception as e:
        logger.debug(f"DependencyMatcher error (falling back to rules): {e}")
    
    # Fallback: Rule-based extraction for co-occurrence in same sentence
    relationships.extend(
        extract_relationships_rule_based(doc, entities, by_type, document, section, seen_pairs)
    )
    
    return relationships


def extract_relationships_rule_based(
    doc, 
    entities: List[Dict], 
    by_type: Dict[str, List[Dict]],
    document: Optional[str],
    section: Optional[str],
    seen_pairs: Set[Tuple[str, str, str]]
) -> List[Dict]:
    """
    Fallback rule-based relationship extraction.
    """
    today = datetime.date.today().isoformat()
    
    def provenance(confidence: float) -> Dict[str, Any]:
        return {
            "confidence": round(confidence, 2),
            "extracted_from": document or "unknown",
            "section": section or "unknown",
            "extracted_on": today,
            "method": "rule_based"
        }
    
    def get_entity_id(ent: Dict, t: str) -> str:
        id_map = {
            "Policy": "policy_id", "Country": "country_id", "Authority": "authority_id",
            "TechDomain": "domain_id", "Equipment": "equipment_id", 
            "Requirement": "requirement_id", "Document": "document_id"
        }
        return ent.get(id_map.get(t, ""), "")
    
    relationships = []
    
    for sent in doc.sents:
        sent_text = sent.text.lower()
        
        # APPLIES_IN (Policy → Country)
        for policy in by_type.get("Policy", []):
            for country in by_type.get("Country", []):
                if (policy.get("name", "").lower() in sent_text and 
                    country.get("name", "").lower() in sent_text):
                    phrase_match = any(p in sent_text for p in ["applies in", "applicable in", "within", "in", "of"])
                    conf = 0.7 if phrase_match else 0.5
                    rel = {
                        "source": get_entity_id(policy, "Policy"),
                        "target": get_entity_id(country, "Country"),
                        "type": "APPLIES_IN",
                        **provenance(conf)
                    }
                    pair = (rel["source"], rel["target"], rel["type"])
                    if pair not in seen_pairs and rel["source"] and rel["target"]:
                        seen_pairs.add(pair)
                        relationships.append(rel)
        
        # ISSUED_BY (Policy → Authority)
        for policy in by_type.get("Policy", []):
            for authority in by_type.get("Authority", []):
                if (policy.get("name", "").lower() in sent_text and 
                    authority.get("name", "").lower() in sent_text):
                    phrase_match = any(p in sent_text for p in ["issued by", "published by", "by the", "enacted by", "adopted by"])
                    conf = 0.7 if phrase_match else 0.5
                    rel = {
                        "source": get_entity_id(policy, "Policy"),
                        "target": get_entity_id(authority, "Authority"),
                        "type": "ISSUED_BY",
                        **provenance(conf)
                    }
                    pair = (rel["source"], rel["target"], rel["type"])
                    if pair not in seen_pairs and rel["source"] and rel["target"]:
                        seen_pairs.add(pair)
                        relationships.append(rel)
        
        # ADMINISTERED_BY (Policy → Authority) - NEW for governance docs
        for policy in by_type.get("Policy", []):
            for authority in by_type.get("Authority", []):
                if (policy.get("name", "").lower() in sent_text and 
                    authority.get("name", "").lower() in sent_text):
                    phrase_match = any(p in sent_text for p in ["administered by", "managed by", "overseen by", "under the", "responsibility of"])
                    if phrase_match:
                        rel = {
                            "source": get_entity_id(policy, "Policy"),
                            "target": get_entity_id(authority, "Authority"),
                            "type": "ADMINISTERED_BY",
                            **provenance(0.7)
                        }
                        pair = (rel["source"], rel["target"], rel["type"])
                        if pair not in seen_pairs and rel["source"] and rel["target"]:
                            seen_pairs.add(pair)
                            relationships.append(rel)
        
        # OPERATES_IN (Authority → Country) - NEW for governance docs
        for authority in by_type.get("Authority", []):
            for country in by_type.get("Country", []):
                if (authority.get("name", "").lower() in sent_text and 
                    country.get("name", "").lower() in sent_text):
                    phrase_match = any(p in sent_text for p in ["in", "of", "within", "across"])
                    conf = 0.7 if phrase_match else 0.5
                    rel = {
                        "source": get_entity_id(authority, "Authority"),
                        "target": get_entity_id(country, "Country"),
                        "type": "OPERATES_IN",
                        **provenance(conf)
                    }
                    pair = (rel["source"], rel["target"], rel["type"])
                    if pair not in seen_pairs and rel["source"] and rel["target"]:
                        seen_pairs.add(pair)
                        relationships.append(rel)
        
        # RESPONSIBLE_FOR (Authority → TechDomain/Policy) - NEW for governance docs
        for authority in by_type.get("Authority", []):
            # Authority responsible for TechDomain
            for domain in by_type.get("TechDomain", []):
                if (authority.get("name", "").lower() in sent_text and 
                    domain.get("name", "").lower() in sent_text):
                    phrase_match = any(p in sent_text for p in ["responsible for", "oversees", "manages", "coordinates", "handles"])
                    if phrase_match:
                        rel = {
                            "source": get_entity_id(authority, "Authority"),
                            "target": get_entity_id(domain, "TechDomain"),
                            "type": "RESPONSIBLE_FOR",
                            **provenance(0.7)
                        }
                        pair = (rel["source"], rel["target"], rel["type"])
                        if pair not in seen_pairs and rel["source"] and rel["target"]:
                            seen_pairs.add(pair)
                            relationships.append(rel)
        
        # IMPLEMENTS (Country → Policy) - NEW for governance docs
        for country in by_type.get("Country", []):
            for policy in by_type.get("Policy", []):
                if (country.get("name", "").lower() in sent_text and 
                    policy.get("name", "").lower() in sent_text):
                    phrase_match = any(p in sent_text for p in ["implements", "implemented", "adopted", "ratified", "signed", "enacted"])
                    if phrase_match:
                        rel = {
                            "source": get_entity_id(country, "Country"),
                            "target": get_entity_id(policy, "Policy"),
                            "type": "IMPLEMENTS",
                            **provenance(0.75)
                        }
                        pair = (rel["source"], rel["target"], rel["type"])
                        if pair not in seen_pairs and rel["source"] and rel["target"]:
                            seen_pairs.add(pair)
                            relationships.append(rel)
        
        # INVOKES (Authority → Policy) - For treaty/policy invocation
        for authority in by_type.get("Authority", []):
            for policy in by_type.get("Policy", []):
                if (authority.get("name", "").lower() in sent_text and 
                    policy.get("name", "").lower() in sent_text):
                    phrase_match = any(p in sent_text for p in ["invoke", "invokes", "invoked", "trigger", "activate"])
                    if phrase_match:
                        rel = {
                            "source": get_entity_id(authority, "Authority"),
                            "target": get_entity_id(policy, "Policy"),
                            "type": "INVOKES",
                            **provenance(0.8)
                        }
                        pair = (rel["source"], rel["target"], rel["type"])
                        if pair not in seen_pairs and rel["source"] and rel["target"]:
                            seen_pairs.add(pair)
                            relationships.append(rel)
        
        # COOPERATES_WITH (Country → Country) - For international relations
        countries = by_type.get("Country", [])
        if len(countries) >= 2:
            country_names_in_sent = [c for c in countries if c.get("name", "").lower() in sent_text]
            if len(country_names_in_sent) >= 2:
                phrase_match = any(p in sent_text for p in ["cooperat", "partner", "alliance", "agreement", "treaty", "collaboration"])
                if phrase_match:
                    for i, c1 in enumerate(country_names_in_sent):
                        for c2 in country_names_in_sent[i+1:]:
                            rel = {
                                "source": get_entity_id(c1, "Country"),
                                "target": get_entity_id(c2, "Country"),
                                "type": "COOPERATES_WITH",
                                **provenance(0.65)
                            }
                            pair = (rel["source"], rel["target"], rel["type"])
                            if pair not in seen_pairs and rel["source"] and rel["target"]:
                                seen_pairs.add(pair)
                                relationships.append(rel)
        
        # REGULATED_BY (Equipment → Policy)
        for equip in by_type.get("Equipment", []):
            for policy in by_type.get("Policy", []):
                if (equip.get("name", "").lower() in sent_text and 
                    policy.get("name", "").lower() in sent_text):
                    phrase_match = any(p in sent_text for p in ["regulated by", "governed by", "under"])
                    conf = 0.7 if phrase_match else 0.5
                    rel = {
                        "source": get_entity_id(equip, "Equipment"),
                        "target": get_entity_id(policy, "Policy"),
                        "type": "REGULATED_BY",
                        **provenance(conf)
                    }
                    pair = (rel["source"], rel["target"], rel["type"])
                    if pair not in seen_pairs and rel["source"] and rel["target"]:
                        seen_pairs.add(pair)
                        relationships.append(rel)
        
        # REQUIRES (Policy → Requirement)
        for policy in by_type.get("Policy", []):
            for req in by_type.get("Requirement", []):
                if (policy.get("name", "").lower() in sent_text or 
                    any(p in sent_text for p in ["regulation", "policy", "law", "act", "article"])):
                    phrase_match = any(p in sent_text for p in ["requires", "mandates", "must", "shall", "need"])
                    if phrase_match:
                        rel = {
                            "source": get_entity_id(policy, "Policy"),
                            "target": get_entity_id(req, "Requirement"),
                            "type": "REQUIRES",
                            **provenance(0.65)
                        }
                        pair = (rel["source"], rel["target"], rel["type"])
                        if pair not in seen_pairs and rel["source"] and rel["target"]:
                            seen_pairs.add(pair)
                            relationships.append(rel)
        
        # BELONGS_TO_DOMAIN (Equipment → TechDomain)
        for equip in by_type.get("Equipment", []):
            for domain in by_type.get("TechDomain", []):
                if equip.get("name", "").lower() in sent_text:
                    phrase_match = any(p in sent_text for p in ["ai", "artificial intelligence", "powered", "enabled", "based"])
                    conf = 0.7 if phrase_match else 0.5
                    rel = {
                        "source": get_entity_id(equip, "Equipment"),
                        "target": get_entity_id(domain, "TechDomain"),
                        "type": "BELONGS_TO_DOMAIN",
                        **provenance(conf)
                    }
                    pair = (rel["source"], rel["target"], rel["type"])
                    if pair not in seen_pairs and rel["source"] and rel["target"]:
                        seen_pairs.add(pair)
                        relationships.append(rel)
    
    return relationships


# =============================================================================
# Main Extractor Functions (API)
# =============================================================================

def spacy_extract_entities(text: str) -> List[Dict[str, Any]]:
    """Extract entities using EntityRuler-enhanced pipeline."""
    return extract_entities_with_ruler(text)


def spacy_extract_relationships(
    text: str, 
    entities: List[Dict], 
    document: Optional[str] = None, 
    section: Optional[str] = None
) -> List[Dict]:
    """Extract relationships using DependencyMatcher + rule-based fallback."""
    return extract_relationships_with_matcher(text, entities, document, section)


# =============================================================================
# SpacyEntityExtractor Class (for pipeline compatibility)
# =============================================================================

class SpacyEntityExtractor:
    """Entity and relationship extractor using enhanced spaCy with EntityRuler."""
    
    def __init__(self):
        self.stats = {
            "chunks_processed": 0,
            "chunks_with_entities": 0,
            "total_entities": 0,
            "total_relationships": 0,
            "unique_entities": {
                "policies": set(),
                "countries": set(),
                "authorities": set(),
                "equipment": set(),
                "tech_domains": set(),
                "requirements": set(),
            }
        }
        # Initialize the enhanced NLP pipeline
        get_enhanced_nlp()
        logger.info("SpacyEntityExtractor initialized with EntityRuler and DependencyMatcher")

    def enrich_chunk(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        text = chunk.get("text", "")
        document = chunk.get("document", None)
        section = chunk.get("section", None)
        
        if not text:
            chunk["entities"] = []
            chunk["relationships"] = []
            return chunk
        
        entities = spacy_extract_entities(text)
        relationships = spacy_extract_relationships(text, entities, document, section)
        
        chunk["entities"] = entities
        chunk["relationships"] = relationships
        
        # Update statistics
        self.stats["chunks_processed"] += 1
        if entities or relationships:
            self.stats["chunks_with_entities"] += 1
        self.stats["total_entities"] += len(entities)
        self.stats["total_relationships"] += len(relationships)
        
        for entity in entities:
            entity_type = entity.get("type", "").lower()
            entity_name = entity.get("name", entity.get("description", ""))
            type_map = {
                "policy": "policies", "country": "countries", "authority": "authorities",
                "equipment": "equipment", "techdomain": "tech_domains", "requirement": "requirements"
            }
            stat_key = type_map.get(entity_type)
            if stat_key and entity_name:
                self.stats["unique_entities"][stat_key].add(entity_name.lower())
        
        return chunk

    def enrich_chunks(self, chunks: List[Dict[str, Any]], batch_size: int = 10, delay: float = 0.0) -> List[Dict[str, Any]]:
        import time
        enriched = []
        for i, chunk in enumerate(chunks):
            enriched_chunk = self.enrich_chunk(chunk)
            enriched.append(enriched_chunk)
            if delay > 0:
                time.sleep(delay)
            if (i + 1) % batch_size == 0 or (i + 1) == len(chunks):
                logger.info(f"[EntityRuler+DependencyMatcher] Progress: {i + 1}/{len(chunks)} chunks")
        return enriched

    def get_statistics(self) -> Dict[str, Any]:
        """Return extraction statistics."""
        return self.stats



