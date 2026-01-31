"""
Policy and Regulation RAG System.

Architecture (as specified):
    User Question
       ↓
    Query Understanding (Intent + Entity Extraction)
       ↓
    Entity Linking (Text → KG Nodes)
       ↓
    KG Retrieval (Neo4j Cypher)
       ↓
    (Optional Vector Retrieval)
       ↓
    Context Builder (KG Facts → LLM Context)
       ↓
    Prompt (Anti-Hallucination)
       ↓
    LLM Answer
       ↓
    Sources & Confidence
"""

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import spacy
from dotenv import load_dotenv
from groq import Groq
from neo4j import Driver, GraphDatabase

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"


# =============================================================================
# 1. Question Types (Very Important)
# =============================================================================

class QuestionType(Enum):
    """Define question types for the RAG system."""
    COMPLIANCE = "compliance"           # "Is X compliant with Y?"
    REQUIREMENTS = "requirements"       # "What paperwork is required for X in Y?"
    POLICY_APPLICABILITY = "policy"     # "Does policy X apply to equipment Y?"
    AUTHORITY = "authority"             # "Who regulates X in Y?"
    DOCUMENTATION = "documentation"     # "What documents are needed for X?"
    COMPARISON = "comparison"           # "Compare regulations in X vs Y"
    GENERAL = "general"                 # Fallback for unclassified queries


@dataclass
class QueryTemplate:
    """Template for different question types."""
    question_type: QuestionType
    cypher_template: str
    context_template: str
    required_entities: List[str]


# Query templates for each question type
QUERY_TEMPLATES = {
    QuestionType.REQUIREMENTS: QueryTemplate(
        question_type=QuestionType.REQUIREMENTS,
        cypher_template="""
            MATCH (p:Policy)-[:APPLIES_IN]->(c:Country)
            WHERE c.iso_code = $country OR toLower(c.name) CONTAINS toLower($country)
            OPTIONAL MATCH (p)-[:ISSUED_BY]->(a:Authority)
            OPTIONAL MATCH (a2:Authority)-[:OPERATES_IN]->(c)
            RETURN p.name as policy, p.policy_type as policy_type,
                   c.name as country, COALESCE(a.name, a2.name) as authority
            LIMIT 20
        """,
        context_template="Requirements and policies in {country}",
        required_entities=["country"]
    ),
    QuestionType.POLICY_APPLICABILITY: QueryTemplate(
        question_type=QuestionType.POLICY_APPLICABILITY,
        cypher_template="""
            MATCH (p:Policy)-[:APPLIES_IN]->(c:Country)
            WHERE toLower(p.name) CONTAINS toLower($policy)
               OR c.iso_code = $country OR toLower(c.name) CONTAINS toLower($country)
            OPTIONAL MATCH (p)-[:ISSUED_BY]->(a:Authority)
            OPTIONAL MATCH (c2:Country)-[:IMPLEMENTS]->(p)
            RETURN p.name as policy, p.policy_type as policy_type, c.name as country,
                   a.name as authority, c2.name as implementing_country
            LIMIT 20
        """,
        context_template="Policy applicability for {policy} in {country}",
        required_entities=["country"]
    ),
    QuestionType.AUTHORITY: QueryTemplate(
        question_type=QuestionType.AUTHORITY,
        cypher_template="""
            MATCH (a:Authority)-[:OPERATES_IN]->(c:Country)
            WHERE c.iso_code = $country OR toLower(c.name) CONTAINS toLower($country)
            OPTIONAL MATCH (p:Policy)-[:ISSUED_BY]->(a)
            OPTIONAL MATCH (p)-[:ADMINISTERED_BY]->(a)
            RETURN DISTINCT a.name as authority, a.level as authority_level, 
                   p.name as policy, c.name as country
            LIMIT 20
        """,
        context_template="Regulatory authorities in {country}",
        required_entities=["country"]
    ),
    QuestionType.DOCUMENTATION: QueryTemplate(
        question_type=QuestionType.DOCUMENTATION,
        cypher_template="""
            MATCH (p:Policy)-[:APPLIES_IN]->(c:Country)
            OPTIONAL MATCH (p)-[:ISSUED_BY]->(a:Authority)
            WHERE p.name CONTAINS $equipment OR $equipment = ''
            RETURN p.name as policy, p.policy_type as policy_type,
                   c.name as country, a.name as authority
            LIMIT 20
        """,
        context_template="Documentation and policies for {equipment}",
        required_entities=["equipment"]
    ),
    QuestionType.COMPLIANCE: QueryTemplate(
        question_type=QuestionType.COMPLIANCE,
        cypher_template="""
            MATCH (p:Policy)-[:APPLIES_IN]->(c:Country)
            OPTIONAL MATCH (p)-[:ISSUED_BY]->(a:Authority)
            OPTIONAL MATCH (a)-[:RESPONSIBLE_FOR]->(t:TechDomain)
            RETURN p.name as policy, p.policy_type as policy_type,
                   c.name as country, a.name as authority, t.name as tech_domain
            LIMIT 20
        """,
        context_template="Compliance requirements",
        required_entities=["equipment"]
    ),
    QuestionType.GENERAL: QueryTemplate(
        question_type=QuestionType.GENERAL,
        cypher_template="""
            MATCH (p:Policy)
            WHERE ($policy <> '' AND (
                   toLower(replace(p.name, '\n', ' ')) CONTAINS toLower($policy) 
                   OR ANY(word IN split($policy, ' ') WHERE size(word) > 3 AND toLower(replace(p.name, '\n', ' ')) CONTAINS toLower(word))
               ))
               OR ($country <> '' AND toLower(p.name) CONTAINS toLower($country))
            OPTIONAL MATCH (p)-[:APPLIES_IN]->(c:Country)
            OPTIONAL MATCH (p)-[:ISSUED_BY]->(a:Authority)
            OPTIONAL MATCH (c2:Country)-[:IMPLEMENTS]->(p)
            RETURN DISTINCT p.name as policy, p.policy_type as policy_type, 
                   c.name as country, a.name as authority,
                   c2.name as implementing_country
            LIMIT 20
        """,
        context_template="General policy information",
        required_entities=[]
    ),
}


# =============================================================================
# 2. Query Understanding (Intent + Entity Extraction)
# =============================================================================

@dataclass
class ParsedQuery:
    """Structured representation of a parsed user query."""
    original_query: str
    question_type: QuestionType
    intent: str
    equipment: Optional[str] = None
    country: Optional[str] = None
    policy: Optional[str] = None
    authority: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    confidence: float = 0.0


class QueryUnderstanding:
    """Parse and understand user queries to extract intent and entities."""
    
    # Intent detection patterns
    INTENT_PATTERNS = {
        QuestionType.REQUIREMENTS: [
            r"what.*(?:requirements?|paperwork|documents?).*(?:for|needed|required)",
            r"how\s+(?:to|do\s+i).*(?:register|certify|approve)",
            r"(?:requirements?|regulations?).*(?:in|for)",
            r"what\s+(?:do\s+i\s+)?need\s+(?:to|for)",
            r"steps?\s+(?:to|for).*(?:register|certify|approve)",
        ],
        QuestionType.POLICY_APPLICABILITY: [
            r"(?:does|do|is).*(?:policy|regulation|law).*(?:apply|applicable)",
            r"what.*(?:policies?|regulations?).*(?:apply|govern)",
            r"which.*(?:policies?|regulations?).*(?:cover|regulate)",
            r"tell.*about.*(?:policy|regulation|law)",
        ],
        QuestionType.AUTHORITY: [
            r"who\s+(?:regulates?|enforces?|oversees?|is\s+responsible)",
            r"which\s+(?:authority|agency|body|ministry)",
            r"regulatory\s+(?:authority|body|agency)",
            r"(?:contact|reach).*(?:authority|regulator)",
        ],
        QuestionType.DOCUMENTATION: [
            r"what\s+(?:documents?|paperwork|forms?).*(?:needed|required)",
            r"(?:documentation|forms?|paperwork)\s+(?:for|required)",
            r"(?:submit|file|provide).*(?:documents?|forms?)",
        ],
        QuestionType.COMPLIANCE: [
            r"(?:is|are).*(?:compliant|compliance)",
            r"how\s+(?:to|do\s+i).*(?:comply|compliant)",
            r"(?:compliance|compliant).*(?:with|for)",
            r"(?:meet|satisfy).*(?:requirements?|standards?)",
        ],
        QuestionType.COMPARISON: [
            r"(?:compare|comparison|difference).*(?:between|vs|versus)",
            r"(?:how|what).*(?:differ|different)",
            r"(\w+)\s+vs\.?\s+(\w+)",
        ],
    }
    
    # Country patterns with ISO codes
    COUNTRY_PATTERNS = {
        "IN": [r"\bindia\b", r"\bindian\b"],
        "US": [r"\b(?:us|usa|united\s+states|america)\b"],
        "GB": [r"\b(?:uk|united\s+kingdom|britain|british)\b"],
        "EU": [r"\b(?:eu|europe|european\s+union)\b"],
        "DE": [r"\b(?:germany|german)\b"],
        "FR": [r"\b(?:france|french)\b"],
        "JP": [r"\b(?:japan|japanese)\b"],
        "CN": [r"\b(?:china|chinese)\b"],
        "AU": [r"\b(?:australia|australian)\b"],
        "CA": [r"\b(?:canada|canadian)\b"],
        "BR": [r"\b(?:brazil|brazilian)\b"],
        "SG": [r"\b(?:singapore)\b"],
        "KR": [r"\b(?:korea|korean|south\s+korea)\b"],
    }
    
    # Equipment patterns
    EQUIPMENT_PATTERNS = {
        "mri_scanner": [r"\b(?:mri|magnetic\s+resonance)\b"],
        "ct_scanner": [r"\b(?:ct|computed\s+tomography|cat\s+scan)\b"],
        "xray": [r"\b(?:x-?ray|radiograph)\b"],
        "ultrasound": [r"\b(?:ultrasound|sonograph|echo)\b"],
        "ventilator": [r"\b(?:ventilator|respirator)\b"],
        "pacemaker": [r"\b(?:pacemaker|cardiac\s+pacemaker)\b"],
        "defibrillator": [r"\b(?:defibrillator|aed)\b"],
        "infusion_pump": [r"\b(?:infusion\s+pump|iv\s+pump)\b"],
        "patient_monitor": [r"\b(?:patient\s+monitor|vital\s+signs?\s+monitor)\b"],
        "ai_device": [r"\b(?:ai|artificial\s+intelligence).*(?:device|equipment|scanner)\b"],
    }
    
    def __init__(self):
        """Initialize with spaCy model."""
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
            self.nlp = spacy.load("en_core_web_sm")
    
    def parse(self, query: str) -> ParsedQuery:
        """
        Parse a user query to extract intent and entities.
        
        Returns structured query:
        {
          "equipment": "AI MRI Scanner",
          "country": "India",
          "intent": "requirements"
        }
        """
        query_lower = query.lower()
        
        # Detect question type/intent
        question_type = QuestionType.GENERAL
        intent_confidence = 0.0
        
        for q_type, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    question_type = q_type
                    intent_confidence = 0.8
                    break
            if question_type != QuestionType.GENERAL:
                break
        
        # Extract country
        country = None
        country_code = None
        for code, patterns in self.COUNTRY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    country_code = code
                    # Get full country name
                    country = self._get_country_name(code)
                    break
            if country:
                break
        
        # Extract equipment
        equipment = None
        for equip_type, patterns in self.EQUIPMENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, query_lower)
                if match:
                    equipment = equip_type.replace("_", " ").title()
                    break
            if equipment:
                break
        
        # Use spaCy for additional entity extraction
        doc = self.nlp(query)
        keywords = [token.text for token in doc if not token.is_stop and not token.is_punct and len(token.text) > 2]
        
        # Extract policy names (LAW entities or known policy patterns)
        policy = None
        for ent in doc.ents:
            if ent.label_ == "LAW":
                policy = ent.text
                break
        
        # If no LAW entity found, try to extract policy name from query
        if not policy:
            policy = self._extract_policy_from_query(query_lower, keywords)
        
        # Calculate overall confidence
        confidence = intent_confidence
        if equipment:
            confidence += 0.1
        if country:
            confidence += 0.1
        if policy:
            confidence += 0.1
        
        return ParsedQuery(
            original_query=query,
            question_type=question_type,
            intent=question_type.value,
            equipment=equipment,
            country=country,
            policy=policy,
            keywords=keywords,
            confidence=min(confidence, 1.0)
        )
    
    def _extract_policy_from_query(self, query_lower: str, keywords: List[str]) -> Optional[str]:
        """Extract policy name from query using patterns and keywords."""
        # Known policy patterns to look for
        policy_patterns = [
            r"abraham\s*accords?",
            r"article\s+\d+[a-z]?(?:\s+of\s+[\w\s]+)?",
            r"(?:the\s+)?(?:\d+(?:st|nd|rd|th))?\s*amendment(?:\s+act)?",
            r"(?:the\s+)?right\s+to\s+information\s+act",
            r"(?:the\s+)?rti\s+act",
            r"constitution",
            r"nato\s+treaty",
            r"north\s+atlantic\s+treaty",
            r"euro-?atlantic",
            r"national\s+security\s+strategy",
            r"strategic\s+concept",
        ]
        
        for pattern in policy_patterns:
            match = re.search(pattern, query_lower)
            if match:
                return match.group(0).strip()
        
        # If query contains "explain" or "what is", the main noun phrase is likely the policy
        explain_patterns = [
            r"(?:explain|describe|what\s+is|what\s+are|tell\s+me\s+about)\s+(?:the\s+)?(.+?)(?:\?|$)",
        ]
        
        for pattern in explain_patterns:
            match = re.search(pattern, query_lower)
            if match:
                potential_policy = match.group(1).strip()
                # Filter out very generic terms
                if len(potential_policy) > 3 and potential_policy not in ["it", "this", "that", "them"]:
                    return potential_policy
        
        return None
    
    def _get_country_name(self, iso_code: str) -> str:
        """Get full country name from ISO code."""
        names = {
            "IN": "India", "US": "United States", "GB": "United Kingdom",
            "EU": "European Union", "DE": "Germany", "FR": "France",
            "JP": "Japan", "CN": "China", "AU": "Australia", "CA": "Canada",
            "BR": "Brazil", "SG": "Singapore", "KR": "South Korea",
        }
        return names.get(iso_code, iso_code)


# =============================================================================
# 3. Entity Linking (Text → KG Nodes)
# =============================================================================

@dataclass
class LinkedEntities:
    """Entities linked to KG node IDs."""
    equipment_ids: List[str] = field(default_factory=list)
    country_ids: List[str] = field(default_factory=list)
    policy_ids: List[str] = field(default_factory=list)
    authority_ids: List[str] = field(default_factory=list)
    domain_ids: List[str] = field(default_factory=list)


class EntityLinker:
    """Link extracted entities to canonical KG nodes."""
    
    # Alias tables for exact matching
    EQUIPMENT_ALIASES = {
        "mri scanner": ["mri", "magnetic resonance", "mr scanner"],
        "ct scanner": ["ct", "computed tomography", "cat scan"],
        "x-ray machine": ["xray", "x-ray", "radiography"],
        "ultrasound": ["ultrasound", "sonography", "echo"],
        "ventilator": ["ventilator", "respirator"],
        "pacemaker": ["pacemaker", "cardiac pacemaker"],
        "defibrillator": ["defibrillator", "aed"],
        "infusion pump": ["infusion pump", "iv pump"],
        "patient monitor": ["patient monitor", "vital signs monitor"],
    }
    
    COUNTRY_ALIASES = {
        "IN": ["india", "indian"],
        "US": ["usa", "us", "united states", "america", "american"],
        "GB": ["uk", "united kingdom", "britain", "british", "england"],
        "EU": ["eu", "europe", "european union", "european"],
        "DE": ["germany", "german", "deutschland"],
        "FR": ["france", "french"],
        "JP": ["japan", "japanese"],
        "CN": ["china", "chinese", "prc"],
        "AU": ["australia", "australian"],
        "CA": ["canada", "canadian"],
    }
    
    def __init__(self, driver: Optional[Driver] = None):
        """Initialize with optional Neo4j connection."""
        self.driver = driver
    
    def link(self, parsed_query: ParsedQuery) -> LinkedEntities:
        """
        Link parsed query entities to KG node IDs.
        
        Methods:
        1. Exact match
        2. Alias tables
        3. (Optional) Embedding similarity
        """
        linked = LinkedEntities()
        
        # Link equipment
        if parsed_query.equipment:
            equip_lower = parsed_query.equipment.lower()
            for canonical, aliases in self.EQUIPMENT_ALIASES.items():
                if equip_lower in aliases or any(a in equip_lower for a in aliases):
                    equip_id = self._make_id("equipment", canonical)
                    linked.equipment_ids.append(equip_id)
                    break
            
            # If not found in aliases, try graph lookup
            if not linked.equipment_ids and self.driver:
                linked.equipment_ids = self._lookup_equipment_in_graph(parsed_query.equipment)
        
        # Link country
        if parsed_query.country:
            country_lower = parsed_query.country.lower()
            for iso_code, aliases in self.COUNTRY_ALIASES.items():
                if country_lower in aliases or any(a in country_lower for a in aliases):
                    country_id = self._make_id("country", iso_code)
                    linked.country_ids.append(country_id)
                    break
        
        # Link policy from graph if available
        if parsed_query.policy and self.driver:
            linked.policy_ids = self._lookup_policy_in_graph(parsed_query.policy)
        
        return linked
    
    def _make_id(self, prefix: str, value: str) -> str:
        """Create deterministic hash ID."""
        return f"{prefix}_" + hashlib.md5(value.lower().encode()).hexdigest()[:8]
    
    def _lookup_equipment_in_graph(self, equipment: str) -> List[str]:
        """Lookup equipment in Neo4j graph."""
        ids = []
        try:
            with self.driver.session() as session:  # type: ignore
                result = session.run(
                    """
                    MATCH (e:Equipment)
                    WHERE toLower(e.name) CONTAINS toLower($name)
                    RETURN e.equipment_id as id
                    LIMIT 5
                    """,
                    name=equipment
                )
                ids = [r["id"] for r in result if r["id"]]
        except Exception as e:
            logger.warning(f"Equipment graph lookup failed: {e}")
        return ids
    
    def _lookup_policy_in_graph(self, policy: str) -> List[str]:
        """Lookup policy in Neo4j graph."""
        ids = []
        try:
            with self.driver.session() as session:  # type: ignore
                result = session.run(
                    """
                    MATCH (p:Policy)
                    WHERE toLower(p.name) CONTAINS toLower($name)
                    RETURN p.policy_id as id
                    LIMIT 5
                    """,
                    name=policy
                )
                ids = [r["id"] for r in result if r["id"]]
        except Exception as e:
            logger.warning(f"Policy graph lookup failed: {e}")
        return ids


# =============================================================================
# 4. Graph Retrieval (Core RAG Step)
# =============================================================================

@dataclass
class RetrievedFact:
    """A single fact retrieved from the knowledge graph."""
    subject: str
    predicate: str
    object: str
    source_policy: Optional[str] = None
    source_authority: Optional[str] = None
    source_country: Optional[str] = None
    confidence: float = 1.0


@dataclass
class RetrievalResult:
    """Results from KG retrieval."""
    facts: List[RetrievedFact] = field(default_factory=list)
    raw_records: List[Dict] = field(default_factory=list)
    query_used: str = ""
    node_count: int = 0


class KGRetriever:
    """Retrieve relevant subgraph from Neo4j."""
    
    def __init__(self, uri: str, user: str, password: str):
        """Initialize Neo4j connection."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        """Close connection."""
        if self.driver:
            self.driver.close()
    
    def retrieve(self, parsed_query: ParsedQuery, linked_entities: LinkedEntities) -> RetrievalResult:
        """
        Retrieve relevant subgraph based on question type and linked entities.
        
        Returns structured facts, not raw text.
        """
        result = RetrievalResult()
        
        # Get appropriate query template
        template = QUERY_TEMPLATES.get(parsed_query.question_type)
        
        # Build query parameters
        params = {
            "equipment": parsed_query.equipment or "",
            "country": parsed_query.country or "",
            "policy": parsed_query.policy or "",
        }
        
        # Execute main retrieval query
        if template:
            result = self._execute_template_query(template, params)
        
        # If no results, try fallback queries
        if not result.facts:
            result = self._execute_fallback_queries(parsed_query, params)
        
        # Determine if we should also run text search
        # Run text search if:
        # 1. No KG results found, OR
        # 2. We have a policy query (to get actual content), OR
        # 3. Query is a "who is" type question (looking for person info)
        should_text_search = (
            not result.facts or 
            parsed_query.policy or
            re.search(r'\bwho\s+(is|are|was|were)\b', parsed_query.original_query.lower())
        )
        
        if should_text_search:
            text_result = self._execute_text_search(parsed_query)
            if text_result.facts:
                # Merge text search results with KG results
                result.facts.extend(text_result.facts)
                result.raw_records.extend(text_result.raw_records)
                # If text search found results, mark it
                if text_result.query_used == "text_search":
                    result.query_used = result.query_used or ""
                    if result.query_used and "text_search" not in result.query_used:
                        result.query_used = "combined"
                    elif not result.query_used:
                        result.query_used = "text_search"
        
        return result
    
    def _execute_template_query(self, template: QueryTemplate, params: Dict) -> RetrievalResult:
        """Execute a template-based Cypher query."""
        result = RetrievalResult()
        
        try:
            with self.driver.session() as session:  # type: ignore
                records = session.run(template.cypher_template, **params)  # type: ignore
                
                for record in records:
                    record_dict = dict(record)
                    result.raw_records.append(record_dict)
                    
                    # Convert to structured facts
                    fact = self._record_to_fact(record_dict)
                    if fact:
                        result.facts.append(fact)
                
                result.query_used = template.cypher_template
                result.node_count = len(result.raw_records)
                
        except Exception as e:
            logger.error(f"Template query failed: {e}")
        
        return result
    
    def _execute_fallback_queries(self, parsed_query: ParsedQuery, params: Dict) -> RetrievalResult:
        """Execute fallback queries when template query returns no results."""
        result = RetrievalResult()
        
        # Get policy search terms from parsed query
        policy_search = parsed_query.policy or ""
        
        fallback_queries = [
            # Search policies by name keywords (handles newlines in policy names)
            """
            MATCH (p:Policy)
            WHERE $policy <> '' AND (
                toLower(replace(p.name, '\n', ' ')) CONTAINS toLower($policy)
                OR ANY(word IN split($policy, ' ') WHERE size(word) > 3 AND toLower(replace(p.name, '\n', ' ')) CONTAINS toLower(word))
            )
            OPTIONAL MATCH (p)-[:APPLIES_IN]->(c:Country)
            OPTIONAL MATCH (p)-[:ISSUED_BY]->(a:Authority)
            RETURN DISTINCT p.name as policy, p.policy_type as policy_type, 
                   c.name as country, a.name as authority
            LIMIT 20
            """,
            # Get all policies for a country with authorities
            """
            MATCH (p:Policy)-[:APPLIES_IN]->(c:Country)
            WHERE c.iso_code = $country OR toLower(c.name) CONTAINS toLower($country)
            OPTIONAL MATCH (p)-[:ISSUED_BY]->(a:Authority)
            OPTIONAL MATCH (a2:Authority)-[:OPERATES_IN]->(c)
            RETURN p.name as policy, p.policy_type as policy_type, 
                   c.name as country, COALESCE(a.name, a2.name) as authority
            LIMIT 20
            """,
            # Get authorities operating in a country
            """
            MATCH (a:Authority)-[:OPERATES_IN]->(c:Country)
            WHERE c.iso_code = $country OR toLower(c.name) CONTAINS toLower($country) OR $country = ''
            OPTIONAL MATCH (p:Policy)-[:ISSUED_BY]->(a)
            RETURN DISTINCT a.name as authority, c.name as country, p.name as policy
            LIMIT 20
            """,
            # Get countries and their policies (general overview)
            """
            MATCH (p:Policy)-[:APPLIES_IN]->(c:Country)
            OPTIONAL MATCH (p)-[:ISSUED_BY]->(a:Authority)
            RETURN p.name as policy, p.policy_type as policy_type,
                   c.name as country, a.name as authority
            LIMIT 15
            """,
            # Get cooperating countries
            """
            MATCH (c1:Country)-[:COOPERATES_WITH]->(c2:Country)
            RETURN c1.name as country, c2.name as partner_country, 'cooperation' as relationship_type
            LIMIT 15
            """
        ]
        
        try:
            with self.driver.session() as session:  # type: ignore
                for query in fallback_queries:
                    records = list(session.run(query, **params))  # type: ignore
                    if records:
                        for record in records:
                            record_dict = dict(record)
                            result.raw_records.append(record_dict)
                            fact = self._record_to_fact(record_dict)
                            if fact:
                                result.facts.append(fact)
                        result.query_used = query
                        result.node_count = len(records)
                        break
        except Exception as e:
            logger.error(f"Fallback query failed: {e}")
        
        return result
    
    def _execute_text_search(self, parsed_query: ParsedQuery) -> RetrievalResult:
        """
        Execute text-based search on Chunk nodes when entity-based search fails.
        
        Searches the raw text content of chunks for relevant keywords from the query.
        """
        result = RetrievalResult()
        
        # Build search terms from the query
        search_terms = []
        if parsed_query.policy:
            search_terms.append(parsed_query.policy.lower())
        if parsed_query.country:
            search_terms.append(parsed_query.country.lower())
        if parsed_query.equipment:
            search_terms.append(parsed_query.equipment.lower())
        
        # Also extract keywords from original query
        original_query = parsed_query.original_query.lower()
        # Extract meaningful phrases (3+ char words, exclude common words)
        stop_words = {'the', 'what', 'who', 'how', 'why', 'when', 'where', 'which', 
                      'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had',
                      'does', 'did', 'will', 'would', 'could', 'should', 'can',
                      'for', 'and', 'but', 'with', 'about', 'from', 'into', 'is'}
        words = [w for w in original_query.split() if len(w) > 2 and w not in stop_words]
        
        # Normalize search terms - handle abbreviations like "S.Krishnan" -> "S. Krishnan"
        normalized_terms = []
        for term in search_terms + words:
            # Add space after period in abbreviations (e.g., "S.K" -> "S. K")
            normalized = re.sub(r'\.([A-Za-z])', r'. \1', term)
            normalized_terms.append(normalized)
            if normalized != term:
                normalized_terms.append(term)  # Also keep original
        
        # Build search query
        if not search_terms and not words:
            return result
            return result
        
        try:
            with self.driver.session() as session:
                cypher = """
                MATCH (c:Chunk)
                WHERE toLower(c.text) CONTAINS toLower($search_text)
                RETURN c.id as chunk_id, c.text as chunk_text
                LIMIT 10
                """
                
                records = []
                search_used = ""
                
                # First priority: search for the extracted policy name
                if search_terms:
                    for term in search_terms:
                        records = list(session.run(cypher, search_text=term))
                        if records:
                            search_used = term
                            break
                
                # Second priority: try normalized terms (handles abbreviations like S.Krishnan)
                if not records and normalized_terms:
                    for term in normalized_terms:
                        records = list(session.run(cypher, search_text=term))
                        if records:
                            search_used = term
                            break
                
                # Third priority: try multi-word phrases from query
                if not records:
                    query_text = " ".join(words[:5])  # Use first 5 meaningful words
                    records = list(session.run(cypher, search_text=query_text))
                    if records:
                        search_used = query_text
                
                # Fourth priority: try individual keywords
                if not records and words:
                    for word in words[:3]:
                        records = list(session.run(cypher, search_text=word))
                        if records:
                            search_used = word
                            break
                
                if records:
                    # Determine what search term was used for the fact description
                    search_description = search_used or (search_terms[0] if search_terms else " ".join(words[:5]))
                    
                    for record in records:
                        record_dict = dict(record)
                        result.raw_records.append(record_dict)
                        
                        # Create a fact from the text chunk
                        chunk_text = record_dict.get("chunk_text", "")
                        chunk_id = record_dict.get("chunk_id", "")
                        
                        # Extract document name from chunk_id if possible
                        doc_name = chunk_id.split("_")[0] if "_" in chunk_id else "document"
                        
                        fact = RetrievedFact(
                            subject=doc_name,
                            predicate="contains information about",
                            object=search_description,
                            source_policy=None,
                            source_authority=None,
                            source_country=None,
                            confidence=0.8
                        )
                        result.facts.append(fact)
                        
                        # Also store the actual text for context building
                        result.raw_records[-1]["text_content"] = chunk_text
                    
                    result.query_used = "text_search"
                    result.node_count = len(records)
                    
        except Exception as e:
            logger.error(f"Text search failed: {e}")
        
        return result
    
    def _record_to_fact(self, record: Dict) -> Optional[RetrievedFact]:
        """Convert a Neo4j record to a structured fact."""
        # Extract key fields
        equipment = record.get("equipment")
        policy = record.get("policy")
        requirement = record.get("requirement")
        country = record.get("country")
        authority = record.get("authority")
        
        # Build fact based on available data
        if equipment and policy:
            return RetrievedFact(
                subject=equipment,
                predicate="is regulated by",
                object=policy,
                source_policy=policy,
                source_authority=authority,
                source_country=country
            )
        elif policy and requirement:
            return RetrievedFact(
                subject=policy,
                predicate="requires",
                object=requirement,
                source_policy=policy,
                source_authority=authority,
                source_country=country
            )
        elif policy and country:
            return RetrievedFact(
                subject=policy,
                predicate="applies in",
                object=country,
                source_policy=policy,
                source_authority=authority,
                source_country=country
            )
        elif authority and policy:
            return RetrievedFact(
                subject=authority,
                predicate="enforces",
                object=policy,
                source_policy=policy,
                source_authority=authority,
                source_country=country
            )
        
        return None


# =============================================================================
# 5. Context Builder (Critical - Only KG Facts, No Inference)
# =============================================================================

class ContextBuilder:
    """
    Build LLM-ready context from graph results.
    
    Rules:
    - Only KG-derived facts
    - No inference
    - No speculation
    """
    
    def build(self, retrieval_result: RetrievalResult, parsed_query: ParsedQuery) -> str:
        """
        Convert graph results into LLM-readable context.
        
        Output example:
        "In India, AI MRI scanners must be registered under the Digital Health Act."
        """
        if not retrieval_result.facts:
            return "No specific information found in the knowledge graph for this query."
        
        context_lines = []
        
        # Check if this is a text-based search result or combined
        is_text_search = retrieval_result.query_used in ["text_search", "combined"]
        
        # First, add any text content from chunks (most detailed info)
        if is_text_search:
            text_content_added = False
            seen_texts = set()
            # Look for records with text_content (from text search)
            for record in retrieval_result.raw_records:
                text_content = record.get("text_content", record.get("chunk_text", ""))
                if text_content and text_content not in seen_texts:
                    if not text_content_added:
                        context_lines.append("## Relevant Document Content:")
                        text_content_added = True
                    # Truncate long texts
                    if len(text_content) > 800:
                        text_content = text_content[:800] + "..."
                    context_lines.append(f"\n{text_content}")
                    seen_texts.add(text_content)
                    if len(seen_texts) >= 3:  # Limit to 3 text chunks
                        break
            
            # If we only have text content, return it
            if retrieval_result.query_used == "text_search":
                return "\n".join(context_lines)
        
        # Group facts by type for cleaner output
        policy_facts = []
        requirement_facts = []
        authority_facts = []
        equipment_facts = []
        
        for fact in retrieval_result.facts:
            if "requires" in fact.predicate:
                requirement_facts.append(fact)
            elif "regulated by" in fact.predicate:
                equipment_facts.append(fact)
            elif "enforces" in fact.predicate:
                authority_facts.append(fact)
            else:
                policy_facts.append(fact)
        
        # Build context sections
        if equipment_facts:
            context_lines.append("## Equipment Regulations:")
            seen = set()
            for fact in equipment_facts[:5]:
                line = f"- {fact.subject} is regulated by {fact.object}"
                if fact.source_country:
                    line += f" in {fact.source_country}"
                if line not in seen:
                    context_lines.append(line)
                    seen.add(line)
        
        if requirement_facts:
            context_lines.append("\n## Requirements:")
            seen = set()
            for fact in requirement_facts[:5]:
                line = f"- {fact.subject} requires: {fact.object}"
                if line not in seen:
                    context_lines.append(line)
                    seen.add(line)
        
        if authority_facts:
            context_lines.append("\n## Regulatory Authorities:")
            seen = set()
            for fact in authority_facts[:5]:
                line = f"- {fact.subject} enforces {fact.object}"
                if fact.source_country:
                    line += f" in {fact.source_country}"
                if line not in seen:
                    context_lines.append(line)
                    seen.add(line)
        
        if policy_facts:
            context_lines.append("\n## Policies:")
            seen = set()
            for fact in policy_facts[:5]:
                line = f"- {fact.subject} {fact.predicate} {fact.object}"
                if line not in seen:
                    context_lines.append(line)
                    seen.add(line)
        
        return "\n".join(context_lines)
    
    def build_sources(self, retrieval_result: RetrievalResult) -> List[Dict[str, str]]:
        """
        Extract source attribution from retrieved facts.
        
        Returns:
        - Policy name
        - Authority  
        - Country/Document reference
        """
        sources = []
        seen = set()
        
        # Handle text search or combined results - add text sources first
        if retrieval_result.query_used in ["text_search", "combined"]:
            for record in retrieval_result.raw_records:
                chunk_id = record.get("chunk_id", "")
                if chunk_id:  # Only process records with chunk_id (from text search)
                    # Extract document name from chunk_id
                    doc_name = chunk_id.split("_")[0] if "_" in chunk_id else "Document"
                    source_key = (doc_name, "Text Search", "N/A")
                    if source_key not in seen:
                        sources.append({
                            "policy": doc_name,
                            "authority": "Direct text match",
                            "country": "N/A",
                        })
                        seen.add(source_key)
            
            # If we found text sources, return them (prioritize over KG sources)
            if sources:
                return sources[:5]
        
        # Handle structured KG results
        for fact in retrieval_result.facts:
            source_key = (fact.source_policy, fact.source_authority, fact.source_country)
            if source_key not in seen and any(source_key):
                sources.append({
                    "policy": fact.source_policy or "Unknown",
                    "authority": fact.source_authority or "Unknown",
                    "country": fact.source_country or "Unknown",
                })
                seen.add(source_key)
        
        return sources[:5]  # Limit to top 5 sources


# =============================================================================
# 6. Prompt Design (Anti-Hallucination)
# =============================================================================

class PromptBuilder:
    """Build anti-hallucination prompts for the LLM."""
    
    SYSTEM_PROMPT = """You are a policy and regulatory compliance assistant specializing in governance, national security, and public policy documents.

CRITICAL INSTRUCTIONS:
1. Answer primarily using the provided context from the Knowledge Graph
2. If the context mentions a topic but lacks details, you MAY supplement with general knowledge, but CLEARLY mark it as such using "(General Knowledge:)" prefix
3. Do NOT invent specific policies, dates, or requirements
4. When supplementing with general knowledge, keep it brief and factual
5. Always prioritize the document context over general knowledge
6. Always mention the source policy/authority when available from the context
7. Be precise and factual - this is for regulatory compliance

Your role is to help users understand:
- Policy and regulation requirements
- National and international strategies
- Governance frameworks and authorities
- Required documentation and compliance"""

    USER_PROMPT_TEMPLATE = """Question: {question}

Question Type: {question_type}
Topic/Policy: {policy}
Country: {country}

=== KNOWLEDGE GRAPH CONTEXT ===
{context}
=== END OF CONTEXT ===

Instructions:
1. If the context contains information that answers the question, provide a CONFIDENT and DIRECT answer
2. Quote or paraphrase the relevant parts of the context
3. Only say "I cannot provide a complete answer" if the context truly has NO relevant information
4. If the context has partial information, present what IS available clearly"""

    # Fallback prompt when KG has no results - allows LLM to use general knowledge
    FALLBACK_SYSTEM_PROMPT = """You are a policy and regulatory compliance assistant specializing in governance, national security, and public policy.

The Knowledge Graph did not contain specific information for this query. You may use your general knowledge to provide a helpful response, but:
1. Clearly indicate that this answer is based on general knowledge, NOT from the document database
2. Be honest about limitations and uncertainties
3. Recommend the user verify critical information from official sources
4. Provide a balanced, factual overview"""

    FALLBACK_USER_PROMPT = """Question: {question}

The Knowledge Graph did not contain specific information about this topic.

Please provide a general overview based on your knowledge, but clearly indicate that this is general information and not from the specific documents in the database. Recommend verifying with official sources for critical decisions."""

    def build_prompt(self, query: str, parsed_query: ParsedQuery, context: str, use_fallback: bool = False) -> Tuple[str, str]:
        """Build system and user prompts."""
        if use_fallback:
            # Use fallback prompts when KG has no results
            user_prompt = self.FALLBACK_USER_PROMPT.format(question=query)
            return self.FALLBACK_SYSTEM_PROMPT, user_prompt
        
        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            question=query,
            question_type=parsed_query.question_type.value,
            policy=parsed_query.policy or "Not specified",
            country=parsed_query.country or "Not specified",
            context=context
        )
        return self.SYSTEM_PROMPT, user_prompt


# =============================================================================
# 7. LLM Answer Generator
# =============================================================================

@dataclass
class RAGResponse:
    """Complete RAG response with answer, sources, and confidence."""
    answer: str
    sources: List[Dict[str, str]]
    confidence: float
    question_type: str
    entities_found: Dict[str, Optional[str]]
    facts_retrieved: int
    requires_review: bool = False


class LLMAnswerGenerator:
    """Generate answers using Groq LLM with retrieved context."""
    
    def __init__(self, api_key: str, model: str = GROQ_MODEL):
        """Initialize Groq client."""
        self.client = Groq(api_key=api_key)
        self.model = model
        self.prompt_builder = PromptBuilder()
    
    def generate(
        self,
        query: str,
        parsed_query: ParsedQuery,
        context: str,
        sources: List[Dict[str, str]],
        facts_count: int,
        use_fallback: bool = False
    ) -> RAGResponse:
        """
        Generate answer with source attribution and confidence.
        
        Args:
            use_fallback: If True, use LLM's general knowledge when KG has no results
        """
        # Build prompts (use fallback if no facts found)
        system_prompt, user_prompt = self.prompt_builder.build_prompt(
            query, parsed_query, context, use_fallback=use_fallback
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3 if use_fallback else 0.2,  # Slightly higher for fallback
                max_tokens=1024,
            )
            
            answer = response.choices[0].message.content or ""
            
            # Add disclaimer for fallback answers
            if use_fallback and answer:
                answer = "⚠️ **Note: This answer is based on general knowledge, not from the document database.**\n\n" + answer
            
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            answer = f"I apologize, but I encountered an error generating a response: {str(e)}"
        
        # Calculate confidence (lower for fallback)
        confidence = self._calculate_confidence(parsed_query, facts_count, len(sources), use_fallback)
        
        # Determine if human review is needed
        requires_review = confidence < 0.6 or use_fallback
        
        return RAGResponse(
            answer=answer,
            sources=sources,
            confidence=confidence,
            question_type=parsed_query.question_type.value,
            entities_found={
                "equipment": parsed_query.equipment,
                "country": parsed_query.country,
                "policy": parsed_query.policy,
            },
            facts_retrieved=facts_count,
            requires_review=requires_review
        )
    
    def _calculate_confidence(self, parsed_query: ParsedQuery, facts_count: int, sources_count: int, use_fallback: bool = False) -> float:
        """Calculate confidence score for the response."""
        # Fallback answers have inherently lower confidence
        if use_fallback:
            return 0.4  # Fixed lower confidence for LLM-only answers
        
        confidence = 0.0
        
        # Query understanding confidence
        confidence += parsed_query.confidence * 0.3
        
        # Facts retrieved (more facts = higher confidence)
        if facts_count > 10:
            confidence += 0.3
        elif facts_count > 5:
            confidence += 0.2
        elif facts_count > 0:
            confidence += 0.1
        
        # Sources found
        if sources_count > 0:
            confidence += 0.2
        
        # Entity linking success
        if parsed_query.policy or parsed_query.country:
            confidence += 0.2
        
        return min(confidence, 1.0)


# =============================================================================
# RAG System - Main Interface
# =============================================================================

class RAGSystem:
    """
    Policy and Regulation RAG System.
    
    Pipeline:
        User Question → Query Understanding → Entity Linking →
        KG Retrieval → Context Builder → Prompt → LLM Answer → Sources & Confidence
    """
    
    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        groq_api_key: str = GROQ_API_KEY,
        groq_model: str = GROQ_MODEL,
    ):
        """Initialize the RAG system."""
        logger.info("Initializing RAG System...")
        
        # Initialize components
        self.query_understanding = QueryUnderstanding()
        self.kg_retriever = KGRetriever(neo4j_uri, neo4j_user, neo4j_password)
        self.entity_linker = EntityLinker(driver=self.kg_retriever.driver)
        self.context_builder = ContextBuilder()
        self.llm_generator = LLMAnswerGenerator(groq_api_key, groq_model)
        
        logger.info("RAG System initialized successfully")
    
    def query(self, user_query: str, verbose: bool = False) -> RAGResponse:
        """
        Process a user query through the complete RAG pipeline.
        
        Args:
            user_query: Natural language query
            verbose: Whether to log debug information
            
        Returns:
            RAGResponse with answer, sources, and confidence
        """
        # Step 1: Query Understanding
        parsed = self.query_understanding.parse(user_query)
        if verbose:
            logger.info(f"Parsed query: type={parsed.question_type.value}, "
                       f"policy={parsed.policy}, country={parsed.country}")
        
        # Step 2: Entity Linking
        linked = self.entity_linker.link(parsed)
        if verbose:
            logger.info(f"Linked entities: {linked}")
        
        # Step 3: KG Retrieval
        retrieved = self.kg_retriever.retrieve(parsed, linked)
        if verbose:
            logger.info(f"Retrieved {len(retrieved.facts)} facts from KG")
        
        # Step 4: Context Building
        context = self.context_builder.build(retrieved, parsed)
        sources = self.context_builder.build_sources(retrieved)
        if verbose:
            logger.info(f"Built context with {len(sources)} sources")
        
        # Determine if we need to use LLM fallback (no KG results)
        use_fallback = len(retrieved.facts) == 0 and len(retrieved.raw_records) == 0
        
        if use_fallback and verbose:
            logger.info("No KG results found, using LLM fallback mode")
        
        # Step 5: LLM Answer Generation
        response = self.llm_generator.generate(
            user_query, parsed, context, sources, len(retrieved.facts),
            use_fallback=use_fallback
        )
        
        # Step 6: Check if LLM couldn't answer from context - trigger fallback
        if not use_fallback and self._answer_indicates_no_info(response.answer):
            if verbose:
                logger.info("LLM indicates insufficient context, using fallback mode")
            
            # Regenerate with fallback mode (use LLM's general knowledge)
            response = self.llm_generator.generate(
                user_query, parsed, context, sources, len(retrieved.facts),
                use_fallback=True
            )
        
        return response
    
    def _answer_indicates_no_info(self, answer: str) -> bool:
        """
        Check if the LLM's answer indicates it couldn't find relevant information.
        
        Returns True if the answer suggests the context was completely irrelevant.
        Only triggers fallback for truly missing information, not incomplete info.
        """
        # Strong indicators that context is completely irrelevant
        no_info_phrases = [
            "cannot provide a complete answer",
            "no information about",
            "not mentioned in",
            "not found in the",
            "not available in",
            "provided context does not",
            "available information does not",
            "I don't have information",
            "I cannot find",
            "there is no mention",
            "no relevant information",
            "insufficient information",
            "not covered in",
            "outside the scope of"
        ]
        
        # If answer has these phrases but also mentions the topic, don't fallback
        # (means there's partial info that could be useful)
        partial_info_indicators = [
            "it only mentions",
            "it mentions",
            "references",
            "related to",
            "discusses",
            "context mentions",
            "document mentions"
        ]
        
        answer_lower = answer.lower()
        
        # Check if answer has any partial info indicators - don't fallback if so
        has_partial_info = any(phrase in answer_lower for phrase in partial_info_indicators)
        if has_partial_info:
            return False
        
        return any(phrase.lower() in answer_lower for phrase in no_info_phrases)
    
    def close(self):
        """Close connections."""
        self.kg_retriever.close()


# =============================================================================
# Interactive CLI
# =============================================================================

def format_response(response: RAGResponse) -> str:
    """Format RAG response for display."""
    output = []
    
    output.append("\n" + "=" * 60)
    output.append("💡 ANSWER")
    output.append("=" * 60)
    output.append(response.answer)
    
    output.append("\n" + "-" * 60)
    output.append("📊 METADATA")
    output.append("-" * 60)
    output.append(f"Question Type: {response.question_type}")
    output.append(f"Confidence: {response.confidence:.0%}")
    output.append(f"Facts Retrieved: {response.facts_retrieved}")
    
    # Show source type - check if fallback was used by looking for disclaimer in answer
    is_fallback = "⚠️ **Note: This answer is based on general knowledge" in response.answer
    if is_fallback:
        output.append("Source: LLM General Knowledge (Fallback)")
    else:
        output.append("Source: Knowledge Graph")
    
    output.append(f"Requires Review: {'Yes ⚠️' if response.requires_review else 'No ✓'}")
    
    if response.entities_found:
        output.append(f"Entities: {response.entities_found}")
    
    if response.sources:
        output.append("\n" + "-" * 60)
        output.append("📚 SOURCES")
        output.append("-" * 60)
        for src in response.sources:
            output.append(f"  • Policy: {src['policy']}")
            output.append(f"    Authority: {src['authority']}")
            output.append(f"    Country: {src['country']}")
    
    return "\n".join(output)


def run_interactive():
    """Run interactive RAG system CLI."""
    from src.config import config
    
    print("\n" + "=" * 60)
    print("📜 Policy and Regulation RAG System")
    print("=" * 60)
    print("\nInitializing system...")
    
    try:
        rag = RAGSystem(
            neo4j_uri=config.NEO4J_URI,
            neo4j_user=config.NEO4J_USER,
            neo4j_password=config.NEO4J_PASSWORD,
        )
        
        print("\n✅ System ready!")
        print("\nExample questions:")
        print("  • What is the National Security Strategy of the United States?")
        print("  • What are NATO's strategic objectives?")
        print("  • What policies govern public administration in India?")
        print("  • What is the Electricity Act and who administers it?")
        print("  • What are the key objectives of the Tariff Policy in India?")
        print("  • What role does the Planning Commission play in governance?")
        print("\nType 'quit' to exit, 'verbose' to toggle debug mode.\n")
        
        verbose = False
        
        while True:
            try:
                query = input("\n🔍 Your question: ").strip()
                
                if not query:
                    continue
                
                if query.lower() == 'quit':
                    print("\nGoodbye!")
                    break
                
                if query.lower() == 'verbose':
                    verbose = not verbose
                    print(f"Verbose mode: {'ON' if verbose else 'OFF'}")
                    continue
                
                print("\n⏳ Processing...")
                response = rag.query(query, verbose=verbose)
                print(format_response(response))
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
        
        rag.close()
        
    except Exception as e:
        print(f"\n❌ Failed to initialize: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_interactive()
