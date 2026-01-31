import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'), 
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

with driver.session() as session:
    print("=== Chunks containing 'article 10' ===")
    results = session.run("MATCH (c:Chunk) WHERE toLower(c.text) CONTAINS 'article 10' RETURN c.text as text LIMIT 5")
    count = 0
    for r in results:
        count += 1
        print(f"\n--- Chunk {count} ---")
        print(r['text'][:700] + "...")
    print(f"\nTotal chunks with 'article 10': {count}")

driver.close()
