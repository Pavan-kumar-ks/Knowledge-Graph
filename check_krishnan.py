import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'), 
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

with driver.session() as session:
    # Try different variations
    searches = ['s.krishnan', 's. krishnan', 'krishnan', 's krishnan']
    
    for search in searches:
        results = list(session.run(f"MATCH (c:Chunk) WHERE toLower(c.text) CONTAINS '{search}' RETURN c.text as text LIMIT 2"))
        print(f"=== '{search}' found: {len(results)} chunks ===")
        for r in results:
            text = r['text']
            # Find context around krishnan
            idx = text.lower().find('krishnan')
            if idx >= 0:
                start = max(0, idx - 50)
                end = min(len(text), idx + 100)
                print(f"  ...{text[start:end]}...")
        print()

driver.close()
