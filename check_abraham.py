import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'), 
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

with driver.session() as session:
    print("=== Policies containing 'abraham' ===")
    results = session.run("MATCH (p:Policy) WHERE toLower(p.name) CONTAINS 'abraham' RETURN p.name as name")
    for r in results:
        print(f"  - {r['name']}")
    
    print("\n=== Policies containing 'accord' ===")
    results = session.run("MATCH (p:Policy) WHERE toLower(p.name) CONTAINS 'accord' RETURN p.name as name")
    for r in results:
        print(f"  - {r['name']}")
    
    print("\n=== Chunks containing 'Abraham Accords' ===")
    results = session.run("MATCH (c:Chunk) WHERE toLower(c.text) CONTAINS 'abraham accords' RETURN c.text as text LIMIT 3")
    for r in results:
        print(f"  - {r['text'][:200]}...")

driver.close()
