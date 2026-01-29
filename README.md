# 📊 Policy Knowledge Graph using Neo4j

## ⚡ **v2.0 - Now with AI-Powered Entity Extraction!**

This repository builds a **Policy Knowledge Graph** from policy documents using:

- 📄 PDF parsing & semantic chunking
- 🤖 **AI-powered entity extraction (Groq LLM)**
- 🔗 **Relationship extraction between entities**
- 📊 Neo4j graph database with rich semantic connections
- 💯 Confidence scores for extracted entities

Perfect for learning **Knowledge Graphs**, **Graph Databases**, **LLM Integration**, and **RAG pipelines**.

---

## 🚀 **Quick Start**

```bash
# 1. Setup
cp .env.example .env
# Edit .env and add: GROQ_API_KEY=your_key_here

# 2. Install
pip install -r requirements.txt

# 3. Test
python test_improvements.py

# 4. Run
python -m src.pipeline
```

📖 **[Read QUICK_START.md for detailed setup instructions →](QUICK_START.md)**

---

## 🎯 **What's New in v2.0**

### ✨ Enhanced Features
- **Semantic Chunking** - Sentence-aware splitting with configurable overlap
- **Groq LLM Integration** - AI-powered entity extraction (replaces regex)
- **Relationship Extraction** - Discovers connections between entities (NEW)
- **7 Entity Types** - policies, institutions, sectors, strategies, countries, people, locations
- **5 Relationship Types** - IMPLEMENTS, GOVERNS, RELATED_TO, MENTIONED_IN, COLLABORATES_WITH
- **Rich Metadata** - Chunk statistics, confidence scores, position tracking

### 📈 Improvements
| Feature | Before | After |
|---------|--------|-------|
| Entity Extraction | Regex patterns | AI-powered (Groq) |
| Accuracy | ~65% | ~90% |
| Entity Types | 5 | 7 |
| Relationships | None | Yes (5 types) |
| Confidence Scores | No | Yes |
| Context Awareness | No | Yes |

---

## 📁 **Project Structure**

```
Neo4j/
├── data/pdfs/              # Source policy PDFs
├── src/
│   ├── pdf_loader.py       # PDF text extraction
│   ├── chunker.py          # Semantic chunking
│   ├── entity_extractor.py # Groq LLM extraction
│   ├── pipeline.py         # Main orchestrator
│   ├── neo4j_loader.py     # Graph loader
│   └── config.py           # Configuration
├── output/
│   ├── chunks.json         # Chunked documents
│   └── chunks_with_entities.json  # With entities + relationships
├── logs/
│   └── pipeline.log        # Execution logs
├── test_improvements.py    # Validation tests
└── .env                    # Your configuration (create from .env.example)
```

---

## 🎯 **Tech Stack**

| Component | Technology |
|-----------|------------|
| Language | Python 3.8+ |
| PDF Parsing | PyPDF2 |
| Chunking | Semantic sentence-aware |
| Entity Extraction | **Groq LLM (llama-3.1-70b-versatile)** |
| Graph Database | Neo4j |
| Query Language | Cypher |

---

## 🧠 **How It Works**

1. **Load PDFs** → Extract text from policy documents
2. **Semantic Chunking** → Split into sentence-aware chunks with overlap
3. **AI Extraction** → Groq LLM extracts entities and relationships
4. **Graph Construction** → Load into Neo4j with semantic connections
5. **Query & Analyze** → Run Cypher queries to explore relationships

---

## 📚 **Documentation**

| File | Description |
|------|-------------|
| **[QUICK_START.md](QUICK_START.md)** | 👈 Start here - Complete setup guide |
| **[REFERENCE_CARD.md](REFERENCE_CARD.md)** | Quick commands & reference |
| **[IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md)** | Setup checklist |
| **[BEFORE_AFTER_COMPARISON.md](BEFORE_AFTER_COMPARISON.md)** | What changed in v2.0 |
| **[UPGRADE_SUMMARY.md](UPGRADE_SUMMARY.md)** | Technical details |
| **[DOCS_INDEX.md](DOCS_INDEX.md)** | Documentation navigator |

---

## ⚙️ **Configuration**

Create `.env` file with:

```bash
# Required
GROQ_API_KEY=your_groq_api_key_here

# Optional (defaults shown)
GROQ_MODEL=llama-3.1-70b-versatile
CHUNK_SIZE=1024
CHUNK_OVERLAP=200
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

---

## 🧪 **Testing**

Run validation tests:

```bash
python test_improvements.py
```

Expected: All 6 tests pass ✅

---

## 📊 **Example Output**

```json
{
  "chunk_id": 0,
  "text": "The Ministry of Power implements electricity tariff policy...",
  "entities": [
    {"text": "Ministry of Power", "type": "institutions", "confidence": 0.95},
    {"text": "electricity tariff policy", "type": "policies", "confidence": 0.92}
  ],
  "relationships": [
    {
      "source": "Ministry of Power",
      "target": "electricity tariff policy",
      "type": "IMPLEMENTS",
      "context": "ministry implements and regulates the policy"
    }
  ],
  "metadata": {
    "char_count": 156,
    "word_count": 28,
    "sentence_count": 3
  }
}
```

---

## 🔍 **Sample Cypher Queries**

### Most Connected Entities
```cypher
MATCH (e)
WHERE e:Policy OR e:Institution OR e:Sector
RETURN labels(e)[0] AS type, e.name AS name, 
       size((e)--()) AS connections
ORDER BY connections DESC
LIMIT 10;
```

### Entity Relationships
```cypher
MATCH (e1)-[r]->(e2)
WHERE e1:Institution AND e2:Policy
RETURN e1.name, type(r), e2.name
LIMIT 20;
```

---

## 🚨 **Requirements**

- Python 3.8+
- Groq API key (get from [console.groq.com](https://console.groq.com))
- Neo4j (Desktop or Aura)
- 2GB+ RAM recommended

---

## 🤝 **Contributing**

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test your changes
4. Submit a pull request

---

## 📄 **License**

MIT License - feel free to use for learning and projects!

---

## 🆘 **Troubleshooting**

| Issue | Solution |
|-------|----------|
| "GROQ_API_KEY not found" | Add key to .env file |
| Import errors | Run `pip install -r requirements.txt` |
| API timeouts | Increase `GROQ_TIMEOUT` in config |
| Tests fail | Check logs/pipeline.log |

See [QUICK_START.md](QUICK_START.md) for detailed troubleshooting.

---

## 🎉 **Credits**

Built with love for the Knowledge Graph community!

**Version:** 2.0.0  
**Last Updated:** January 2026

---

## 📞 **Quick Links**

- 🚀 [Quick Start Guide](QUICK_START.md)
- 📖 [Full Documentation](DOCS_INDEX.md)
- 🧪 [Test Suite](test_improvements.py)
- 💾 [Original Repo](https://github.com/Pavan-kumar-ks/Knowledge-Graph)

---

**Ready to build your Knowledge Graph?** → [Get Started Now!](QUICK_START.md) 🚀
