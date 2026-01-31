import os
import re

from dotenv import load_dotenv

from src.rag_system import RAGSystem, format_response

load_dotenv()

rag = RAGSystem(os.getenv('NEO4J_URI'), os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))

queries = [
    'who is S.Krishnan',
    'Explain the Abraham Accords',
    'What is Article 10',
]

for query in queries:
    print(f'\n{"="*60}')
    print(f'🔍 Your question: {query}')
    print('='*60)
    print('\n⏳ Processing...')
    response = rag.query(query, verbose=False)
    
    # Check if it's a fallback
    is_fallback = "⚠️ **Note: This answer is based on general knowledge" in response.answer
    
    print(f'\n✅ Answer (first 300 chars): {response.answer[:300]}...')
    print(f'\n📊 Is fallback: {is_fallback}')
    print(f'📊 Facts Retrieved: {response.facts_retrieved}')
    print(f'📚 Sources: {response.sources[:2]}')

rag.close()
print('\n\n✅ All tests completed!')
