# Test script for entity extractor and RAG system

from src.entity_extractor import spacy_extract_entities

print("=" * 60)
print("Testing Entity Extractor Improvements")
print("=" * 60)

# Test 1: Should NOT label "Chand" as a country
test1 = "Chand Kumar is working on AI policy in India."
print(f"\nTest 1: {test1}")
entities = spacy_extract_entities(test1)
for e in entities:
    name = e.get("name", e.get("description", "?"))
    print(f"  - {e['type']}: {name}")
    if e["type"] == "Country" and "chand" in name.lower():
        print("    ❌ ERROR: 'Chand' should not be a Country!")

# Test 2: AI and Artificial Intelligence should be the SAME node
test2 = "AI and Artificial Intelligence are used in medical devices."
print(f"\nTest 2: {test2}")
entities = spacy_extract_entities(test2)
tech_domains = [e for e in entities if e["type"] == "TechDomain"]
print(f"  TechDomain entities: {len(tech_domains)}")
for e in tech_domains:
    print(f"    - {e.get('name')} (id: {e.get('domain_id')})")
if len(tech_domains) == 1:
    print("  ✓ Correctly normalized AI = Artificial Intelligence")
else:
    print("  ❌ ERROR: Should have only 1 TechDomain entity!")

# Test 3: Valid country extraction
test3 = "Medical devices in Germany and India require registration."
print(f"\nTest 3: {test3}")
entities = spacy_extract_entities(test3)
countries = [e for e in entities if e["type"] == "Country"]
print(f"  Countries found: {[e['name'] for e in countries]}")
print(f"  ISO codes: {[e.get('iso_code') for e in countries]}")

print("\n" + "=" * 60)
print("Entity Extractor Tests Complete")
print("=" * 60)
