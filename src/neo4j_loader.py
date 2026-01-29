"""
Neo4j graph loading module.
Loads chunks and entities into Neo4j database.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from neo4j import Driver, GraphDatabase, Session

logger = logging.getLogger(__name__)


class Neo4jConnection:
    """Manages Neo4j connection and lifecycle."""
    
    def __init__(self, uri: str, user: str, password: str, timeout: int = 30):
        """
        Initialize Neo4j connection.
        
        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
            timeout: Connection timeout in seconds
        """
        self.uri = uri
        self.user = user
        self.driver: Optional[Driver] = None
        self.timeout = timeout
        
        try:
            self.driver = GraphDatabase.driver(
                uri,
                auth=(user, password),
                connection_timeout=timeout
            )
            logger.info(f"Neo4j connection initialized: {uri}")
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j connection: {e}")
            raise
    
    def verify_connection(self) -> bool:
        """
        Verify Neo4j connection is working.
        
        Returns:
            True if connection is valid
        """
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("✅ Neo4j connection verified")
            return True
        except Exception as e:
            logger.error(f"❌ Neo4j connection failed: {e}")
            return False
    
    def close(self) -> None:
        """Close database connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")


class GraphBuilder:
    """Builds and manages graph structure."""
    
    def __init__(self, driver: Driver):
        """
        Initialize graph builder.
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
    
    def create_constraints(self, labels: List[str]) -> None:
        """
        Create uniqueness constraints for labels.
        
        Args:
            labels: List of label names
        """
        with self.driver.session() as session:
            for label in labels:
                property_name = "id" if label == "Chunk" else "name"
                try:
                    session.run(
                        f"CREATE CONSTRAINT IF NOT EXISTS "
                        f"FOR (n:{label}) REQUIRE n.{property_name} IS UNIQUE"
                    )
                    logger.debug(f"Constraint created: {label}.{property_name}")
                except Exception as e:
                    logger.warning(f"Could not create constraint for {label}: {e}")
    
    def merge_node(self, session: Session, label: str, name: str) -> None:
        """
        Merge a node into the graph.
        
        Args:
            session: Neo4j session
            label: Node label
            name: Node name property
        """
        session.run(
            f"MERGE (n:{label} {{name: $name}})",
            name=name
        )
    
    def merge_chunk(self, session: Session, chunk_id: str, text: str) -> None:
        """
        Merge a chunk node into the graph.
        
        Args:
            session: Neo4j session
            chunk_id: Unique chunk identifier
            text: Chunk text content
        """
        session.run(
            "MERGE (c:Chunk {id: $id}) SET c.text = $text",
            id=chunk_id,
            text=text
        )
    
    def create_relationship(
        self,
        session: Session,
        from_label: str,
        from_key: str,
        from_val: str,
        to_label: str,
        to_key: str,
        to_val: str,
        rel_type: str
    ) -> None:
        """
        Create a relationship between two nodes.
        
        Args:
            session: Neo4j session
            from_label: Source node label
            from_key: Source node property key
            from_val: Source node property value
            to_label: Target node label
            to_key: Target node property key
            to_val: Target node property value
            rel_type: Relationship type
        """
        session.run(
            f"""
            MATCH (a:{from_label} {{{from_key}: $from_val}})
            MATCH (b:{to_label} {{{to_key}: $to_val}})
            MERGE (a)-[:{rel_type}]->(b)
            """,
            from_val=from_val,
            to_val=to_val
        )


class ChunkLoader:
    """Loads chunks and entities into the graph."""
    
    ENTITY_LABELS = {
        "policies": "Policy",
        "institutions": "Institution",
        "sectors": "Sector",
        "countries": "Country",
        "strategies": "Strategy"
    }
    
    def __init__(self, driver: Driver):
        """
        Initialize chunk loader.
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
        self.builder = GraphBuilder(driver)
    
    def load_chunk(self, session: Session, chunk: Dict[str, Any]) -> None:
        """
        Load a single chunk with all relationships and entities.
        
        Args:
            session: Neo4j session
            chunk: Chunk dictionary
        """
        doc = chunk["document"]
        section = chunk["section"]
        chunk_id = chunk["chunk_id"]
        chunk_uid = f"{doc}_{section}_{chunk_id}"
        
        # Create document, section, and chunk nodes
        self.builder.merge_node(session, "Document", doc)
        self.builder.merge_node(session, "Section", section)
        self.builder.merge_chunk(session, chunk_uid, chunk["text"])
        
        # Create structural relationships
        self.builder.create_relationship(
            session,
            "Document", "name", doc,
            "Section", "name", section,
            "HAS_SECTION"
        )
        
        self.builder.create_relationship(
            session,
            "Section", "name", section,
            "Chunk", "id", chunk_uid,
            "HAS_CHUNK"
        )
        
        # Create entity nodes and relationships
        entities = chunk.get("entities", [])
        for entity in entities:
            entity_type = entity.get("type")
            # Map to schema label if possible, else use type as label
            label = self.ENTITY_LABELS.get(entity_type.lower() + 's', entity_type) if entity_type else None
            # Use 'name' or 'title' or 'text' as the entity name
            entity_name = entity.get("name") or entity.get("title") or entity.get("text")
            if not label or not entity_name:
                continue
            self.builder.merge_node(session, label, entity_name)
            self.builder.create_relationship(
                session,
                "Chunk", "id", chunk_uid,
                label, "name", entity_name,
                "MENTIONS"
            )


def load_graph(
    uri: str,
    user: str,
    password: str,
    chunks: List[Dict[str, Any]],
    chunk_size: int = 100
) -> Dict[str, int]:
    """
    Load chunks and entities into Neo4j graph.
    
    Args:
        uri: Neo4j connection URI
        user: Neo4j username
        password: Neo4j password
        chunks: List of chunk dictionaries
        chunk_size: Number of chunks to process before progress update
        
    Returns:
        Statistics dictionary
    """
    # Initialize connection
    conn = Neo4jConnection(uri, user, password)
    
    if not conn.verify_connection():
        raise RuntimeError("Failed to connect to Neo4j")
    
    # Create constraints
    builder = GraphBuilder(conn.driver)
    labels = ["Document", "Section", "Chunk", "Policy", "Institution", "Sector", "Country", "Strategy"]
    builder.create_constraints(labels)
    
    # Load chunks
    loader = ChunkLoader(conn.driver)
    
    logger.info(f"Loading {len(chunks)} chunks into Neo4j...")
    
    with conn.driver.session() as session:
        for idx, chunk in enumerate(chunks):
            try:
                loader.load_chunk(session, chunk)
            except Exception as e:
                logger.error(f"Failed to load chunk {idx}: {e}")
                continue
            
            if (idx + 1) % chunk_size == 0:
                logger.info(f"  Processed {idx + 1}/{len(chunks)} chunks...")
    
    logger.info("✅ Graph loading complete")
    conn.close()
    
    return {
        "total_chunks": len(chunks),
        "status": "success"
    }


# Legacy function for backward compatibility
def load_chunks_legacy(data_path: str = None):
    """
    Load chunks from JSON file (legacy function).
    
    Args:
        data_path: Path to chunks JSON file
        
    Returns:
        List of chunks
    """
    if data_path is None:
        from config import config
        data_path = str(config.CHUNKS_ENTITIES_FILE)
    
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    from config import config
    
    try:
        config.validate()
        
        logger.info(f"Loading data from {config.CHUNKS_ENTITIES_FILE}")
        chunks = load_chunks_legacy(str(config.CHUNKS_ENTITIES_FILE))
        
        load_graph(
            config.NEO4J_URI,
            config.NEO4J_USER,
            config.NEO4J_PASSWORD,
            chunks
        )
    except Exception as e:
        logger.error(f"Failed to load graph: {e}", exc_info=True)
