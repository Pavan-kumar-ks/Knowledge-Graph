# import re

# POLICY_KEYWORDS = [
#     "tariff policy",
#     "foreign policy",
#     "public policy",
#     "energy policy",
# ]

# INSTITUTIONS = [
#     "ministry of power",
#     "ministry of external affairs",
#     "niti aayog",
#     "central government",
#     "state government",
#     "government of india",
#     "cerc",
#     "serc",
#     "parliament",
# ]

# SECTORS = [
#     "energy",
#     "electricity",
#     "governance",
#     "education",
#     "health",
#     "agriculture",
#     "infrastructure",
#     "transport",
# ]

# STRATEGIES = [
#     "new india",
#     "strategy for new india",
# ]

# COUNTRIES = [
#     "india",
#     "china",
#     "usa",
#     "russia",
#     "pakistan",
#     "bangladesh",
#     "nepal",
#     "bhutan",
#     "sri lanka",
# ]


# def find_matches(text, word_list):
#     found = set()
#     text_lower = text.lower()

#     for word in word_list:
#         if word in text_lower:
#             found.add(word.title())

#     return list(found)


# def extract_entities(text):
#     entities = {
#         "policies": find_matches(text, POLICY_KEYWORDS),
#         "institutions": find_matches(text, INSTITUTIONS),
#         "sectors": find_matches(text, SECTORS),
#         "strategies": find_matches(text, STRATEGIES),
#         "countries": find_matches(text, COUNTRIES),
#     }

#     return entities


# # For testing
# if __name__ == "__main__":
#     sample_text = """
#     The Tariff Policy 2016 was issued by the Ministry of Power under the Government of India.
#     It focuses on the electricity and energy sector and aligns with Strategy for New India.
#     """

#     print(extract_entities(sample_text))
import json
import os
import re

# -----------------------------
# Entity patterns (regex)
# -----------------------------

ENTITY_PATTERNS = {
    "policies": [
        r"tariff\s+policy",
        r"foreign\s+policy",
        r"public\s+policy",
    ],

    "institutions": [
        r"ministry\s+of\s+power",
        r"ministry\s+of\s+external\s+affairs",
        r"niti\s+aayog",
        r"government\s+of\s+india",
        r"central\s+government",
        r"parliament",
        r"cerc",
        r"serc",
    ],

    "sectors": [
        r"energy",
        r"electricity",
        r"governance",
        r"education",
        r"health",
        r"agriculture",
        r"infrastructure",
    ],

    "strategies": [
        r"new\s+india",
        r"strategy\s+for\s+new\s+india",
    ],

    "countries": [
        r"india",
        r"china",
        r"united\s+states|usa",
        r"russia",
        r"pakistan",
        r"bangladesh",
        r"nepal",
        r"bhutan",
        r"sri\s+lanka",
    ]
}

# -----------------------------
# Text normalization
# -----------------------------

def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)  # remove punctuation
    text = re.sub(r"\s+", " ", text)          # normalize spaces
    return text

# -----------------------------
# Entity extraction
# -----------------------------

def extract_entities_from_text(text):
    normalized = normalize(text)

    entities = {
        "policies": [],
        "institutions": [],
        "sectors": [],
        "strategies": [],
        "countries": []
    }

    for entity_type, patterns in ENTITY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, normalized):
                label = pattern.replace("\\s+", " ").replace("|", "/").title()
                entities[entity_type].append(label)

    return entities

# -----------------------------
# Process all chunks
# -----------------------------

# def process_chunks(input_path, output_path):
#     with open(input_path, "r", encoding="utf-8") as f:
#         chunks = json.load(f)

#     print(f"Loaded {len(chunks)} chunks")

#     extracted_count = 0

#     for chunk in chunks:
#         entities = extract_entities_from_text(chunk["text"])
#         chunk["entities"] = entities

#         if any(len(v) > 0 for v in entities.values()):
#             extracted_count += 1

#     with open(output_path, "w", encoding="utf-8") as f:
#         json.dump(chunks, f, indent=2, ensure_ascii=False)

#     print(f"Chunks with at least 1 entity: {extracted_count}")
#     print(f"Saved to {output_path}")
def process_chunks(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Loaded {len(chunks)} chunks")

    extracted_count = 0

    unique_entities = {
        "policies": set(),
        "institutions": set(),
        "sectors": set(),
        "strategies": set(),
        "countries": set()
    }

    total_mentions = 0

    for chunk in chunks:
        entities = extract_entities_from_text(chunk["text"])
        chunk["entities"] = entities

        if any(len(v) > 0 for v in entities.values()):
            extracted_count += 1

        for etype, entity_list in entities.items():
            total_mentions += len(entity_list)
            for entity in entity_list:
                unique_entities[etype].add(entity)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print(f"\nChunks with at least 1 entity: {extracted_count}")
    print(f"Total entity mentions: {total_mentions}")

    print("\nUnique entity counts:")
    total_unique = 0
    for etype, values in unique_entities.items():
        print(f"{etype}: {len(values)}")
        total_unique += len(values)

    print(f"\nTotal unique entities: {total_unique}")
    print(f"Saved to {output_path}")


# -----------------------------
# Run
# -----------------------------

if __name__ == "__main__":
    BASE_DIR = "C:\\Users\\91779\\Desktop\\InternShip_Rooman\\policy-knowledge-graph"

    input_file = os.path.join(BASE_DIR, "chunks.json")
    output_file = os.path.join(BASE_DIR, "chunks_with_entities.json")

    process_chunks(input_file, output_file)



