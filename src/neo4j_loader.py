"""
Neo4j graph loading module.
Loads chunks and entities into Neo4j database.
"""
# pyright: reportArgumentType=false

import logging
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
            with self.driver.session() as session:  # type: ignore
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
    
    def create_constraints(self):
        """
        Create uniqueness constraints and indexes for canonical schema.
        """
        constraints = [
            ("Country", "country_id"),
            ("TechDomain", "domain_id"),
            ("Equipment", "equipment_id"),
            ("Policy", "policy_id"),
            ("Authority", "authority_id"),
            ("Requirement", "requirement_id"),
            ("Document", "document_id"),
            ("Chunk", "id"),
        ]
        indexes = [
            ("Policy", "name"),
        ]
        with self.driver.session() as session:
            for label, prop in constraints:
                try:
                    session.run(
                        f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                    )
                    logger.debug(f"Constraint created: {label}.{prop}")
                except Exception as e:
                    logger.warning(f"Could not create constraint for {label}: {e}")
            for label, prop in indexes:
                try:
                    session.run(
                        f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.{prop})"
                    )
                    logger.debug(f"Index created: {label}.{prop}")
                except Exception as e:
                    logger.warning(f"Could not create index for {label}: {e}")
    
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
        
        # Create canonical entity nodes
        entities = chunk.get("entities", [])
        for entity in entities:
            entity_type = entity.get("type")
            if not entity_type:
                continue
            # Canonical label and ID property
            label = entity_type
            id_key = None
            if label == "Country":
                id_key = "country_id"
            elif label == "TechDomain":
                id_key = "domain_id"
            elif label == "Equipment":
                id_key = "equipment_id"
            elif label == "Policy":
                id_key = "policy_id"
            elif label == "Authority":
                id_key = "authority_id"
            elif label == "Requirement":
                id_key = "requirement_id"
            elif label == "Document":
                id_key = "document_id"
            if not id_key or id_key not in entity:
                continue
            # Merge node with all properties
            props = {k: v for k, v in entity.items() if k != "type"}
            prop_str = ", ".join([f"{k}: ${k}" for k in props])
            session.run(
                f"MERGE (n:{label} {{{id_key}: ${id_key}}}) SET n += {{{prop_str}}}",
                **props
            )
            # Optionally, link chunk to entity for traceability
            self.builder.create_relationship(
                session,
                "Chunk", "id", chunk_uid,
                label, id_key, entity[id_key],
                "MENTIONS"
            )

        # Create relationships (edges) with metadata
        relationships = chunk.get("relationships", [])
        for rel in relationships:
            src_id = rel.get("source")
            tgt_id = rel.get("target")
            rel_type = rel.get("type")
            # Find source/target types for label lookup
            src_type = None
            tgt_type = None
            for e in entities:
                if src_id in e.values():
                    src_type = e["type"]
                if tgt_id in e.values():
                    tgt_type = e["type"]
            if not src_type or not tgt_type or not rel_type:
                continue
            # Relationship metadata
            meta = {k: v for k, v in rel.items() if k not in ("source", "target", "type")}
            meta_str = ", ".join([f"{k}: ${k}" for k in meta])
            session.run(
                f"MATCH (a:{src_type} {{{src_type.lower()}_id: $src_id}}) "
                f"MATCH (b:{tgt_type} {{{tgt_type.lower()}_id: $tgt_id}}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                + (f"SET r += {{{meta_str}}}" if meta else ""),
                src_id=src_id,
                tgt_id=tgt_id,
                **meta
            )


def load_graph(
    uri: str,
    user: str,
    password: str,
    chunks: List[Dict[str, Any]],
    chunk_size: int = 100,
    batch_size: int = 50
) -> Dict[str, Any]:
    """
    Load chunks and entities into Neo4j graph with batch processing.
    
    Args:
        uri: Neo4j connection URI
        user: Neo4j username
        password: Neo4j password
        chunks: List of chunk dictionaries
        chunk_size: Number of chunks to process before progress update
        batch_size: Number of chunks to process in a single transaction (for performance)
        
    Returns:
        Statistics dictionary
    """
    import time
    start_time = time.time()
    
    # Initialize connection
    conn = Neo4jConnection(uri, user, password)
    
    if not conn.verify_connection():
        raise RuntimeError("Failed to connect to Neo4j")
    
    # Create constraints
    builder = GraphBuilder(conn.driver)
    labels = ["Document", "Section", "Chunk", "Policy", "Institution", "Sector", "Country", "Strategy"]
    builder.create_constraints()
    
    # Load chunks with batch processing
    loader = ChunkLoader(conn.driver)
    
    logger.info(f"Loading {len(chunks)} chunks into Neo4j (batch size: {batch_size})...")
    
    loaded_count = 0
    error_count = 0
    
    # Process in batches for better performance
    for batch_start in range(0, len(chunks), batch_size):
        batch_end = min(batch_start + batch_size, len(chunks))
        batch = chunks[batch_start:batch_end]
        
        # Use a single transaction per batch
        with conn.driver.session() as session:  # type: ignore
            with session.begin_transaction() as tx:
                for chunk in batch:
                    try:
                        loader.load_chunk(tx, chunk)
                        loaded_count += 1
                    except Exception as e:
                        logger.error(f"Failed to load chunk {batch_start}: {e}")
                        error_count += 1
                        continue
                tx.commit()
        
        if batch_end % chunk_size == 0 or batch_end == len(chunks):
            logger.info(f"  Processed {batch_end}/{len(chunks)} chunks...")
    
    elapsed_time = time.time() - start_time
    
    logger.info("✅ Graph loading complete")
    logger.info(f"   Loaded: {loaded_count}, Errors: {error_count}, Time: {elapsed_time:.2f}s")
    conn.close()
    
    return {
        "total_chunks": len(chunks),
        "loaded_chunks": loaded_count,
        "error_count": error_count,
        "elapsed_seconds": round(elapsed_time, 2),
        "status": "success"
    }
