# Hands-On Labs — Phase 1: GraphRAG Foundation

> **Format:** Same structure as rag-chatbot hands-on labs. Each lab has a concept, experiments, record tables, and a "What you learned" section.
> **API base:** `http://localhost:8200`
> **UI:** `http://localhost:8501`

---

## Table of Contents

- [Cost Estimation — Local vs Cloud](#cost-estimation)
- [Setup — Ingest Docs First](#setup)
- [🫏 The Donkey Analogy — Phase 1 Metrics](#donkey-analogy)
- [Lab 1: Vector Search — "Did I find the right chunks?"](#lab-1-vector-search)
- [Lab 2: Graph Traversal — "Did the knowledge graph expand my answer?"](#lab-2-graph-traversal)
- [Lab 3: GraphRAG Combined — "Is 1+1 > 2?"](#lab-3-graphrag-combined)
- [Phase 1 Skills Checklist](#skills-checklist)

---

## Cost Estimation {#cost-estimation}

| Stack | Per lab session (~50 queries) | Monthly (always on) |
|-------|------------------------------|---------------------|
| **Local** | **€0** | **€0** |
| AWS (Bedrock Haiku + DynamoDB) | ~€0.02 | €0 (PAY_PER_REQUEST idle) |
| Azure (GPT-4o-mini + Cosmos DB) | ~€0.03 | €0 (free tier) |

> 💡 Always run labs locally first. Switch to cloud only to validate cross-provider behaviour.

---

## Setup — Ingest Docs First {#setup}

Before running any lab, you need docs in the vector store and graph:

```bash
# Step 1: Start services
docker compose up -d neo4j chromadb

# Step 2: Start API
poetry run start

# Step 3: Ingest your AI portfolio docs
curl -X POST http://localhost:8200/ingest/run

# Step 4: Wait for ingestion to complete (~2-5 min for all repos)
watch -n 5 'curl -s http://localhost:8200/ingest/status'
# Wait until chunks > 0 and topics > 0
```

---

## 🫏 The Donkey Analogy — Phase 1 Metrics {#donkey-analogy}

| Metric | Donkey Version | What It Really Measures | How It's Calculated |
|--------|---------------|------------------------|---------------------|
| **retrieval_avg** | The donkey searches the warehouse and picks 5 packages. How good were they? 0.9 = all excellent. 0.2 = mostly wrong shelf. | Average cosine similarity of retrieved chunks to the query. | Sum of chunk scores / chunk count. Min-max normalized so best = 1.0 (fixes Titan low-score issue from rag-chatbot). |
| **context_precision** | Of the 5 packages the donkey grabbed, how many were actually what the customer ordered? | Fraction of retrieved chunks that are relevant to the question. | Keyword overlap: relevant_chunks / total_chunks. |
| **context_recall** | **NEW** — The warehouse has 10 relevant shelves. The donkey only visited 6. Recall = 0.6. Precision doesn't catch this — recall does. | Of ALL expected topics, how many actually appeared in what was retrieved? | expected_topics_found / total_expected_topics. Graph expansion helps this score. |
| **latency_ms** | How long did the donkey take to complete the delivery? Target: < 3000ms local. | Wall-clock time from question to answer. | `time.monotonic()` delta in milliseconds. |

**Phase 1 insight:** Vector search gives precision. Graph traversal gives recall.
You need both to score well on all metrics — that's why this is GraphRAG, not just RAG.

---

## Lab 1: Vector Search — "Did I find the right chunks?" {#lab-1-vector-search}

**Skill:** Understand vector retrieval quality, chunk scoring, top_k impact
**Time:** 20 minutes
**Metric focus:** `retrieval_avg`, `context_precision`

### Concept

```
Query: "What is the Titan embedding normalization fix?"
        ↓
Embedding model converts query → vector [0.2, 0.8, 0.1, ...]
        ↓
ChromaDB finds 5 most similar document vectors
        ↓
Returns: chunks with cosine similarity scores
        ↓
Evaluator measures: avg score, precision
```

### Experiment 1a — Baseline retrieval (vector only, no graph)

```bash
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What is RAG and why is it used?"}'
```

📝 **Record results:**

| Metric | Value |
|--------|-------|
| `retrieval_avg` | ___ |
| `context_precision` | ___ |
| `latency_ms` | ___ |
| Number of sources returned | ___ |
| Did the answer contain 🫏? | Yes / No |

### Experiment 1b — Specific technical question

```bash
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "Why did AWS Titan embeddings score low and how was the normalization fix applied?"}'
```

📝 **Record:**

| Metric | Value | Better/Worse than 1a? |
|--------|-------|----------------------|
| `retrieval_avg` | ___ | ___ |
| `context_precision` | ___ | ___ |
| Sources contain rag-chatbot docs? | Yes / No | — |

> **Why specific questions score higher:** The query embedding is closer to specific technical chunks than vague concept chunks. This is why good prompt engineering in production matters.

### Experiment 1c — Question with NO relevant docs

```bash
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the best recipe for Dutch stroopwafel?"}'
```

📝 **Record:**

| Metric | Value | What does it mean? |
|--------|-------|-------------------|
| `retrieval_avg` | ___ | Low = no relevant chunks found |
| Did the LLM refuse? | Yes / No | Correct behaviour = "I don't have this in my docs" |
| Did it hallucinate a recipe? | Yes / No | Incorrect behaviour = hallucination |

> 🫏 If retrieval_avg < 0.3, the donkey couldn't find the right shelf. A good system should say "I don't know" rather than invent an answer.

### What you learned

- [ ] Specific questions → higher retrieval scores
- [ ] Out-of-domain questions → low scores AND should produce refusals, not hallucinations
- [ ] The knowledge engine only knows what you ingested — garbage in, garbage out

---

## Lab 2: Graph Traversal — "Did the knowledge graph expand my answer?" {#lab-2-graph-traversal}

**Skill:** Understand how graph expansion improves context recall
**Time:** 25 minutes
**Metric focus:** `context_recall`, `graph_topics_added`, `graph_expansion_useful`

### Concept

```
Vector search finds: chunks about "Titan embeddings"
        ↓
Graph looks up topic "titan-embeddings" in Neo4j
        ↓
Finds connected topics (2 hops): "cosine-similarity", "normalization", "rag-chatbot"
        ↓
These topic NAMES are added to the LLM context
        ↓
LLM now knows the connected landscape, not just the chunk
```

### Experiment 2a — Topic that has graph connections

First, check what topics were extracted during ingestion:

```bash
curl http://localhost:8200/wiki/topics | python3 -m json.tool | head -40
```

📝 **Note one topic that interests you:** _______________

Now ask about it:

```bash
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain GraphRAG and what makes it different from plain vector search"}'
```

📝 **Record:**

| Metric | Value |
|--------|-------|
| `topics` array in response | List them |
| `graph_topics_added` | ___ |
| `graph_expansion_useful` | true/false |
| Did the answer mention connected topics? | Yes / No |

### Experiment 2b — Multi-hop question (tests 2-hop graph traversal)

```bash
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "How does the feedback loop in the knowledge engine connect to the evaluation system?"}'
```

This question spans two topics (`feedback-loop` → `evaluation`) that are 2 hops apart in the graph.

📝 **Record:**

| Metric | Expected | Actual |
|--------|----------|--------|
| Topics in response | feedback, evaluation, wiki | ___ |
| Answer mentions both feedback AND evaluation? | Yes | ___ |
| `context_recall` (if shown) | > 0.7 | ___ |

### Experiment 2c — Compare: graph ON vs graph OFF

Temporarily set `GRAPH_ENABLED=false` in `.env`, restart, ask the same question:

```bash
# With graph OFF (vector only):
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "How does feedback improve the wiki?"}'
```

📝 **Compare:**

| Metric | Graph ON | Graph OFF | Difference |
|--------|----------|-----------|------------|
| Answer mentions related concepts? | ___ | ___ | ___ |
| Answer length (approx words) | ___ | ___ | ___ |
| Topics array length | ___ | 0 | ___ |

> 🫏 Graph ON = the donkey has a full city map. Graph OFF = the donkey only knows its own street.

### What you learned

- [ ] Graph traversal adds connected topic names as context
- [ ] 2-hop traversal catches topics not directly in retrieved chunks
- [ ] `context_recall` improves with graph ON vs OFF
- [ ] `graph_expansion_useful=false` = topics were found but LLM didn't use them (tweak max_hops or top_k)

---

## Lab 3: GraphRAG Combined — "Is 1+1 > 2?" {#lab-3-graphrag-combined}

**Skill:** See the combined effect of vector + graph
**Time:** 20 minutes
**Metric focus:** all 4 Phase 1 metrics together

### Experiment 3a — Run the full evaluation suite

```bash
# POST to the evaluation endpoint
curl -X POST http://localhost:8200/eval/run \
  -H "Content-Type: application/json" \
  -d '{"n_questions": 5}'
```

This runs 5 golden questions from `scripts/golden-questions.yaml` and returns all metrics.

📝 **Record summary:**

| Metric | Score | Pass (>0.5)? |
|--------|-------|-------------|
| `avg_retrieval` | ___ | ___ |
| `avg_context_precision` | ___ | ___ |
| `avg_context_recall` | ___ | ___ |
| `pass_rate` | ___ | ___ |
| `avg_latency_ms` | ___ | — |

### Experiment 3b — Run all 11 golden questions

```bash
curl -X POST http://localhost:8200/eval/run \
  -H "Content-Type: application/json" \
  -d '{"n_questions": 11}'
```

📝 **Record full results:** (save to `scripts/eval-results/my-baseline.json`)

### Experiment 3c — Ingest more docs, re-run eval

Add a new markdown document to one of your repos, re-ingest, run eval again.

```bash
# Re-ingest after adding docs
curl -X POST http://localhost:8200/ingest/run
# Wait, then re-run eval
curl -X POST http://localhost:8200/eval/run -d '{"n_questions": 11}'
```

📝 **Compare:**

| Metric | Before | After more docs | Change |
|--------|--------|----------------|--------|
| `avg_context_recall` | ___ | ___ | ___ |
| `pass_rate` | ___ | ___ | ___ |

> 🫏 More docs = better road. The donkey gets smarter every time you add cobblestones.

### Phase 1 Skills Checklist {#skills-checklist}

- [ ] Can explain the difference between context_precision and context_recall
- [ ] Can explain why graph traversal improves recall
- [ ] Know what a retrieval_avg < 0.4 means (and how to fix it)
- [ ] Have run the golden question eval suite and recorded baseline scores
- [ ] Know that `graph_expansion_useful=false` is a signal to tune, not an error
