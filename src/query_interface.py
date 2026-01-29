"""
Query interface for the Policy Knowledge Graph.
Provides CLI and programmatic access to query the Neo4j graph.
"""

import logging
import os
import sys
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class GraphQueryInterface:
    """Query interface for the Policy Knowledge Graph."""
    
    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize query interface.
        
        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Connected to Neo4j: {uri}")
    
    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()
    
    def run_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Run a Cypher query and return results.
        
        Args:
            query: Cypher query string
            params: Query parameters
            
        Returns:
            List of result dictionaries
        """
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [dict(record) for record in result]
    
    # ===== Pre-built Queries =====
    
    def get_all_policies(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all Policy nodes."""
        query = """
        MATCH (p:Policy)
        RETURN p.policy_id AS policy_id, p.name AS name, p.policy_type AS policy_type
        LIMIT $limit
        """
        return self.run_query(query, {"limit": limit})
    
    def get_all_countries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all Country nodes."""
        query = """
        MATCH (c:Country)
        RETURN c.country_id AS country_id, c.name AS name, c.iso_code AS iso_code
        LIMIT $limit
        """
        return self.run_query(query, {"limit": limit})
    
    def get_policies_by_country(self, country_name: str) -> List[Dict[str, Any]]:
        """Get all policies that apply in a specific country."""
        query = """
        MATCH (p:Policy)-[r:APPLIES_IN]->(c:Country)
        WHERE toLower(c.name) CONTAINS toLower($country_name)
        RETURN p.policy_id AS policy_id, p.name AS policy_name, 
               c.name AS country_name, r.confidence AS confidence
        """
        return self.run_query(query, {"country_name": country_name})
    
    def get_authorities_for_policy(self, policy_name: str) -> List[Dict[str, Any]]:
        """Get authorities that issued a specific policy."""
        query = """
        MATCH (p:Policy)-[r:ISSUED_BY]->(a:Authority)
        WHERE toLower(p.name) CONTAINS toLower($policy_name)
        RETURN p.name AS policy_name, a.name AS authority_name, 
               a.level AS authority_level, r.confidence AS confidence
        """
        return self.run_query(query, {"policy_name": policy_name})
    
    def get_requirements_for_equipment(self, equipment_name: str) -> List[Dict[str, Any]]:
        """Get requirements for specific equipment."""
        query = """
        MATCH (e:Equipment)-[r:REQUIRES]->(req:Requirement)
        WHERE toLower(e.name) CONTAINS toLower($equipment_name)
        RETURN e.name AS equipment_name, req.description AS requirement,
               r.confidence AS confidence
        """
        return self.run_query(query, {"equipment_name": equipment_name})
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get statistics about the knowledge graph."""
        stats = {}
        
        # Node counts by label
        node_query = """
        CALL db.labels() YIELD label
        CALL apoc.cypher.run('MATCH (n:`' + label + '`) RETURN count(n) as count', {}) YIELD value
        RETURN label, value.count as count
        """
        # Fallback without APOC
        labels = ["Country", "Policy", "Authority", "Equipment", "Requirement", "TechDomain", "Document", "Chunk", "Section"]
        for label in labels:
            result = self.run_query(f"MATCH (n:{label}) RETURN count(n) as count")
            stats[f"node_{label}"] = result[0]["count"] if result else 0
        
        # Relationship counts
        rel_query = """
        MATCH ()-[r]->()
        RETURN type(r) as rel_type, count(r) as count
        ORDER BY count DESC
        """
        rel_results = self.run_query(rel_query)
        stats["relationships"] = {r["rel_type"]: r["count"] for r in rel_results}
        
        return stats
    
    def get_policies_with_provenance(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get policies with full provenance metadata."""
        query = """
        MATCH (p:Policy)-[r:APPLIES_IN]->(c:Country)
        RETURN p.policy_id AS policy_id, p.name AS policy_name, p.policy_type AS policy_type,
               c.name AS country_name, c.iso_code AS iso_code,
               r.confidence AS confidence, r.extracted_from AS source_document,
               r.section AS section, r.extracted_on AS extracted_date
        LIMIT $limit
        """
        return self.run_query(query, {"limit": limit})
    
    def search_entities(self, search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search for entities by name across all node types."""
        query = """
        CALL {
            MATCH (p:Policy) WHERE toLower(p.name) CONTAINS toLower($term) RETURN 'Policy' as type, p.name as name, p.policy_id as id
            UNION
            MATCH (c:Country) WHERE toLower(c.name) CONTAINS toLower($term) RETURN 'Country' as type, c.name as name, c.country_id as id
            UNION
            MATCH (a:Authority) WHERE toLower(a.name) CONTAINS toLower($term) RETURN 'Authority' as type, a.name as name, a.authority_id as id
            UNION
            MATCH (e:Equipment) WHERE toLower(e.name) CONTAINS toLower($term) RETURN 'Equipment' as type, e.name as name, e.equipment_id as id
        }
        RETURN type, name, id
        LIMIT $limit
        """
        return self.run_query(query, {"term": search_term, "limit": limit})
    
    def get_constraints_and_indexes(self) -> Dict[str, List[str]]:
        """Get all constraints and indexes in the database."""
        constraints = self.run_query("SHOW CONSTRAINTS")
        indexes = self.run_query("SHOW INDEXES")
        return {
            "constraints": [c.get("name", str(c)) for c in constraints],
            "indexes": [i.get("name", str(i)) for i in indexes]
        }


def interactive_mode(interface: GraphQueryInterface):
    """Run interactive query mode."""
    print("\n" + "=" * 60)
    print("📊 Policy Knowledge Graph - Interactive Query Interface")
    print("=" * 60)
    print("\nCommands:")
    print("  stats       - Show graph statistics")
    print("  policies    - List all policies")
    print("  countries   - List all countries")
    print("  provenance  - Show policies with provenance")
    print("  search <term> - Search entities")
    print("  cypher      - Enter custom Cypher query")
    print("  quit        - Exit")
    print()
    
    while True:
        try:
            cmd = input("query> ").strip().lower()
            
            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "stats":
                stats = interface.get_graph_statistics()
                print("\n📈 Graph Statistics:")
                for key, value in stats.items():
                    if key == "relationships":
                        print(f"  {key}:")
                        for rel_type, count in value.items():
                            print(f"    - {rel_type}: {count}")
                    else:
                        print(f"  {key}: {value}")
            elif cmd == "policies":
                results = interface.get_all_policies()
                print(f"\n📋 Policies ({len(results)}):")
                for r in results[:20]:
                    print(f"  - {r.get('name', 'N/A')} ({r.get('policy_type', 'N/A')})")
            elif cmd == "countries":
                results = interface.get_all_countries()
                print(f"\n🌍 Countries ({len(results)}):")
                for r in results[:20]:
                    iso = r.get('iso_code') or 'N/A'
                    print(f"  - {r.get('name', 'N/A')} [{iso}]")
            elif cmd == "provenance":
                results = interface.get_policies_with_provenance()
                print(f"\n📜 Policies with Provenance ({len(results)}):")
                for r in results:
                    print(f"  - {r.get('policy_name', 'N/A')} → {r.get('country_name', 'N/A')}")
                    print(f"    Source: {r.get('source_document', 'N/A')}")
                    print(f"    Confidence: {r.get('confidence', 'N/A')}")
            elif cmd.startswith("search "):
                term = cmd[7:].strip()
                results = interface.search_entities(term)
                print(f"\n🔍 Search Results for '{term}' ({len(results)}):")
                for r in results:
                    print(f"  - [{r.get('type', 'N/A')}] {r.get('name', 'N/A')}")
            elif cmd == "cypher":
                print("Enter Cypher query (end with ';'):")
                query_lines = []
                while True:
                    line = input("  ")
                    query_lines.append(line)
                    if line.strip().endswith(";"):
                        break
                query = " ".join(query_lines).rstrip(";")
                try:
                    results = interface.run_query(query)
                    print(f"\n📊 Results ({len(results)}):")
                    for r in results[:20]:
                        print(f"  {r}")
                except Exception as e:
                    print(f"❌ Query error: {e}")
            elif cmd:
                print(f"Unknown command: {cmd}")
            print()
        except KeyboardInterrupt:
            print("\n")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point for CLI."""
    from dotenv import load_dotenv
    load_dotenv()
    
    uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    
    if not password:
        print("❌ NEO4J_PASSWORD not set. Please set it in .env file.")
        sys.exit(1)
    
    interface = GraphQueryInterface(uri, user, password)
    
    try:
        if len(sys.argv) > 1:
            # Run specific command
            cmd = sys.argv[1].lower()
            if cmd == "stats":
                stats = interface.get_graph_statistics()
                print("📈 Graph Statistics:")
                for key, value in stats.items():
                    print(f"  {key}: {value}")
            elif cmd == "test":
                # Run validation query
                print("🧪 Running validation query...")
                results = interface.get_policies_with_provenance(5)
                if results:
                    print("✅ Graph is queryable. Sample results:")
                    for r in results:
                        print(f"  - {r}")
                else:
                    print("⚠️ No results found. Graph may be empty.")
            else:
                print(f"Unknown command: {cmd}")
                print("Usage: python -m src.query_interface [stats|test]")
        else:
            # Interactive mode
            interactive_mode(interface)
    finally:
        interface.close()


if __name__ == "__main__":
    main()
