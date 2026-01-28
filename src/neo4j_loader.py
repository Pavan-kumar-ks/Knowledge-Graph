import json
from neo4j import GraphDatabase

# -------------------
# CONFIG
# -------------------
NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Pavanks123"

DATA_PATH = "C:\\Users\\91779\\Desktop\\InternShip_Rooman\\policy-knowledge-graph\\chunks_with_entities.json"

# -------------------
# Neo4j connection
# -------------------
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# -------------------
# DB helpers
# -------------------
def merge_node(tx, label, name):
    tx.run(f"""
        MERGE (n:{label} {{name: $name}})
    """, name=name)


def merge_chunk(tx, chunk_id, text):
    tx.run("""
        MERGE (c:Chunk {id: $id})
        SET c.text = $text
    """, id=chunk_id, text=text)


def create_relationship(tx, from_label, from_key, from_val,
                              to_label, to_key, to_val, rel):
    tx.run(f"""
        MATCH (a:{from_label} {{{from_key}: $from_val}})
        MATCH (b:{to_label} {{{to_key}: $to_val}})
        MERGE (a)-[:{rel}]->(b)
    """, from_val=from_val, to_val=to_val)

# -------------------
# Load data
# -------------------
def load_chunks():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# -------------------
# Main loader
# -------------------
def main():
    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks")

    with driver.session() as session:
        for idx, chunk in enumerate(chunks):

            doc = chunk["document"]
            section = chunk["section"]
            chunk_uid = f"{doc}_{section}_{chunk['chunk_id']}"

            # ---- Nodes ----
            session.execute_write(merge_node, "Document", doc)
            session.execute_write(merge_node, "Section", section)
            session.execute_write(merge_chunk, chunk_uid, chunk["text"])

            # ---- Relationships ----
            session.execute_write(create_relationship,
                "Document", "name", doc,
                "Section", "name", section,
                "HAS_SECTION"
            )

            session.execute_write(create_relationship,
                "Section", "name", section,
                "Chunk", "id", chunk_uid,
                "HAS_CHUNK"
            )

            # ---- Entity nodes ----
            entities = chunk["entities"]

            for policy in entities["policies"]:
                session.execute_write(merge_node, "Policy", policy)
                session.execute_write(create_relationship,
                    "Chunk", "id", chunk_uid,
                    "Policy", "name", policy,
                    "MENTIONS"
                )

            for inst in entities["institutions"]:
                session.execute_write(merge_node, "Institution", inst)
                session.execute_write(create_relationship,
                    "Chunk", "id", chunk_uid,
                    "Institution", "name", inst,
                    "MENTIONS"
                )

            for sector in entities["sectors"]:
                session.execute_write(merge_node, "Sector", sector)
                session.execute_write(create_relationship,
                    "Chunk", "id", chunk_uid,
                    "Sector", "name", sector,
                    "MENTIONS"
                )

            for country in entities["countries"]:
                session.execute_write(merge_node, "Country", country)
                session.execute_write(create_relationship,
                    "Chunk", "id", chunk_uid,
                    "Country", "name", country,
                    "MENTIONS"
                )

            for strat in entities["strategies"]:
                session.execute_write(merge_node, "Strategy", strat)
                session.execute_write(create_relationship,
                    "Chunk", "id", chunk_uid,
                    "Strategy", "name", strat,
                    "MENTIONS"
                )

            if idx % 200 == 0:
                print(f"Processed {idx} chunks...")

    print("Graph loading complete ✅")
    driver.close()


if __name__ == "__main__":
    main()
