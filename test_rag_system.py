# Test script for RAG system

from src.config import config
from src.rag_system import RAGSystem, format_response

print("=" * 60)
print("Testing RAG System")
print("=" * 60)

# Initialize RAG
print("\nInitializing RAG system...")
rag = RAGSystem(
    neo4j_uri=config.NEO4J_URI,
    neo4j_user=config.NEO4J_USER,
    neo4j_password=config.NEO4J_PASSWORD,
)

# Test queries
test_queries = [
    "What are the requirements for MRI scanners in India?",
    "Who regulates medical devices in the US?",
]

for query in test_queries:
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print("=" * 60)
    
    response = rag.query(query, verbose=False)
    print(format_response(response))

rag.close()
print("\n✅ RAG System tests complete!")
