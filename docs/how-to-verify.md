# How to Verify the Knowledge Engine Is Working

> This answers two key questions:
> 1. **How do I see the connected map?** (the knowledge graph)
> 2. **How do I know the knowledge base is growing from my questions?**

---

## Table of Contents

- [🚚 Courier Analogy First](#-courier-analogy-first)
- [Part 1 — Seeing the Connected Map](#part-1--seeing-the-connected-map)
- [Part 2 — How the Knowledge Base Grows Over Time](#part-2--how-the-knowledge-base-grows-over-time)
- [Part 3 — Measuring Knowledge Growth Numerically](#part-3--measuring-knowledge-growth-numerically)
- [Part 4 — Verify After Each Phase](#part-4--verify-after-each-phase)
- [Summary Checklist](#summary-checklist)

---

## 🚚 Courier Analogy First

> 🚚 The knowledge engine is a courier delivering packages along a road map (the graph) — verifying = checking the roads are actually being drawn, not just trusting it.

---

## Part 1 — Seeing the Connected Map

### Option A: API (JSON — fast check)

```bash
# See all topics the engine has discovered
curl http://localhost:8200/wiki/topics
```

Sample output:
```json
{
  "topics": [
    {"id": "graphrag", "name": "GraphRAG", "description": "..."},
    {"id": "vector-search", "name": "Vector Search", "description": "..."},
    {"id": "titan-normalization", "name": "Titan Normalization", "description": "..."},
    {"id": "evaluation-framework", "name": "Evaluation Framework", "description": "..."}
  ]
}
```

```bash
# See the full graph: all topics + all relationships
curl http://localhost:8200/wiki/graph
```

Sample output:
```json
{
  "topics": [...],
  "relationships": [
    {"source_id": "graphrag", "target_id": "vector-search", "relation_type": "USES", "weight": 0.9},
    {"source_id": "graphrag", "target_id": "neo4j", "relation_type": "USES", "weight": 0.8},
    {"source_id": "titan-normalization", "target_id": "evaluation-framework", "relation_type": "IMPROVES", "weight": 0.7}
  ]
}
```

The `relation_type` tells you *how* topics are connected: `USES`, `EXTENDS`, `RELATED_TO`, `IMPROVES`, `DEPENDS_ON`.

---

### Option B: Neo4j Browser (visual — recommended for exploring)

When running locally, Neo4j has a built-in visual browser:

1. Open http://localhost:7474 in your browser
2. Login: `neo4j` / `password`
3. Run this Cypher query to see the full connected map:

```cypher
MATCH (a:Topic)-[r]->(b:Topic)
RETURN a, r, b
LIMIT 100
```

You'll see a **visual graph** — nodes are topics, edges are relationships. Click any node to see its connections.

**Other useful queries:**

```cypher
-- How many topics total?
MATCH (t:Topic) RETURN count(t) AS total_topics

-- Which topics are most connected? (central nodes)
MATCH (t:Topic)-[r]->()
RETURN t.name, count(r) AS connections
ORDER BY connections DESC
LIMIT 10

-- What is connected to "GraphRAG"?
MATCH (t:Topic {name: "GraphRAG"})-[r*1..2]-(connected)
RETURN t, r, connected

-- Show all relationship types
MATCH ()-[r:USES]->() RETURN count(r) AS uses_count
MATCH ()-[r:EXTENDS]->() RETURN count(r) AS extends_count
MATCH ()-[r:RELATED_TO]->() RETURN count(r) AS related_count
```

---

### Option C: Health Check — quick snapshot

```bash
curl http://localhost:8200/health
```

```json
{"status": "ok", "provider": "local", "chunks": 164, "topics": 52}
```

- **chunks** = how many text pieces are in the vector store (more = richer semantic search)
- **topics** = how many graph nodes exist (more = richer connections)

**Before ingestion:** `chunks: 0, topics: 0`
**After ingestion:** `chunks: ~150-300, topics: ~40-80` (depends on how many repos you have)

---

## Part 2 — How the Knowledge Base Grows Over Time

This is the **self-improving loop**. The knowledge base grows in three ways:

### Way 1: More docs → ingest again

Add more `.md` or `.py` files to your repos. Re-run ingestion:

```bash
curl -X POST http://localhost:8200/ingest/run
# Then poll:
curl http://localhost:8200/ingest/status
```

Watch `chunks` and `topics` increase.

---

### Way 2: 👍 Feedback → Wiki grows

When you mark an answer as good (👍), the Q&A pair is saved to `wiki/feedback/verified-answers.md`. When you rebuild the wiki, these verified answers become additional knowledge:

```bash
# Submit positive feedback
curl -X POST http://localhost:8200/feedback/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What is context recall?", "answer": "Context recall measures...", "signal": "positive"}'

# Rebuild the wiki (adds verified answers as new knowledge pages)
curl -X POST http://localhost:8200/wiki/rebuild
```

**Before/after comparison:**
```bash
# Before
wc -l wiki-output/*.md         # e.g. 0 files

# After rebuild
wc -l wiki-output/*.md         # e.g. 3 files with 200+ lines each
```

Each wiki page is a topic summary — the LLM reads all verified answers for that topic and writes a clean summary page.

---

### Way 3: 👎 Feedback → Eval set grows

When you mark an answer as bad (👎), the question is appended to `scripts/golden-questions.yaml`. This means:
- The eval set gets larger over time
- Bad cases are automatically re-tested on every eval run
- CI blocks deployment if those questions are still failing

```bash
# Submit negative feedback
curl -X POST http://localhost:8200/feedback/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the difference between context precision and context recall?", "answer": "...", "signal": "negative"}'

# Check the golden questions file grew
wc -l scripts/golden-questions.yaml
# More lines = eval set is growing
```

---

## Part 3 — Measuring Knowledge Growth Numerically

Run the evaluation suite before and after using the system to measure improvement:

```bash
# Run eval
curl -X POST http://localhost:8200/eval/run | python3 -m json.tool
```

Track these metrics over time:

| Metric | What it tells you | Growing means... | 🚚 Courier |
|--------|-------------------|------------------|-----------|
| `avg_retrieval` | Are relevant chunks being found? | More/better indexed docs | Did the courier grab the right parcels from the GPS warehouse on average? Higher = better-stocked shelves |
| `avg_context_recall` | Does the context cover the full answer? | Graph expansion working better | Did the courier + paper map together pull in all the parcels needed, not just the closest ones? Higher = the map is well-drawn |
| `avg_faithfulness` | Is the LLM sticking to the context? | LLM not hallucinating | Did the courier copy from the parcels instead of inventing? Higher = the courier is reading the parcels, not making up parcels |
| `avg_completeness` | Are all aspects of the question answered? | Richer knowledge base | Did the courier deliver every item on the order, not just the easy ones? Higher = the warehouse has the missing items now |
| `hallucination_rate_pct` | How often does the LLM make things up? | Lower = knowledge base improving | What fraction of trips had at least one invented parcel? Lower = the courier trusts the parcels over its own pocket more often |
| `overall_pass_rate` | Overall quality gate | Should increase over time | The pass mark on the report card across all metrics — climbs as the warehouse and map fill in the obvious gaps |

### Track improvement in a simple table

After each session, note down:

```
Date        | chunks | topics | pass_rate | hallucination%
------------|--------|--------|-----------|---------------
Day 1       |    164 |     52 |     68%   |    12%
Day 7       |    210 |     71 |     74%   |     8%
Day 14      |    280 |     89 |     81%   |     5%
```

If `pass_rate` is going up and `hallucination_rate_pct` is going down — **the knowledge base is getting smarter from your usage**.

---

## Part 4 — Verify After Each Phase

### After ingestion

```bash
curl http://localhost:8200/health
# chunks > 0 AND topics > 0
```

### After asking questions

```bash
# Check answer includes connected topics
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "How does GraphRAG improve retrieval?"}' | python3 -m json.tool
# "topics" field should list 2+ connected topics (not empty)
```

### After positive feedback + wiki rebuild

```bash
ls wiki-output/
# Should see .md files appearing
```

### After negative feedback

```bash
grep -c "question:" scripts/golden-questions.yaml
# Count increases after each 👎
```

### After running labs

```bash
cat scripts/lab-results/local/lab-results-report.md | head -50
# Shows: experiments ran, pass rate, 9 metrics table
```

---

## Summary Checklist

```
✅ chunks > 0            → ingestion worked
✅ topics > 0            → graph extraction worked
✅ /wiki/graph returns relationships  → graph is connected (not isolated nodes)
✅ answer includes "topics" field     → graph expansion is happening
✅ answer includes 🚚 courier analogy  → LLM system prompt is working
✅ wiki-output/ has .md files         → wiki is growing from feedback
✅ golden-questions.yaml growing      → eval set is improving from bad answers
✅ eval pass_rate ≥ 0.65              → quality gate passes
```
