# GraphRAG Concepts

> The hub concept doc for the knowledge-engine. Read this once and every other deep dive in this repo will click. If you've already read `rag-chatbot/docs/ai-engineering/rag-concepts.md`, this is the "what we add on top" doc.

---

## Table of Contents

- [What is GraphRAG?](#what-is-graphrag)
- [Why a graph AND a vector store](#why-a-graph-and-a-vector-store)
- [The data model: nodes, edges, properties](#the-data-model-nodes-edges-properties)
- [Pipeline overview](#pipeline-overview)
- [Provider matrix](#provider-matrix)
- [Key components glossary](#key-components-glossary)
- [When NOT to use GraphRAG](#when-not-to-use-graphrag)
- [Further reading](#further-reading)

---

## What is GraphRAG?

Plain RAG answers a question in three steps: embed the question, look up the nearest chunks in a vector store, hand those chunks to the LLM as context. That's it. The LLM sees a flat bag of text snippets — no idea which snippet is connected to which.

GraphRAG adds a **second store** that records *how the concepts in your docs relate to each other*. When a question comes in, the system still does a vector search to find the most relevant chunks — but it also walks the graph from the entities mentioned in those chunks to pull in *connected* topics that the bare vector search would have missed.

Concretely, in this repo:

- **Plain RAG** would answer "How does Titan normalisation affect retrieval?" by retrieving the 5 chunks most similar to that sentence. If the fix is documented in three different chunks (one in `evaluation-framework.md`, one in `aws-services.md`, one in a lab result), and only one of them ranks in the top 5, you get a partial answer.
- **GraphRAG** retrieves the 5 chunks AND walks the graph from the entity `Titan Embeddings` along the edges `IMPROVES → Retrieval Score` and `USES → Cosine Similarity` to surface the other two chunks even if they didn't rank top 5 by pure semantic similarity.

🫏 **Donkey lens:** plain RAG hands the donkey GPS coordinates to find the closest backpacks; GraphRAG also gives a paper map of which towns connect, so the donkey grabs nearby-by-distance AND nearby-by-relationship.

---

## Why a graph AND a vector store

Both stores answer different questions:

| Store | Answers the question | Strength | Weakness |
| --- | --- | --- | --- |
| Vector store (Chroma / DynamoDB / Azure AI Search) | "Which text chunks are *semantically similar* to this query?" | Catches paraphrases, synonyms, cross-language matches | Treats every chunk as independent — has no idea Topic A is the parent of Topic B |
| Graph store (Neo4j / DynamoDB adjacency / Cosmos DB) | "Which other concepts are *connected* to this concept, and how?" | Captures explicit relationships (`USES`, `EXTENDS`, `IMPROVES`, `DEPENDS_ON`) the LLM extracted from your docs | Doesn't grade similarity — a node either is or isn't connected |

Run them together and the weaknesses cancel. Vector search finds relevant *text*; graph traversal finds relevant *neighbours of that text's entities*. The LLM gets both.

🫏 **Donkey lens:** the GPS warehouse finds the closest backpacks and the paper map shows which towns are related — a good delivery uses both.

---

## The data model: nodes, edges, properties

A GraphRAG graph has three things. Every store in this repo materialises them, even when the underlying tech is not a graph DB (e.g. DynamoDB stores edges as adjacency-list rows).

### Nodes (entities / topics)

A node represents a *concept* the LLM extracted from a document. In this repo nodes have the type `Topic` (see `src/models.py → Topic`):

```python
class Topic:
    id: str            # slug, e.g. "graphrag"
    name: str          # human label, e.g. "GraphRAG"
    description: str   # 1–2 sentence summary, written by the LLM
```

Concrete examples extracted from this repo's own docs: `graphrag`, `vector-search`, `titan-normalization`, `evaluation-framework`, `feedback-loop`, `gap-detector`.

### Edges (relationships)

An edge connects two nodes and carries a *type* describing the relationship (see `src/models.py → Relationship`):

```python
class Relationship:
    source_id: str          # "graphrag"
    target_id: str          # "vector-search"
    relation_type: str      # "USES" | "EXTENDS" | "RELATED_TO" | "IMPROVES" | "DEPENDS_ON"
    evidence: str           # the exact sentence the LLM extracted this from
```

Concrete edges in this repo:

- `graphrag --USES--> vector-search`
- `graphrag --USES--> neo4j`
- `titan-normalization --IMPROVES--> evaluation-framework`
- `gap-detector --DEPENDS_ON--> retrieval-score`

The `evidence` field is the auditable bit — every edge can be traced back to the sentence in your docs that produced it. If an edge looks wrong, you can fix the doc and re-ingest.

### Properties

Both nodes and edges can carry extra metadata. In this repo:

- Topic nodes carry `description`.
- Relationship edges carry `evidence` (the source sentence).
- Vector chunks carry `source_path`, `chunk_index`, and a vector embedding (lives in the *vector* store, not the graph store, but they are joined by the topic name).

🫏 **Donkey lens:** nodes are towns, edges are roads with road-signs (`USES`, `IMPROVES`...), properties are the small print on the signpost ("road built from sentence X in `architecture.md`").

---

## Pipeline overview

The full data flow, written in pipeline order. Each stage maps to one or more files under `src/`.

```
Source repos (.md / .py)
        │
        ▼
[1] Scan          src/ingestion/scanner.py
        │  walks SOURCE_REPOS_PATH, yields documents
        ▼
[2] Chunk         src/ingestion/scanner.py
        │  splits each doc into RAG_CHUNK_SIZE windows
        ▼
[3] Extract       src/ingestion/graph_extractor.py + src/llm/*
        │  LLM reads each chunk, returns {topics:[…], relationships:[…]}
        ▼
[4] Embed         src/llm/<provider>.py
        │  embedding model turns each chunk into a vector
        ▼
[5] Store both    src/vectorstore/<provider>.py  +  src/graphstore/<provider>.py
        │  vectors → vector store ; topics + edges → graph store
        ▼
                     ────── ingestion ends, query begins ──────
        │
        ▼
[6] Vector search src/chat/engine.py → vector_store.search()
        │  top-k chunks by cosine similarity
        ▼
[7] Graph expand  src/chat/engine.py → graph_store.get_connected_topics()
        │  follow edges 1–2 hops from topics that appear in the top-k chunks
        ▼
[8] Gap check     src/chat/gap_detector.py
        │  HIGH / PARTIAL / GAP based on retrieval score
        ▼
[9] LLM answer    src/llm/<provider>.py → complete()
        │  prompt = system prompt + retrieved chunks + connected topics + question
        ▼
[10] Feedback     src/chat/feedback.py + src/chat/candidate_store.py
            👍 → wiki/feedback/verified-answers.md (re-ingested next run)
            👎 → scripts/golden-questions.yaml (eval set grows)
            GAP→ candidate stored for human review
```

Two things to notice:

1. **Both stores are written in the same ingestion run.** They never go out of sync because they're both fed from the same chunk.
2. **Retrieval is a join.** The vector store finds chunks; the graph store extends those chunks with neighbour topics. Neither store could do this alone.

🫏 **Donkey lens:** the post office (ingestion) reads every letter, files the contents in the GPS warehouse, and updates the town map at the same time. When the donkey is dispatched, it consults both before leaving the stable.

---

## Provider matrix

The same three interfaces ship in three flavours. Switching is one env var: `CLOUD_PROVIDER=local|aws|azure`.

| Layer | Local (€0) | AWS | Azure |
| --- | --- | --- | --- |
| Vector store | ChromaDB (`src/vectorstore/chroma.py`) | DynamoDB table + Python cosine (`dynamodb.py`) | Azure AI Search (`azure_search.py`) |
| Graph store | Neo4j Community (`graphstore/neo4j_store.py`) | DynamoDB adjacency list (`dynamodb_graph.py`) | Cosmos DB NoSQL (`cosmos_graph.py`) |
| LLM + embeddings | Ollama llama3.2 + nomic-embed-text (`llm/ollama.py`) | Bedrock Claude Haiku + Titan v2 (`llm/bedrock.py`) | Azure OpenAI GPT-4o-mini + text-embedding-3-small (`llm/azure_openai.py`) |
| Run cost (per lab session ~50 queries) | €0 | ~€0.25 | ~€0.50 |
| 🫏 Donkey | The home barn — local llama, ChromaDB shelf, Neo4j map, no bills | The AWS depot — Claude writer, DynamoDB shelf AND DynamoDB adjacency-list map sharing one warehouse | The Azure hub — GPT-4o-mini writer, AI Search shelf, Cosmos DB map, free-tier postcode |

**Why no managed graph DB on AWS?** Neptune Serverless costs €0.50–0.70/hr just to exist. For a portfolio repo we model the graph as DynamoDB partition rows (`PK = "TOPIC#<id>"`, `SK = "REL#<target_id>"`) and traverse with `Query` calls. Same data model, fraction of the cost. See `src/graphstore/dynamodb_graph.py`.

**Why Cosmos DB NoSQL on Azure (not Gremlin API)?** Cosmos NoSQL has a generous free tier (400 RU/s) and lets us use the same adjacency pattern as DynamoDB. Gremlin would be a more "graph-native" choice but adds cost and an extra query language for no measurable retrieval win on this dataset size.

---

## Key components glossary

The pieces unique to this repo (above and beyond the rag-chatbot pipeline). Every entry maps to a file under `src/`.

| Component | File | What it does | 🫏 Donkey |
| --- | --- | --- | --- |
| Scanner | `src/ingestion/scanner.py` | Walks `SOURCE_REPOS_PATH`, yields markdown / python files, splits them into chunks | The post-office sorter — opens every envelope, cuts long letters into uniform pages before they hit the warehouse |
| Graph extractor | `src/ingestion/graph_extractor.py` | Calls the LLM on each chunk to pull out topics + typed relationships, then writes them to the graph store | The town-cartographer — reads each delivery note and pencils the towns and roads onto the official paper map |
| Vector store | `src/vectorstore/base.py` + providers | Stores chunk embeddings, returns top-k by cosine similarity | The GPS warehouse with stadium signs — every backpack on a numbered shelf, retrieved by GPS proximity |
| Graph store | `src/graphstore/base.py` + providers | Stores topics + relationships, returns 1–2 hop neighbours | The wall-sized paper map — knows which town leads to which, regardless of GPS distance |
| Chat engine | `src/chat/engine.py` | Orchestrates: vector search → graph expand → gap check → LLM answer | The dispatcher — gives the donkey the GPS shortlist plus the map neighbours, then signs the delivery note |
| Gap detector | `src/chat/gap_detector.py` | Buckets retrieval score into HIGH / PARTIAL / GAP and writes unanswered questions to `wiki/gaps/` | The honest auditor — flags trips where the donkey couldn't find a real road, so you don't mistake invented routes for real ones |
| Candidate store | `src/chat/candidate_store.py` | When confidence = GAP, the LLM still answers from training data; that answer is parked here for human review | The shortlist clipboard — invented routes wait here for the supervisor's 👍 before they're pencilled onto the official map |
| Wiki generator | `src/wiki/generator.py` | Reads verified Q&A and writes a tourist brochure (`.md`) per topic, ready to be re-ingested | The brochure-writer — turns approved trip reports into a visitor's guide for each town |
| Feedback loop | `src/chat/feedback.py` | 👍 → verified-answers.md ; 👎 → golden-questions.yaml ; closes the self-improving loop | The trip-debrief desk — good trips get framed on the wall, bad trips get added to next month's training run |
| Evaluator | `src/evaluation/evaluator.py` | Scores answers on retrieval, faithfulness, completeness, hallucination_rate, etc. | The report card — same 9 columns every run, so improvements and regressions are obvious |

---

## When NOT to use GraphRAG

GraphRAG adds two real costs: an extra LLM call per chunk during ingestion (to extract topics) and a second store to keep alive at query time. Plain RAG is the right answer when:

| Situation | Why plain RAG wins |
| --- | --- |
| Your corpus is short, flat, and topically narrow (<500 chunks, single subject) | Vector search alone hits the right chunks; graph adds no neighbours worth visiting |
| Your queries are factoid lookups ("What is the capital of France?") | One semantically-nearest chunk usually contains the whole answer |
| Latency budget is sub-200 ms | Graph expansion + extra prompt tokens push tail latency up |
| Ingestion budget is dominated by LLM cost | Topic extraction roughly doubles the LLM tokens per ingest |
| Your team can't maintain two stores | Operationally a graph store is one more thing to back up, monitor, and migrate |

Use GraphRAG when at least two of the following are true: corpus has many cross-references, users ask multi-hop questions ("how does X compare to Y given Z?"), the same entity appears in many docs under different phrasings, or you want auditable explanations ("the answer mentions X because the graph connects X to Y via `IMPROVES`, evidence: …").

🫏 **Donkey lens:** if your village has one road and three houses you don't need a paper map — it only pays off once you have multiple villages with shared roads.

---

## Further reading

Inside this repo (most of these arrive in batches B/C/D — placeholders today):

- `docs/architecture.md` — the system diagram
- `docs/ai-engineering/ingestion-pipeline-deep-dive.md` — stages 1–5 in detail
- `docs/ai-engineering/graph-extractor-deep-dive.md` — how the LLM is prompted to emit topics + edges
- `docs/ai-engineering/chat-engine-deep-dive.md` *(coming in batch C)* — stages 6–9 in detail
- `docs/ai-engineering/gap-detector-deep-dive.md` *(coming in batch C)* — confidence thresholds and the audit trail
- `docs/ai-engineering/wiki-generator-deep-dive.md` *(coming in batch C)* — how verified answers become re-ingestable docs
- `docs/hands-on-labs/how-to-read-the-labs.md` — read this BEFORE the phase labs

Outside this repo:

- `rag-chatbot/docs/ai-engineering/rag-concepts.md` — the prerequisite doc; covers embeddings, chunking, and plain RAG
- The original Microsoft GraphRAG paper (2024) — a heavier, community-detection variant of the same idea; this repo uses a simpler entity-extraction variant
