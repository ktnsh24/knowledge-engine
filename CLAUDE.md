# Knowledge Engine — Project Context

## Status: 🟡 In Progress — Core scaffold complete, not yet run

## What This Is

A self-improving GraphRAG knowledge base that:
1. Ingests all markdown docs from 6 AI portfolio repos
2. Builds a knowledge graph (topics + relationships)
3. Answers questions using vector search + graph traversal + LLM
4. Auto-generates a wiki that improves from feedback

## Tech Stack

| Layer | Local | AWS | Azure |
|-------|-------|-----|-------|
| LLM | Ollama (llama3.2) | Bedrock Haiku | Azure OpenAI GPT-4o-mini |
| Vector | ChromaDB | DynamoDB | Azure AI Search |
| Graph | Neo4j | DynamoDB adjacency | Cosmos DB NoSQL |
| Config | `.env` | `.env` | `.env` |

## Why GraphRAG (Not Just Vector Search)

Vector search answers "what chunks are relevant?" — semantic similarity only.
Graph traversal answers "what else is connected?" — topic relationships.
Combined = GraphRAG. Ask about "RAG" and automatically get "embeddings", "vector store", "retrieval" — 2 hops away in the graph.

## 🫏 Donkey Analogy — Always On

Baked into `src/llm/base.py` as `DONKEY_SYSTEM_PROMPT`.
Every LLM response MUST include a donkey analogy — not optional.
- LLM = the donkey (carries the load)
- Infrastructure = the road (broken road = donkey can't deliver)
- Data = the goods

## Files Created

```
src/
├── config.py              ✅ Pydantic settings, 3 providers
├── models.py              ✅ All Pydantic models
├── main.py                ✅ FastAPI factory + lifespan
├── ingestion/
│   ├── scanner.py         ✅ Scan repos, chunk markdown
│   └── graph_extractor.py ✅ LLM extracts topics + relations
├── vectorstore/
│   ├── base.py            ✅ Abstract interface
│   ├── chroma.py          ✅ Local ChromaDB
│   └── factory.py         ✅ Provider factory
├── graphstore/
│   ├── base.py            ✅ Abstract interface
│   ├── neo4j_store.py     ✅ Local Neo4j
│   ├── dynamodb_graph.py  ✅ AWS DynamoDB adjacency list
│   └── factory.py         ✅ Provider factory
├── llm/
│   ├── base.py            ✅ Abstract + DONKEY_SYSTEM_PROMPT
│   ├── ollama.py          ✅ Local Ollama
│   ├── bedrock.py         ✅ AWS Bedrock (Converse API)
│   ├── azure_openai.py    ✅ Azure OpenAI
│   └── factory.py         ✅ Provider factory
├── chat/
│   ├── engine.py          ✅ GraphRAG: vector + graph + LLM
│   └── feedback.py        ✅ 👍→wiki, 👎→eval set
├── wiki/
│   └── generator.py       ✅ Auto-generate wiki pages per topic
└── routes/
    ├── chat.py            ✅ POST /chat/
    ├── wiki.py            ✅ /wiki/*
    ├── ingest.py          ✅ /ingest/*
    ├── health.py          ✅ GET /health
    └── feedback.py        ✅ POST /feedback/

docker-compose.yml         ✅ Neo4j + ChromaDB + Ollama + API + UI
Dockerfile                 ✅
README.md                  ✅

TODO:
├── src/vectorstore/dynamodb.py      ⬜ AWS vector store (embeddings in DynamoDB)
├── src/vectorstore/azure_search.py  ⬜ Azure AI Search
├── src/graphstore/cosmos_graph.py   ⬜ Azure Cosmos DB graph
├── ui/app.py                        ⬜ Streamlit chat UI
├── src/evaluation/evaluator.py      ⬜ RAGAS evaluation
├── scripts/golden-questions.yaml    ⬜ Golden eval set
├── infra/aws/                       ⬜ Terraform (DynamoDB, Bedrock, S3)
├── infra/azure/                     ⬜ Terraform (Cosmos DB, Azure OpenAI)
├── tests/                           ⬜ Unit + integration tests
└── .github/workflows/               ⬜ CI + wiki-rebuild workflow
```

## Next Steps to Make It Runnable

1. `poetry install` — install all deps
2. `docker compose up -d neo4j chromadb` — start local stores
3. `ollama pull llama3.2 && ollama pull nomic-embed-text`
4. `cp .env.example .env` — configure SOURCE_REPOS_PATH
5. `curl -X POST http://localhost:8200/ingest/run` — ingest docs
6. Open `http://localhost:8501` — Streamlit UI

## Cost

- Local: €0.00
- AWS per run (~2hr): €0.25-0.50
- Azure per run (~2hr): €0.50-1.00
- Total project: ~€5-8

## Key Design Decisions

- No Neptune Serverless (€0.50-0.70/hr) — DynamoDB adjacency list instead
- No OpenSearch Serverless — DynamoDB for vectors on AWS
- Neo4j Community in Docker — free, same Cypher queries as production
- Credential isolation: never touch Odido AWS account (211132580210)
- Personal AWS account only for cloud runs

## AI Engineer Skills Demonstrated

1. Evaluation: RAGAS metrics, golden questions, eval gates in CI
2. Iteration: swap provider with 1 env var change
3. Monitoring: structlog, Prometheus, latency in every response
4. Feedback loops: 👍/👎 → wiki + eval set improvement
5. CI/CD: GitHub Actions, eval gate blocks deploy on regression
6. Product integration: REST API + Streamlit UI + Docker
