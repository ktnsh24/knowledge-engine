# Hands-on Labs — Config Tuning (Tier 1–5)

> **Why these labs exist:** This is the AI-engineering interview answer. When asked "how would you tune this system?" the answer is a guided tour of these sweeps + their trade-offs.
>
> **How to run:** Each lab changes ONE config in `.env`, runs the same 3 questions, records the metrics, and explains the trade-off.
>
> **🚚 Courier lens:** Each lab ends with a courier takeaway summarising the trade-off in plain language.

## Table of Contents
- [Setup — Common to all labs](#setup--common-to-all-labs)
- [Lab 1: Chunk Size Sweep](#lab-1-chunk-size-sweep--how-big-should-each-parcel-pocket-be)
- [Lab 2: Chunk Overlap Sweep](#lab-2-chunk-overlap-sweep--should-pockets-share-content-at-the-edges)
- [Lab 3: top_k Sweep](#lab-3-top_k-sweep--how-many-pockets-should-the-courier-carry)
- [Lab 4: Temperature Sweep](#lab-4-temperature-sweep--how-creative-should-the-courier-be)
- [Lab 5: System Prompt Sweep](#lab-5-system-prompt-sweep--strict-vs-lax-delivery-note)
- [Lab 6: Embedding Model Sweep](#lab-6-embedding-model-sweep--smaller-vs-bigger-gps-coordinates)
- [Lab 7: Reranker On/Off](#lab-7-reranker-onoff--second-pass-quality-check)
- [Lab 8: Hybrid Search On/Off](#lab-8-hybrid-search-onoff--gps-plus-keyword-radio)
- [Lab 9: Max Tokens Sweep](#lab-9-max-tokens-sweep--parcels-capacity-of-the-reply)
- [Lab 10: Distance Metric Sweep](#lab-10-distance-metric-sweep--how-to-measure-gps-closeness)
- [Lab 11: HNSW M Sweep](#lab-11-hnsw-m-sweep--how-many-stadium-signs-per-junction)
- [Lab 12: HNSW ef_construction Sweep](#lab-12-hnsw-ef_construction-sweep--build-time-quality-of-the-sign-network)
- [Lab 13: HNSW ef_search Sweep](#lab-13-hnsw-ef_search-sweep--how-many-signs-to-check-at-query-time)
- [Lab 14: Query Rewriting On/Off](#lab-14-query-rewriting-onoff--rewrite-vague-delivery-notes)
- [Lab 15: Multi-Query Sweep](#lab-15-multi-query-sweep--ask-the-question-n-different-ways)
- [Lab 16: Metadata Filtering](#lab-16-metadata-filtering--pre-sort-the-warehouse-aisle)
- [Lab 17: Chunk Strategy](#lab-17-chunk-strategy--how-the-post-office-pre-sorts)
- [Lab 18: Eval Thresholds](#lab-18-eval-thresholds--how-strict-is-the-report-card)
- [Lab 19: LLM-as-Judge Evaluation](#lab-19-llm-as-judge-evaluation--can-a-smarter-llm-grade-the-couriers-report-card)

---

## Setup — Common to all labs

1. Make sure the API is running: `poetry run uvicorn src.main:app --port 8200 --reload`
2. Make sure backing stores are up: `docker compose up -d neo4j chromadb`
3. Have the 3 fixed test questions ready:
   - **Q1:** "What is the courier analogy in this codebase?"
   - **Q2:** "How does the rag-chatbot ingestion pipeline work end-to-end?"
   - **Q3:** "What vector store does ai-gateway use and why?"
4. Each lab takes ~5–10 min: change config → restart/re-ingest → run questions → record table

---

## Lab 1: Chunk Size Sweep — "How big should each parcel compartment be?"

**Config:** `RAG_CHUNK_SIZE` (default: `500`)
**What it controls:** Number of characters per chunk during ingestion.
**Hypothesis:** Small chunks = precise but miss cross-section context; large chunks = more context but lower retrieval precision.

### Setup
1. Set `RAG_CHUNK_SIZE=200` in `.env`
2. Re-ingest: `poetry run python -m src.ingestion.run`
3. Run the same 3 questions (Q1–Q3 from common setup)
4. Repeat for each value below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| 200 | ___ | ___ | ___ | ___ | ___ |
| 500 | ___ | ___ | ___ | ___ | ___ |
| 1000 | ___ | ___ | ___ | ___ | ___ |

### What we learned
Small chunks isolate facts cleanly but split arguments across boundaries; the LLM ends up retrieving 5 fragments that each say half the story. Large chunks include more context but dilute the embedding (one vector covers many topics) and waste prompt budget. Rule of thumb: 500 characters is a strong default for technical markdown; go to 1000 for narrative docs, 200 only for FAQ-style snippets.

### 🚚 Courier takeaway
Tiny pockets in the parcel mean each one holds one clean fact, but the courier forgets how facts connect; giant pockets carry the whole chapter but the GPS coordinates point to a vague middle.

---

## Lab 2: Chunk Overlap Sweep — "Should pockets share content at the edges?"

**Config:** `RAG_CHUNK_OVERLAP` (default: `100`)
**What it controls:** Characters duplicated between adjacent chunks.
**Hypothesis:** Higher overlap = better answers spanning section boundaries, more storage cost.

### Setup
1. Set `RAG_CHUNK_OVERLAP=0` in `.env`
2. Re-ingest: `poetry run python -m src.ingestion.run`
3. Run the same 3 questions (Q1–Q3)
4. Repeat for each value below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| 0 | ___ | ___ | ___ | ___ | ___ |
| 100 | ___ | ___ | ___ | ___ | ___ |
| 200 | ___ | ___ | ___ | ___ | ___ |

### What we learned
Zero overlap loses any fact that straddles the cut line; 200 overlap recovers them but inflates the index by ~20% and pays for it on every query. Sweet spot is usually 10–20% of `chunk_size`.

### 🚚 Courier takeaway
Letting two parcel compartments overlap a few words means a sentence cut in half is still complete in at least one pocket — at the price of carrying the same words twice.

---

## Lab 3: top_k Sweep — "How many pockets should the courier carry?"

**Config:** `RAG_TOP_K` (default: `5`)
**What it controls:** Number of chunks pulled from the vector store and stuffed into the prompt.
**Hypothesis:** Low = focused & cheap; high = noisy, dilutes retrieval average.

### Setup
1. Set `RAG_TOP_K=1` in `.env`
2. Run the same 3 questions (Q1–Q3) — no re-ingest needed
3. Repeat for each value below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| 1 | ___ | ___ | ___ | ___ | ___ |
| 3 | ___ | ___ | ___ | ___ | ___ |
| 5 | ___ | ___ | ___ | ___ | ___ |
| 10 | ___ | ___ | ___ | ___ | ___ |

### What we learned
top_k=1 collapses if the top chunk is wrong; top_k=10 buys recall but introduces irrelevant chunks that the LLM may quote anyway, lowering faithfulness. Pair high top_k with a reranker (Lab 7).

### 🚚 Courier takeaway
Carrying one pocket is fast but if it's the wrong pocket the delivery fails; carrying ten pockets means the courier is rummaging through stuff it doesn't need.

---

## Lab 4: Temperature Sweep — "How creative should the courier be?"

**Config:** `LLM_TEMPERATURE` (default: `0.3`)
**What it controls:** Sampling randomness for the LLM.
**Hypothesis:** 0.0 = deterministic & faithful; higher = more hallucination.

### Setup
1. Set `LLM_TEMPERATURE=0.0` in `.env`
2. Run the same 3 questions (Q1–Q3)
3. Repeat for each value below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| 0.0 | ___ | ___ | ___ | ___ | ___ |
| 0.3 | ___ | ___ | ___ | ___ | ___ |
| 0.7 | ___ | ___ | ___ | ___ | ___ |

### What we learned
For RAG/QA, low temperature is almost always correct — you want the courier to read the shipping manifest, not invent. Reserve >0.5 for brainstorming or creative agents.

### 🚚 Courier takeaway
Cold courier reads the shipping manifest word-for-word; warm courier starts adding side notes that were never in the parcel.

---

## Lab 5: System Prompt Sweep — "Strict vs lax shipping manifest"

**Config:** `SYSTEM_PROMPT` (default: balanced)
**What it controls:** The instructions prepended to every LLM call.
**Hypothesis:** Strict ("ONLY use context, otherwise say I don't know") prevents hallucination; lax allows world knowledge to leak in.

### Setup
1. Set `SYSTEM_PROMPT` in `.env` to the strict variant (see `src/llm/base.py`)
2. Run the same 3 questions (Q1–Q3)
3. Repeat for the lax variant

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| strict | ___ | ___ | ___ | ___ | ___ |
| balanced (default) | ___ | ___ | ___ | ___ | ___ |
| lax | ___ | ___ | ___ | ___ | ___ |

### What we learned
The single biggest quality lever in RAG. A strict "answer only from context" prompt can lift faithfulness 20+ points overnight, at the cost of more "I don't know" responses (which is actually good — calibrated honesty).

### 🚚 Courier takeaway
A shipping manifest saying "deliver only what's in the parcel" stops the courier from adding extras from memory; a vague note lets it freestyle.

---

## Lab 6: Embedding Model Sweep — "Smaller vs bigger GPS coordinates"

**Config:** `EMBEDDING_MODEL` (default: `nomic-embed-text` 768d locally)
**What it controls:** The model that maps text → vector. Different models produce different dimensions and quality.
**Hypothesis:** Bigger = higher retrieval quality + cost; **requires re-ingest + new index** because dimensions differ.

### Setup
1. Set `EMBEDDING_MODEL=all-MiniLM-L6-v2` (384d) in `.env`
2. Drop and re-ingest: `poetry run python -m src.ingestion.run --reset`
3. Run the same 3 questions (Q1–Q3)
4. Repeat for each value below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| MiniLM (384d) | ___ | ___ | ___ | ___ | ___ |
| nomic-embed (768d) | ___ | ___ | ___ | ___ | ___ |
| Titan v2 (1024d) | ___ | ___ | ___ | ___ | ___ |

### What we learned
Bigger embedding dims usually retrieve better but are slower to embed and search, and the index must be rebuilt — this is a deploy-day decision, not a runtime knob. Always re-evaluate on the same golden set.

### 🚚 Courier takeaway
A high-resolution GPS pins each parcel exactly; a low-resolution GPS lumps similar parcels at the same junction and the courier fetches the wrong one.

---

## Lab 7: Reranker On/Off — "Second-pass quality check"

**Config:** `RERANKER_ENABLED` + `RERANKER_MODEL` (default: `false`)
**What it controls:** Whether top_k×3 retrieved chunks are re-scored by a cross-encoder before stuffing.
**Hypothesis:** +10–20% retrieval quality, +200–500ms latency.

### Setup
1. Set `RERANKER_ENABLED=false` in `.env`
2. Run the same 3 questions (Q1–Q3)
3. Set `RERANKER_ENABLED=true` and `RERANKER_MODEL=BAAI/bge-reranker-base`, repeat
4. (Optional) Try `RERANKER_MODEL=cohere-rerank-english-v3`

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| off | ___ | ___ | ___ | ___ | ___ |
| bge-reranker-base | ___ | ___ | ___ | ___ | ___ |
| cohere-rerank-v3 | ___ | ___ | ___ | ___ | ___ |

### What we learned
Reranking is the cheapest big win after the system prompt — pull more candidates from the GPS warehouse, then have a smarter (slower) model pick the best 5. Costs latency, gains precision.

### 🚚 Courier takeaway
After grabbing 15 pockets at the warehouse, a quality inspector re-checks the labels and keeps only the 5 the courier actually needs.

---

## Lab 8: Hybrid Search On/Off — "GPS plus keyword radio"

**Config:** `HYBRID_SEARCH_ENABLED` + `HYBRID_ALPHA` (default: `false`, alpha `0.5`)
**What it controls:** Combine vector similarity with keyword (BM25) matching. Alpha = vector weight.
**Hypothesis:** Wins for queries with rare terms (names, IDs, error codes) that semantic search blurs over.

### Setup
1. Set `HYBRID_SEARCH_ENABLED=false` in `.env`
2. Run the same 3 questions (Q1–Q3) plus a "rare term" probe like "What is `COURIER_SYSTEM_PROMPT`?"
3. Enable hybrid and sweep alpha

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| off | ___ | ___ | ___ | ___ | ___ |
| alpha=0.3 | ___ | ___ | ___ | ___ | ___ |
| alpha=0.5 | ___ | ___ | ___ | ___ | ___ |
| alpha=0.7 | ___ | ___ | ___ | ___ | ___ |

### What we learned
Pure vector search loses identifiers and code symbols; pure keyword loses paraphrases. Hybrid with alpha=0.5–0.7 is usually best for technical docs.

### 🚚 Courier takeaway
The courier uses GPS to get to the right neighbourhood and a keyword radio to find the exact street name — together they beat either alone.

---

## Lab 9: Max Tokens Sweep — "parcel capacity of the reply"

**Config:** `LLM_MAX_TOKENS` (default: `1024`)
**What it controls:** Hard cap on output tokens.
**Hypothesis:** Truncation vs cost — short caps cut answers mid-sentence; long caps inflate spend.

### Setup
1. Set `LLM_MAX_TOKENS=256` in `.env`
2. Run the same 3 questions (Q1–Q3) — note any truncated answers
3. Repeat for each value below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| 256 | ___ | ___ | ___ | ___ | ___ |
| 1024 | ___ | ___ | ___ | ___ | ___ |
| 4096 | ___ | ___ | ___ | ___ | ___ |

### What we learned
Output tokens are 4–5× the cost of input tokens — pick the smallest cap that doesn't truncate your worst-case answer.

### 🚚 Courier takeaway
A small parcel crate forces the courier to drop half the parcel; an oversized crate makes every trip expensive even when there's barely anything to carry.

---

## Lab 10: Distance Metric Sweep — "How to measure GPS closeness"

**Config:** `DISTANCE_METRIC` (default: `cosine`)
**What it controls:** How the vector store scores similarity between query and chunks.
**Hypothesis:** Cosine usually wins for normalized embeddings; L2 and dot-product can flip ranks subtly.

### Setup
1. Set `DISTANCE_METRIC=cosine` in `.env`
2. Re-ingest if your store bakes the metric into the index: `poetry run python -m src.ingestion.run --reset`
3. Run the same 3 questions (Q1–Q3)
4. Repeat for each value below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| cosine | ___ | ___ | ___ | ___ | ___ |
| L2 | ___ | ___ | ___ | ___ | ___ |
| dot | ___ | ___ | ___ | ___ | ___ |

### What we learned
For OpenAI/Titan/nomic embeddings (all L2-normalized at training time), cosine ≈ dot and both beat L2. Always check whether your embedding model is normalized before changing.

### 🚚 Courier takeaway
Cosine measures the angle between two GPS coordinates ignoring magnitude — perfect for normalized parcels; L2 also cares about how far away they are, which can mislead.

---

## Lab 11: HNSW M Sweep — "How many stadium signs per junction"

**Config:** `HNSW_M` (default: `16`)
**What it controls:** Number of bidirectional links per node in the HNSW graph index.
**Hypothesis:** Higher M = better recall, slower build, more RAM.

### Setup
1. Set `HNSW_M=8` in `.env`
2. Re-ingest (HNSW is built at index time): `poetry run python -m src.ingestion.run --reset`
3. Run the same 3 questions (Q1–Q3)
4. Repeat for each value below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| 8 | ___ | ___ | ___ | ___ | ___ |
| 16 | ___ | ___ | ___ | ___ | ___ |
| 32 | ___ | ___ | ___ | ___ | ___ |

### What we learned
M trades RAM for recall. Defaults of 16 are usually fine; only push higher if recall is the bottleneck and the index fits in memory.

### 🚚 Courier takeaway
More stadium signs per junction means the courier almost always finds the right exit; fewer signs save space but the courier occasionally takes the wrong road.

---

## Lab 12: HNSW ef_construction Sweep — "Build-time quality of the sign network"

**Config:** `HNSW_EF_CONSTRUCTION` (default: `200`)
**What it controls:** How exhaustively the index is built — wider search during construction = better neighbours per node.
**Hypothesis:** Higher = better index quality, much slower ingestion.

### Setup
1. Set `HNSW_EF_CONSTRUCTION=100` in `.env`
2. Re-ingest and time it: `time poetry run python -m src.ingestion.run --reset`
3. Run the same 3 questions (Q1–Q3)
4. Repeat for each value below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| 100 | ___ | ___ | ___ | ___ | ___ |
| 200 | ___ | ___ | ___ | ___ | ___ |
| 400 | ___ | ___ | ___ | ___ | ___ |

### What we learned
A one-time build cost paid for permanent query-time recall — usually worth pushing higher than the default if you re-index rarely.

### 🚚 Courier takeaway
Spending an extra hour at the post office putting up better signs means every future courier trip is faster and more reliable.

---

## Lab 13: HNSW ef_search Sweep — "How many signs to check at query time"

**Config:** `HNSW_EF_SEARCH` (default: `64`)
**What it controls:** Width of the candidate list explored during a query.
**Hypothesis:** Higher = better recall, slower queries — the run-time recall/latency dial.

### Setup
1. Set `HNSW_EF_SEARCH=32` in `.env`
2. Run the same 3 questions (Q1–Q3) — no re-ingest needed
3. Repeat for each value below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| 32 | ___ | ___ | ___ | ___ | ___ |
| 64 | ___ | ___ | ___ | ___ | ___ |
| 128 | ___ | ___ | ___ | ___ | ___ |
| 256 | ___ | ___ | ___ | ___ | ___ |

### What we learned
The cleanest dial in HNSW: turn it up for accuracy, down for latency, no rebuild needed. Tune per query SLO.

### 🚚 Courier takeaway
Reading more stadium signs at each junction means the courier is more likely to take the optimal road, but every junction takes longer.

---

## Lab 14: Query Rewriting On/Off — "Rewrite vague shipping manifests"

**Config:** `QUERY_REWRITING_ENABLED` (default: `false`)
**What it controls:** Whether an LLM call rewrites the user query (adding context, expanding pronouns) before vector search.
**Hypothesis:** Helps vague conversational queries; LLM rewrites to add context before search.

### Setup
1. Set `QUERY_REWRITING_ENABLED=false` in `.env`
2. Run the same 3 questions (Q1–Q3) plus a vague one like "and what about its cost?"
3. Enable and repeat

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| off | ___ | ___ | ___ | ___ | ___ |
| on | ___ | ___ | ___ | ___ | ___ |

### What we learned
Pays off for chat where users speak in fragments; wasteful for one-shot well-formed queries. Adds an extra LLM call to every request.

### 🚚 Courier takeaway
Before leaving the depot, the courier rewrites the smudged shipping manifest into clear handwriting so the warehouse can find the parcel.

---

## Lab 15: Multi-Query Sweep — "Ask the question N different ways"

**Config:** `MULTI_QUERY_COUNT` (default: `1`)
**What it controls:** Generates N paraphrases of the query, retrieves for each, then unions/dedups.
**Hypothesis:** More variants = better recall, ~N× embedding cost.

### Setup
1. Set `MULTI_QUERY_COUNT=1` in `.env`
2. Run the same 3 questions (Q1–Q3)
3. Repeat for each value below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| 1 | ___ | ___ | ___ | ___ | ___ |
| 3 | ___ | ___ | ___ | ___ | ___ |
| 5 | ___ | ___ | ___ | ___ | ___ |

### What we learned
Multi-query trades cost for recall; great for low-frequency queries with high stakes (legal, support), wasteful for high-volume cheap ones.

### 🚚 Courier takeaway
The courier sends three different couriers asking the same question in three ways — between them they almost always find the parcel.

---

## Lab 16: Metadata Filtering — "Pre-sort the warehouse aisle"

**Config:** `METADATA_FILTERS` (default: none)
**What it controls:** Pre-filter chunks by metadata (source repo, date, author) before vector search.
**Hypothesis:** Massive precision boost when applicable; pre-filters before vector search.

### Setup
1. Set `METADATA_FILTERS=` (none) in `.env`
2. Run the same 3 questions (Q1–Q3)
3. Try `METADATA_FILTERS=source=rag-chatbot` and re-run Q2 (rag-chatbot ingestion question)
4. Try `METADATA_FILTERS=date>2025-01-01` and re-run

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| none | ___ | ___ | ___ | ___ | ___ |
| source=rag-chatbot | ___ | ___ | ___ | ___ | ___ |
| date>2025-01-01 | ___ | ___ | ___ | ___ | ___ |

### What we learned
The cheapest precision win when you know which subset is relevant — equivalent to telling the warehouse "only check aisle 3". Useless if your metadata isn't trustworthy.

### 🚚 Courier takeaway
The courier skips the entire warehouse and walks straight to aisle 3 because the shipping manifest already says "books, not groceries".

---

## Lab 17: Chunk Strategy — "How the post office pre-sorts"

**Config:** `CHUNK_STRATEGY` (default: `fixed`)
**What it controls:** Algorithm splitting documents — fixed-size, semantic (embedding boundary), sentence, or markdown-aware (heading-based).
**Hypothesis:** Markdown-aware preserves headings = much better for technical docs.

### Setup
1. Set `CHUNK_STRATEGY=fixed` in `.env`
2. Re-ingest: `poetry run python -m src.ingestion.run --reset`
3. Run the same 3 questions (Q1–Q3)
4. Repeat for each value below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| fixed | ___ | ___ | ___ | ___ | ___ |
| sentence | ___ | ___ | ___ | ___ | ___ |
| semantic | ___ | ___ | ___ | ___ | ___ |
| markdown-aware | ___ | ___ | ___ | ___ | ___ |

### What we learned
For markdown technical docs, heading-aware chunking dominates because headings are natural semantic boundaries. Fixed chunking is fine for prose, terrible for code blocks.

### 🚚 Courier takeaway
The post office can pre-sort by weight (fixed), by sentence, by topic, or by chapter heading — sorting by chapter heading is what keeps technical knowledge intact.

---

## Lab 18: Eval Thresholds — "How strict is the report card?"

**Config:** `EVAL_FAITHFULNESS_THRESHOLD` + `EVAL_KEYWORD_OVERLAP_PCT` (default: `0.5` / `0.5`)
**What it controls:** Pass/fail thresholds in the evaluator. Same answers, different verdicts.
**Hypothesis:** Strict thresholds expose low-quality answers that lax thresholds wave through; the answers don't change, only the score does.

### Setup
1. Set `EVAL_FAITHFULNESS_THRESHOLD=0.8` and `EVAL_KEYWORD_OVERLAP_PCT=0.7` in `.env`
2. Run the same 3 questions (Q1–Q3) and capture the eval report card
3. Repeat for each preset below

### Results table (fill in as you run)
| Value | Retrieval | Faithfulness | Latency (ms) | Cost (€) | Notes |
|---|---|---|---|---|---|
| strict (0.8/0.7) | ___ | ___ | ___ | ___ | ___ |
| default (0.5/0.5) | ___ | ___ | ___ | ___ | ___ |
| lax (0.3/0.3) | ___ | ___ | ___ | ___ | ___ |

### What we learned
Calibrate the evaluator before trusting it. A lax threshold makes everything look green and is the #1 way teams ship hallucination to prod. Pick thresholds against a human-labelled golden set.

### 🚚 Courier takeaway
The report card itself can be lenient or strict — the courier did the same trip, but a strict teacher fails the delivery for the smallest miss.

---

## Lab 19: LLM-as-Judge Evaluation — "Can a smarter LLM grade the courier's report card?"

**Config:** `EVAL_MODE` (default: `rule_based`)
**What it controls:** Whether evaluation uses Python rules (cheap, deterministic) or a second LLM call (expensive, semantic).
**Hypothesis:** Rule-based eval misses semantic hallucinations (the answer paraphrases something not in the chunks but uses the same keywords). LLM-as-judge catches them at ~$0.001/eval.

### Why this matters
Rule-based evaluation (`EVAL_MODE=rule_based`) splits the answer into sentences, extracts keywords, and checks if they appear in the retrieved chunks. It's free and instant — but it CANNOT detect when the courier paraphrases a hallucination using words that happen to be in the parcel.

LLM-as-judge (`EVAL_MODE=llm_judge`) sends the question, retrieved chunks, and answer to a second cheap LLM (e.g. Claude Haiku, GPT-4o-mini) with a structured rubric: "Score faithfulness 0–1. Did every claim come from the provided context? List any unsupported claims." It catches semantic hallucinations rules miss.

### Setup
1. Add `EVAL_MODE=rule_based` to `.env`
2. Pick a "judge" LLM in `.env`:
   - Local: `JUDGE_LLM_PROVIDER=ollama` + `JUDGE_LLM_MODEL=llama3.2`
   - AWS: `JUDGE_LLM_PROVIDER=bedrock` + `JUDGE_LLM_MODEL=anthropic.claude-haiku-...`
   - Azure: `JUDGE_LLM_PROVIDER=azure_openai` + `JUDGE_LLM_MODEL=gpt-4o-mini`
3. Implement the judge prompt (see template below)
4. Run the same 3 hard questions (Q1–Q3) with both modes
5. Compare scores

### The judge prompt template
```text
You are a strict evaluator of RAG answers. Given:
- QUESTION: {question}
- RETRIEVED_CONTEXT: {chunks}
- ANSWER: {answer}

Score the answer on:
1. faithfulness (0.0–1.0): Did every claim come from RETRIEVED_CONTEXT?
2. completeness (0.0–1.0): Did the answer use the relevant parts of RETRIEVED_CONTEXT?
3. relevance (0.0–1.0): Did the answer address the QUESTION?

Return strict JSON: {"faithfulness": 0.x, "completeness": 0.x, "relevance": 0.x, "unsupported_claims": ["..."]}
```

### Results table (fill in as you run)
| Question | Rule-based faithfulness | LLM-judge faithfulness | Divergence | Why? |
|---|---|---|---|---|
| Q1 (clean) | ___ | ___ | ___ | ___ |
| Q2 (paraphrased hallucination) | ___ | ___ | ___ | LLM-judge catches it; rules miss it |
| Q3 (out-of-scope) | ___ | ___ | ___ | Both should score low |

### Cost comparison
| Mode | Cost per eval | Latency added | Determinism |
|---|---|---|---|
| `rule_based` | €0 | ~1ms | ✅ Same input → same score |
| `llm_judge` (Haiku) | ~$0.001 | ~500–1500ms | ❌ May vary slightly across runs |
| `llm_judge` (GPT-4o) | ~$0.01 | ~1–3s | ❌ May vary |

### What we learned
Rule-based eval is the right default — it's free, fast, and catches obvious failures. LLM-as-judge is the right tool for the borderline cases that rule-based flags as `marginal`. Production pattern: run rule-based on every request, run LLM-judge only on samples flagged as marginal or on a daily nightly batch over the golden dataset. Never run LLM-judge on 100% of traffic — the cost adds up.

### 🚚 Courier takeaway
Rule-based eval is a clipboard-with-checkboxes the depot hand uses on every delivery. LLM-as-judge is the senior trainer who comes in once a week, reviews a sample of trips, and catches the subtle mistakes the checkboxes miss. You need both — but you can't afford the trainer at every door.
