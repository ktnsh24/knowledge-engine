# Architecture Deep Dive

## Table of Contents

- [Overview](#overview)
- [🫏 The Donkey Analogy](#-the-donkey-analogy)
- [Why GraphRAG? (Not Just Vector Search)](#why-graphrag-not-just-vector-search)
- [Data Flow](#data-flow)
- [Provider Architecture](#provider-architecture)
- [Self-Improving Loop](#self-improving-loop)
- [Cost Architecture](#cost-architecture)

---

## Overview

Knowledge Engine is a **GraphRAG** system — it uses BOTH a vector database (semantic search) AND a graph database (relationship traversal) to answer questions.

---

## 🫏 The Donkey Analogy

> The LLM is the donkey — it carries your question to an answer.
> The graph + vector store is the road — a broken road means the donkey can't deliver.
> This architecture builds the best possible road from your raw docs.

---

## Why GraphRAG? (Not Just Vector Search)

| Question | Vector Search Alone | GraphRAG | 🫏 Donkey |
|----------|---------------------|----------|-----------|
| "What is RAG?" | ✅ Finds chunks about RAG | ✅ Finds chunks + expands to "Embeddings", "Retrieval", "Vector DB" | A factoid question — GPS alone gets the right backpacks, but the paper map throws in the neighbouring towns of "Embeddings" and "Vector DB" for richer context |
| "How does Titan fix compare to Azure?" | ❌ May miss connection | ✅ Graph links "Titan normalization" → "cosine similarity" → "retrieval score" | A multi-hop question — GPS finds chunks that mention Titan OR Azure but rarely both; the paper map walks the road from Titan → cosine → retrieval-score and surfaces the comparison sentence |
| "What did we learn from rag-chatbot?" | ❌ Scattered chunks | ✅ Topic "rag-chatbot" links to all sub-topics | A roll-up question — GPS finds 5 random rag-chatbot chunks; the paper map fans out from the rag-chatbot town to every connected sub-topic, so the donkey collects the full set |

**Vector DB** answers: *"what chunks are semantically similar?"*
**Graph DB** answers: *"what other topics are connected to this topic?"*

Combined = richer context → better answers.

---

## Data Flow

```
User question
     ↓
[1] Vector Search (ChromaDB / DynamoDB / Azure AI Search)
     → top-5 most relevant chunks
     ↓
[2] Graph Expansion (Neo4j / DynamoDB adjacency / Cosmos DB)
     → connected topics (2 hops)
     → adds topic names to context
     ↓
[3] Context Assembly
     → chunk texts + connected topic names
     ↓
[4] LLM Completion (Ollama / Bedrock / Azure OpenAI)
     → system prompt: DONKEY_SYSTEM_PROMPT (always on)
     → generates answer + 🫏 donkey analogy
     ↓
[5] Response
     → answer, donkey_analogy, sources, topics, latency_ms
     ↓
[6] Feedback Loop
     👍 → save Q&A to wiki/feedback/verified-answers.md
     👎 → append to scripts/golden-questions.yaml (eval set grows)
```

---

## Provider Architecture

All 3 providers implement the **same 3 interfaces**:
- `BaseVectorStore` — `upsert()`, `search()`, `chunk_count()`, `delete_by_source()`
- `BaseGraphStore` — `upsert_topic()`, `upsert_relationship()`, `get_connected_topics()`, `get_full_graph()`
- `BaseLLM` — `complete()`, `extract_topics_and_relations()`, `generate_wiki_page()`

Switching provider = 1 env var: `CLOUD_PROVIDER=local|aws|azure`

---

## Self-Improving Loop

```
Week 1: Ingest docs → answer questions → feedback
Week 2: Feedback data improves eval set
         New questions added → CI runs evals → poor answers caught early
         Wiki grows → more context → better answers
Week N: The road is well-paved. Donkey delivers fast and accurately.
```

---

## Cost Architecture

| Component | Local | AWS | Azure | 🫏 Donkey |
|-----------|-------|-----|-------|-----------|
| LLM | Ollama (free) | Bedrock Haiku ($0.00025/1K tokens) | GPT-4o-mini ($0.00015/1K tokens) | The writer at the desk — a free local llama vs a per-token Claude Haiku vs a per-token GPT-4o-mini, same delivery note format |
| Embeddings | nomic-embed-text (free) | Titan v2 ($0.00002/1K tokens) | text-embedding-3-small ($0.00002/1K tokens) | The GPS-coordinate stamper — turns each backpack into a numeric address; local stamps are free, cloud stamps charge per 1K tokens stamped |
| Vector Store | ChromaDB (free) | DynamoDB PAY_PER_REQUEST | Azure AI Search (free tier) | The GPS warehouse — a local barn shelf, an AWS pay-per-fetch depot, or an Azure free-tier hub holding the same backpacks |
| Graph Store | Neo4j Community (free) | DynamoDB PAY_PER_REQUEST | Cosmos DB (free tier 400 RU/s) | The paper town map — drawn properly in Neo4j, rolled up as adjacency rows in DynamoDB, or pinned as document pages in Cosmos NoSQL |
| **Total/run** | **€0** | **~€0.25-0.50** | **~€0.50-1.00** | The full hay-and-toll bill for one lab session of ~50 deliveries, all-in across writer, stamper, warehouse, and map |

**Key cost decisions:**
- No Neptune Serverless (€0.50-0.70/hr) → DynamoDB adjacency list instead
- No OpenSearch Serverless → DynamoDB vector store with Python cosine search
- Azure free tier covers Cosmos DB (400 RU/s) and AI Search (3 indexes)
