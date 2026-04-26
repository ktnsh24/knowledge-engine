# Deep Dive: The Chat Engine — `src/chat/engine.py`

> **Study order:** #15 · **Difficulty:** ★★★★★ — small file (≈150 lines) but it
> is where the GraphRAG pattern earns its keep: vector search + graph traversal
> + gap detection + LLM, composed around a single `answer()` call.
>
> **File:** [`src/chat/engine.py`](../../src/chat/engine.py) · **Calls into:**
> [Vector store](vectorstore-interface-deep-dive.md), [Graph store](graphstore-interface-deep-dive.md),
> [LLM](llm-interface-deep-dive.md), [Gap detector](gap-detector-deep-dive.md),
> [Candidate store](feedback-loop-deep-dive.md#candidate-store) · **Exposed by:**
> [`POST /chat`](../architecture-and-design/api-routes/eval-endpoint-explained.md) (see also the wiki/feedback routes).

---

## Table of Contents

- [Why this file matters](#why-this-file-matters)
- [The pipeline at a glance](#the-pipeline-at-a-glance)
- [Step 1 — vector search](#step-1--vector-search)
- [Step 2 — graph expansion](#step-2--graph-expansion)
- [Step 3 — gap detection and confidence](#step-3--gap-detection-and-confidence)
- [Step 4 — routing: grounded vs fallback](#step-4--routing-grounded-vs-fallback)
- [Composing the prompt context](#composing-the-prompt-context)
- [The response object](#the-response-object)
- [How candidates and feedback close the loop](#how-candidates-and-feedback-close-the-loop)
- [Performance notes — what runs in series, what doesn't](#performance-notes--what-runs-in-series-what-doesnt)
- [DE parallel — orchestrator over fan-out fan-in](#de-parallel--orchestrator-over-fan-out-fan-in)
- [🚚 Courier explainer — the dispatcher's office](#-courier-explainer--the-dispatchers-office)
- [Self-test questions](#self-test-questions)
- [What to read next](#what-to-read-next)

---

## Why this file matters

The chat engine is the **only** component that touches every other AI subsystem
in the project. The vector store, the graph store, the LLM, the gap detector,
and the candidate store all exist for one reason: so that `ChatEngine.answer()`
can compose them into one honest reply. Read this file and you understand the
whole runtime data flow of the knowledge engine.

It is also where two project-defining design choices live in code:

1. **Vector AND graph, not vector OR graph.** Plain RAG asks the GPS warehouse
   for the nearest shelves and stops there. The chat engine asks the warehouse
   *and* walks two hops on the paper map to pull in connected towns the question
   never named.
2. **Honesty before convenience.** When the docs do not cover the question, the
   engine does not silently let the LLM make things up. It tags the confidence
   level (`HIGH` / `PARTIAL` / `GAP`), saves the gap to disk, and routes a
   `GAP` answer through the fallback prompt so the response carries a warning
   and a candidate-id the user can review.

---

## The pipeline at a glance

```text
ChatRequest ── question
    │
    ▼
1. vector_store.search(question, top_k)              ← GPS warehouse → candidate chunks
    │
    ▼
2. for each chunk topic_id (max 3):                  ← paper map →
        graph_store.get_connected_topics(tid, hops=2)  expand to neighbour towns
    │
    ▼
3. gap_detector.assess_confidence(...)               ← HIGH / PARTIAL / GAP
    │
    ▼
4a. HIGH or PARTIAL → llm.complete(strict prompt + chunks + neighbour topics)
4b. GAP             → llm.complete(FALLBACK prompt, no docs)
                      → candidate_store.save_candidate(question, answer, gap_id)
    │
    ▼
ChatResponse(answer, sources, topics, confidence, gap_id, candidate_id, latency_ms)
```

The whole thing fits in 150 lines because the heavy lifting is delegated — the
engine is glue, not algorithm.

---

## Step 1 — vector search

```python
chunks = await self.vector_store.search(request.question, top_k=settings.rag_top_k)
chunk_texts = [c.text for c in chunks]
sources = list({c.source_file for c in chunks})
```

`top_k` comes from `RAG_TOP_K` (default 5 — see [Tier-1 Lab 3 in the
labs index](../hands-on-labs/how-to-read-the-labs.md)). Fewer = focused & cheap;
more = noisier and dilutes the average retrieval score.

| Field | Where it goes | 🚚 Courier |
|-------|---------------|-----------|
| `chunks[i].text` | Joined later as the LLM context block | The pages the courier actually loads into the parcel for the trip |
| `chunks[i].source_file` | Returned to the caller as `sources` | The shelf labels the courier shows the supervisor so they can audit the quote |
| `chunks[i].topic_ids` | Used in step 2 to seed graph expansion | The town stamps on each page that tell the courier which neighbours to ask the cartographer about |
| `chunks[0].embedding[0]` | Used (loosely) as `top_score` for the gap detector | The clarity score on the brightest GPS coordinate the warehouse returned |

> ⚠️ The `top_score` heuristic uses `chunks[0].embedding[0]` — the first dimension
> of the top chunk's embedding — as a placeholder until the vector store wraps
> chunks in a real `(score, chunk)` tuple. This is the documented temporary
> shortcut in the file; the gap detector compensates by also weighing
> `chunk_count` and `topic_count`.

---

## Step 2 — graph expansion

```python
topic_ids = list({tid for c in chunks for tid in c.topic_ids})
connected_topics = []
for tid in topic_ids[:3]:
    neighbours = await self.graph_store.get_connected_topics(tid, max_hops=2)
    connected_topics.extend(neighbours)
```

Three rules baked into these four lines:

1. **De-duplicate topic_ids first** — many chunks share topics, no point asking
   the cartographer the same question twice.
2. **Cap at 3 seed topics** — the cost of `get_connected_topics` is one round
   trip per call; capping keeps p95 latency predictable.
3. **`max_hops=2`** — far enough to surface "embeddings ↔ vector store" when the
   question only mentions "RAG", close enough to avoid pulling the whole graph.

The neighbour topic *names* (not chunks) are later glued into the prompt under a
`RELATED TOPICS (from knowledge graph)` header — small payload, big effect on
how the LLM frames the answer.

---

## Step 3 — gap detection and confidence

```python
top_score = chunks[0].embedding[0] if chunks and chunks[0].embedding else 0.0
gap = self.gap_detector.assess_confidence(
    question=request.question,
    top_retrieval_score=top_score,
    chunk_count=len(chunks),
    topic_count=len(connected_topics),
)
if gap.confidence != ConfidenceLevel.HIGH:
    await self.gap_detector.save_gap(gap)
```

The detector returns one of:

| Level | Trigger | Routing |
|-------|---------|---------|
| `HIGH` | `top_score ≥ 0.70` AND `chunk_count ≥ 2` | Grounded answer, no gap saved |
| `PARTIAL` | `top_score ≥ 0.40` OR `chunk_count ≥ 1` | Grounded answer + gap saved with `🟡 PARTIAL` label |
| `GAP` | Neither threshold met | Fallback answer + gap saved with `🔴 GAP` label + candidate created |

Full threshold logic lives in [`src/chat/gap_detector.py`](../../src/chat/gap_detector.py)
and is documented in the [Gap Detector deep dive](gap-detector-deep-dive.md).

---

## Step 4 — routing: grounded vs fallback

The `if gap.confidence == ConfidenceLevel.GAP:` branch is the one that makes
this engine different from a plain RAG chain.

| Branch | System prompt | Context passed | Side effect | 🚚 Courier |
|--------|---------------|----------------|-------------|-----------|
| `HIGH` | `get_system_prompt(settings.system_prompt_mode)` (strict by default) | Joined chunks + related-topics header | None — pure read | The courier writes from the loaded parcel and signs the shipping manifest normally |
| `PARTIAL` | Same as HIGH but with an extra `[NOTE: Coverage for this question is partial...]` line appended to the context | Joined chunks + related-topics + the partial-coverage notice | Gap saved to `wiki/gaps/unanswered.md` with 🟡 label | The courier writes from a half-empty parcel and is told to be explicit about what it does and doesn't know |
| `GAP` | `FALLBACK_SYSTEM_PROMPT` — forces a `⚠️ This answer is from LLM training knowledge` banner | Empty string (`context=""`) | Gap saved with 🔴 label AND candidate saved to `wiki/candidates/pending-review.md` | The courier stamps the parcel with a warning, delivers it from memory, and leaves a copy on the supervisor's clipboard for promotion or rejection |

`temperature=settings.llm_temperature` is passed through every call (default
0.1 — the lower it is, the more reproducible the courier's handwriting).

---

## Composing the prompt context

The grounded branch builds the prompt like this:

```python
topic_context = ""
if topic_names:
    topic_context = f"\n\nRELATED TOPICS (from knowledge graph): {', '.join(topic_names)}"

gap_notice = ""
if gap.confidence == ConfidenceLevel.PARTIAL:
    gap_notice = (
        "\n\n[NOTE: Coverage for this question is partial. "
        "Be explicit about what you do and don't know from the context.]"
    )

context = "\n\n---\n\n".join(chunk_texts) + topic_context + gap_notice
```

Three things to notice:

| Detail | Why it matters | 🚚 Courier |
|--------|---------------|-----------|
| `\n\n---\n\n` between chunks | Markdown horizontal rule; keeps the LLM from blending chunks into one stream and losing `source_file` provenance | A divider page between each delivery doc so the courier doesn't smear two parcels' contents into one note |
| Graph topics appended as a header, not interleaved | The LLM treats them as hint metadata rather than as quotable content — fewer hallucinations of "the docs say X about Y" when Y came from the graph | A separate sticky note on the parcel listing neighbour towns to mention; not pages it can quote verbatim |
| Partial-coverage notice goes at the end of context, not in the system prompt | Per-request flag — the system prompt stays the same across requests so caching and eval comparisons stay valid | A trip-specific warning slip clipped onto today's parcel only, not a permanent change to the desk rules |

---

## The response object

`ChatResponse` (defined in [`src/models.py`](../../src/models.py)) carries
everything the UI and the evaluator need:

| Field | Source | 🚚 Courier |
|-------|--------|-----------|
| `answer` | LLM `complete()` output | The shipping manifest the courier hands over to the supervisor |
| `courier_analogy` | Extracted via `_extract_courier()` from the answer | The 🚚 line the courier is contractually required to write at the end of every note |
| `sources` | De-duplicated `source_file` list from chunks | The shelf labels of every page the courier actually carried — provenance for the audit |
| `topics` | Names from `connected_topics` | The neighbour towns the cartographer flagged as relevant |
| `retrieval_score` | `top_score` heuristic from step 1 | The brightness of the warehouse's best GPS hit; fed into the gap detector |
| `confidence` / `is_gap` / `gap_id` / `gap_reason` / `gap_suggestion` | From the `KnowledgeGap` returned by the detector | The honesty stamp — green/yellow/red plus the supervisor's instructions for closing the gap |
| `answer_source` | `DOCS` / `DOCS_PARTIAL` / `LLM_KNOWLEDGE` | A label saying whether the courier wrote from the parcel, from a half-empty parcel, or from memory |
| `candidate_id` | Set only on `GAP` answers | The clipboard ticket number for the off-road note that needs human review |
| `latency_ms` | `int((time.monotonic() - start) * 1000)` | The trip duration on the courier's tachograph for this single delivery |
| `provider` | `get_settings().cloud_provider.value` | Which depot handled the trip — local barn, AWS depot, or Azure hub |

`_extract_courier()` is a small helper that finds the first `🚚` line in the
answer and returns it as a separate field, so the UI can render it as a callout
even if the LLM buried it mid-paragraph.

---

## How candidates and feedback close the loop

The `GAP` branch ends with:

```python
candidate = await self.candidate_store.save_candidate(
    question=request.question,
    answer=answer_text,
    courier_analogy=_extract_courier(answer_text),
    gap_id=gap.id,
)
candidate_id = candidate.id
```

The candidate sits in `wiki/candidates/pending-review.md` until a human hits
`POST /wiki/candidates/{id}/promote`, which appends the Q&A to
`wiki/feedback/verified-answers.md`. The next `POST /ingest/run` chunks and
embeds that file like any other doc — so the next time the same question is
asked, the vector store returns those chunks and the gap closes itself.

The 👍/👎 path through `POST /feedback/` follows the same shape — see the
[Feedback Loop deep dive](feedback-loop-deep-dive.md) for the full circuit.

---

## Performance notes — what runs in series, what doesn't

The current implementation runs all four steps sequentially. There are two
intentional `await` points where parallelism *could* be added later:

| Pair | Could be parallel? | Why it isn't today |
|------|--------------------|--------------------|
| `vector_store.search` and `graph_store.get_connected_topics` | No — the second one needs `topic_ids` from the first | The graph expansion is seeded by chunks; without chunks there is nothing to expand |
| Multiple `get_connected_topics` calls (one per topic_id, capped at 3) | Yes — these are independent | Kept sequential for readability and predictable rate-limit behaviour against Neo4j / DynamoDB / Cosmos; promote to `asyncio.gather` if p95 ever becomes a problem |

The `time.monotonic()` brackets the whole `answer()` call, so `latency_ms` in
the response is end-to-end including LLM time — the dominant cost for cloud
providers.

---

## DE parallel — orchestrator over fan-out fan-in

If you have written Airflow / Prefect / Dagster pipelines, the chat engine is a
**short, request-scoped orchestrator**:

| Pipeline concept | Chat engine equivalent |
|------------------|------------------------|
| Source operator | `vector_store.search` and `graph_store.get_connected_topics` |
| Branching operator (`BranchPythonOperator`) | The `if gap.confidence == GAP:` switch |
| Sink + audit table | `gap_detector.save_gap` + `candidate_store.save_candidate` |
| Run metadata | `ChatResponse.latency_ms`, `provider`, `confidence` |

The interesting twist is that the "audit table" rows (gaps and candidates)
become *training data* for the next ingest — the orchestrator's failures feed
its own future success. That self-improving loop is the bonus you do not get in
a one-shot DAG.

---

## 🚚 Courier explainer — the dispatcher's office

The chat engine is the dispatcher who briefs the courier before every trip.
First the dispatcher walks to the GPS warehouse and pulls the five most
relevant pages off the shelves matching the customer's question. Then the
dispatcher walks to the paper map on the wall, looks at the town stamps on
those pages, and traces two hops in every direction to find neighbour towns
worth mentioning. Then the auditor (gap detector) eyeballs the haul and stamps
it green, yellow, or red.

On a green stamp the dispatcher hands the courier the parcel of pages, the
sticky note of neighbour towns, and the strict desk rules — write only what is
in there. On a yellow stamp the same briefing happens but with an extra slip
that says "be honest about what you don't know from these pages." On a red
stamp the dispatcher takes the empty parcel away, hands the courier the
fallback rules — "you may write from memory, but stamp the parcel with a
warning" — and drops a copy of the result on the supervisor's clipboard for
promotion or rejection. Every trip is logged with timing, stamp colour, and
parcel contents so tomorrow's report card has something to score.

---

## Self-test questions

1. Which two arguments to `gap_detector.assess_confidence` come from the
   *graph* expansion, and which come from the *vector* search?
2. Why does the engine cap the seed topic ids at 3 before calling
   `get_connected_topics` instead of expanding from every topic in every chunk?
3. The `GAP` branch passes `context=""` to the LLM. What stops the LLM from
   silently inventing source citations in that mode?
4. What is the difference, end-to-end, between an answer with `confidence=PARTIAL`
   and an answer with `confidence=HIGH` from the user's point of view?
5. If a 👍 promotes a candidate but the user never runs `POST /ingest/run`
   afterwards, will the next identical question still hit the `GAP` branch?
   Why?

---

## What to read next

- [Gap Detector Deep Dive](gap-detector-deep-dive.md) — the thresholds and
  storage format behind step 3.
- [Feedback Loop Deep Dive](feedback-loop-deep-dive.md) — what happens after a
  `GAP` answer is reviewed.
- [LLM Interface](llm-interface-deep-dive.md) — the contract `complete()` calls
  into.
- [Vector Store Interface](vectorstore-interface-deep-dive.md) and
  [Graph Store Interface](graphstore-interface-deep-dive.md) — the two
  retrieval layers the engine composes.
- [Evaluation Framework Deep Dive](evaluation-framework-deep-dive.md) — how the
  same `ChatResponse` is scored across nine metrics.
