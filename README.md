# 📊 Policy Knowledge Graph using Neo4j

This repository contains a complete, beginner-friendly project that builds a **Policy Knowledge Graph** from multiple policy documents using:

- PDF parsing & chunking
- Rule-based entity extraction (regex)
- Graph modeling using **Neo4j**
- Meaningful semantic relationships

This is ideal for learning **Knowledge Graphs**, **Graph Databases**, and foundational **RAG pipelines**.

---

## 🧠 Project Overview

📌 **Goal**  
Build a structured knowledge graph from unstructured policy documents to extract relationships between policies, institutions, sectors, strategies, and countries.

📌 **Inputs**  
PDF documents:

- Tariff Policy 2016
- Public Policy & Governance notes
- India’s Foreign Policy text
- Strategy for New India

📌 **Outputs**  
- Hierarchical document graph
- Chunk nodes connected to entities
- Neo4j graph with connected semantic concepts

---

## 🧱 Features

✔ PDF loader & text extraction  
✔ Section-aware chunking  
✔ Regex entity extraction  
✔ Neo4j graph construction  
✔ Visualization queries  
✔ Demo Cypher analytics

---

## 🎯 Tech Stack

| Layer | Technology |
|-------|------------|
| Text parsing | Python (PyPDF2) |
| Chunking | Python |
| Entity Extraction | Regex |
| Graph Database | Neo4j |
| Query Language | Cypher |

---

```bash
📦Knowledge-Graph
├── data/
│ └── pdfs/ # source policy PDFs
├── src/
│ ├── pdf_loader.py # loads PDF text
│ ├── chunker.py # sections + chunking
│ ├── entity_extractor.py # regex entity extraction
│ ├── neo4j_loader.py # graph loader
│ └── query_graph.py # example queries
├── chunks.json # intermediate chunks
├── chunks_with_entities.json # chunks + entity labels
├── .gitignore
└── README.md

```
---

## 🚀 Installation

**1. Clone the repository**

```bash
git clone https://github.com/Pavan-kumar-ks/Knowledge-Graph.git
cd Knowledge-Graph


python -m venv venv
venv\Scripts\activate   # Windows
# or
source venv/bin/activate  # macOS/Linux


pip install -r requirements.txt
🧾 How to Run
1️⃣ Load PDFs
python src/pdf_loader.py


Output: raw text from PDFs.

2️⃣ Create Chunks
python src/chunker.py


Generates chunks.json.

3️⃣ Extract Entities
python src/entity_extractor.py


Generates chunks_with_entities.json.

4️⃣ Load into Neo4j

Make sure Neo4j is running (Desktop or Aura).
Update connection settings in neo4j_loader.py.

python src/neo4j_loader.py

5️⃣ Run Graph Queries

Open Neo4j Browser at:

http://localhost:7474


Try sample queries in src/query_graph.py.

📊 Example Queries
Most connected entities
MATCH (e)
WHERE e:Policy OR e:Institution OR e:Sector OR e:Country OR e:Strategy
RETURN labels(e)[0] AS type, e.name AS name, size((e)--()) AS connections
ORDER BY connections DESC
LIMIT 10;

Dense chunk → entity cluster
MATCH (c1:Chunk)-[:MENTIONS]->(e)<-[:MENTIONS]-(c2:Chunk)
WHERE c1 <> c2
WITH e, collect(DISTINCT c1)[0..6] AS chunks
UNWIND chunks AS c
MATCH (c)-[r:MENTIONS]->(e)
RETURN c, r, e
LIMIT 60;


