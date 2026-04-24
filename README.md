# 🧠 Knowledge Engine

> A self-improving GraphRAG knowledge base that ingests your AI portfolio docs and gets smarter every time you use it.

## 🫏 The Donkey Analogy

The LLM is the donkey — it carries your questions to answers.
The graph + vector store is the road — if the road is bad (missing docs, broken connections), even the smartest LLM can't deliver.
**This project builds the road.** The more docs you add, the better the road becomes.

---

## What It Does

1. **Ingests** all markdown docs across your 6 AI portfolio repos
2. **Extracts** topics and relationships → builds a knowledge graph (Neo4j / DynamoDB / Cosmos DB)
3. **Embeds** document chunks → stores in vector DB (ChromaDB / DynamoDB / Azure AI Search)
4. **Answers** questions using GraphRAG: vector search + graph traversal + LLM
5. **Generates** a wiki that auto-improves from your chat history
6. **Learns** from feedback — 👍 saves verified answers, 👎 adds to eval set

---

## Architecture

```
Your Docs (.md files across 6 repos)
         ↓
    [Ingestion Pipeline]
    Scanner → Chunker → Embedder
                      → Graph Extractor (LLM)
         ↓                    ↓
   [Vector Store]        [Graph Store]
   ChromaDB (local)      Neo4j (local)
   DynamoDB (AWS)        DynamoDB adjacency (AWS)
   Azure AI Search       Cosmos DB NoSQL (Azure)
         ↓                    ↓
              [Chat Engine]
         GraphRAG: vector search + graph traversal
                      ↓
                    [LLM]
           Ollama (local) / Bedrock (AWS) / Azure OpenAI
                      ↓
                [Response + 🫏 Donkey Analogy]
                      ↓
               [Feedback Loop]
         👍 → wiki page   👎 → eval set
```

---

## Quick Start (Local)

### Prerequisites
- Docker + Docker Compose
- Ollama running locally (`ollama pull llama3.2 && ollama pull nomic-embed-text`)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env: set SOURCE_REPOS_PATH to your ai-portfolio/repos directory

# 2. Start all services
docker compose up -d

# 3. Ingest docs (first time ~5-10 min)
curl -X POST http://localhost:8200/ingest/run

# 4. Open the UI
open http://localhost:8501

# 5. Or chat via API
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What is GraphRAG and how does it work?"}'
```

---

## Providers

| Feature | Local | AWS | Azure |
|---------|-------|-----|-------|
| LLM | Ollama (llama3.2) | Bedrock Claude Haiku | Azure OpenAI GPT-4o-mini |
| Embeddings | nomic-embed-text | Titan Embed v2 | text-embedding-3-small |
| Vector Store | ChromaDB | DynamoDB | Azure AI Search |
| Graph Store | Neo4j | DynamoDB adjacency | Cosmos DB NoSQL |
| Cost/run | €0 | ~€0.25-0.50 | ~€0.50-1.00 |

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check + store stats |
| POST | `/chat/` | Ask a question (GraphRAG answer) |
| POST | `/ingest/run` | Run full ingestion pipeline |
| GET | `/ingest/status` | Chunk + topic counts |
| POST | `/wiki/rebuild` | Regenerate all wiki pages |
| GET | `/wiki/topics` | List all topics |
| GET | `/wiki/graph` | Full graph (for D3.js visualization) |
| POST | `/feedback/` | Submit 👍 or 👎 feedback |

---

## The Self-Improving Loop

```
Ask question → get answer → give feedback
     ↓              ↓            ↓
   log Q         🫏 analogy    👍 → wiki
                               👎 → eval set
                                    ↓
                              next ingestion
                              uses eval cases
                              to verify fixes
```

---

## Repo Structure

```
knowledge-engine/
├── src/
│   ├── ingestion/      # scanner, chunker, graph_extractor
│   ├── vectorstore/    # chroma, dynamodb, azure_search
│   ├── graphstore/     # neo4j, dynamodb_graph, cosmos_graph
│   ├── llm/            # ollama, bedrock, azure_openai (donkey analogy baked in)
│   ├── chat/           # engine (GraphRAG), feedback
│   ├── wiki/           # generator, renderer
│   ├── evaluation/     # evaluator, golden_questions
│   ├── routes/         # FastAPI routers
│   └── main.py         # app factory
├── ui/
│   └── app.py          # Streamlit chat UI
├── wiki-output/        # generated wiki (auto-created)
├── infra/
│   ├── aws/            # Terraform: Bedrock, DynamoDB, S3
│   └── azure/          # Terraform: Azure OpenAI, Cosmos DB
├── tests/
├── docker-compose.yml  # Neo4j + ChromaDB + Ollama + API + UI
├── Dockerfile
└── pyproject.toml
```

---

## Skills This Demonstrates

| AI Engineer Skill | How |
|-------------------|-----|
| Evaluation + testing | Golden questions YAML, RAGAS metrics |
| Controlled iteration | Provider swap (local → AWS → Azure) without code change |
| Monitoring + observability | structlog, Prometheus metrics, latency tracking |
| Feedback loops | 👍/👎 → wiki improvement + eval set growth |
| CI/CD for AI | GitHub Actions: ingest on doc change, eval gate |
| Product integration | Streamlit UI, REST API, Docker, 3 cloud providers |

---

## Related Repos

- [`rag-chatbot`](../rag-chatbot/) — the original RAG system this ingests
- [`ai-gateway`](../ai-gateway/) — LLM routing layer (can proxy knowledge-engine LLM calls)
- [`ai-engineering-field-guide`](../ai-engineering-field-guide/) — docs this ingests
