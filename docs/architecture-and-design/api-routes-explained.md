# API Routes — Overview

> **Study order:** #19 · One-page index of every HTTP endpoint the FastAPI
> server exposes, with a link to the dedicated deep dive for each.
>
> **Source:** [`src/main.py`](../../src/main.py) (router wiring) ·
> [`src/routes/`](../../src/routes/) (one file per tag) · **Models:**
> [`src/models.py`](../../src/models.py).

---

## Server basics

| Property | Value |
|----------|-------|
| Framework | FastAPI |
| Default port | `8200` (overridable via `API_PORT`) |
| Auth | None today (`API_KEYS_ENABLED=false` is the default and no middleware checks the key yet) |
| CORS | Wide-open in `src/main.py` — `allow_origins=["*"]`, all methods, all headers |
| Lifespan | `src/main.py:lifespan` constructs the LLM, vector store, graph store, chat engine, wiki generator, and feedback processor, attaching each to `app.state` |

Run locally with:

```bash
poetry run uvicorn src.main:app --port 8200 --reload
```

OpenAPI docs are served by FastAPI at `http://localhost:8200/docs`.

---

## All endpoints at a glance

| Method | Path | Tag | Component(s) called | Doc | 🫏 Donkey |
|--------|------|-----|---------------------|-----|-----------|
| GET | `/health/` | health | `vector_store.chunk_count`, `graph_store.topic_count` | [Health](api-routes/health-endpoint-explained.md) | The stable doorman shouting back chunk count, topic count, and which writer is on shift today |
| POST | `/chat/` | chat | `chat_engine.answer` (full GraphRAG pipeline) | (in [Chat Engine deep dive](../ai-engineering/chat-engine-deep-dive.md)) | The customer service window — push a question through, get a graded delivery note back |
| POST | `/ingest/run` | ingestion | Background task: `scan_repos`, `chunk_document`, `vector_store.upsert`, `extract_and_store` | [Ingest](api-routes/ingest-endpoint-explained.md) | The intake desk — drop the day's letters, the post office starts pre-sorting in the back room |
| GET | `/ingest/status` | ingestion | `vector_store.chunk_count`, `graph_store.topic_count` | [Ingest](api-routes/ingest-endpoint-explained.md) | Window into the back room to count parcels on the GPS shelves and towns on the paper map |
| POST | `/wiki/rebuild` | wiki | `wiki_gen.generate_all` | [Wiki](api-routes/wiki-endpoint-explained.md) | Triggers the brochure printer to reprint one tourist guide per known town |
| GET | `/wiki/topics` | wiki | `graph_store.get_all_topics` | [Wiki](api-routes/wiki-endpoint-explained.md) | The cartographer's full list of every town currently on the paper map |
| GET | `/wiki/graph` | wiki | `graph_store.get_full_graph` | [Wiki](api-routes/wiki-endpoint-explained.md) | A dump of the whole paper map — every town and every road between them |
| GET | `/wiki/gaps` | wiki | `gap_detector.list_gaps`, `gap_detector.gap_summary` | [Wiki](api-routes/wiki-endpoint-explained.md) | The wall of red and yellow flags — every trip the auditor has flagged as needing more docs |
| DELETE | `/wiki/gaps/{gap_id}` | wiki | `gap_detector.resolve_gap` | [Wiki](api-routes/wiki-endpoint-explained.md) | The supervisor crosses a flagged trip off the wall after the missing road has been built |
| GET | `/wiki/candidates` | wiki | `candidate_store.list_candidates`, `candidate_store.summary` | [Wiki](api-routes/wiki-endpoint-explained.md) | The clipboard of off-road notes the donkey wrote from memory, awaiting promote/discard |
| POST | `/wiki/candidates/{id}/promote` | wiki | `candidate_store.promote` (writes to `verified-answers.md`) | [Wiki](api-routes/wiki-endpoint-explained.md) | Supervisor approves the off-road note as a real road; it gets framed and re-shelved on the next pre-sort |
| POST | `/wiki/candidates/{id}/discard` | wiki | `candidate_store.discard` | [Wiki](api-routes/wiki-endpoint-explained.md) | Supervisor rejects the off-road note; the gap stays open on the wall |
| POST | `/feedback/` | feedback | `feedback_proc.process` (👍 → verified-answers, 👎 → golden-questions) | [Feedback](api-routes/feedback-endpoint-explained.md) | The trip-debrief window — drop a 👍/👎 verdict on a delivery and the next ingest absorbs the consequence |
| POST | `/eval/run` | evaluation | `KnowledgeEngineEvaluator` + `run_evaluation` over `golden-questions.yaml` | [Eval](api-routes/eval-endpoint-explained.md) | The road inspector's bell — pull it and the nine clipboards get filled in for every standard test delivery |

---

## How to read a per-route doc

Every per-route doc in `api-routes/` follows the same shape so you can scan
them quickly:

1. Endpoint summary table (method, path, auth, purpose, 🫏 column)
2. Request schema — fields, types, required flags
3. Response schema — fields, types
4. Internal flow — middleware → route handler → component(s) → response
5. One copy-pasteable `curl` example
6. Error cases table with 🫏 column
7. 🫏 Donkey explainer that names the specific endpoint

---

## 🫏 Donkey explainer — the stable's front door signs

The API routes are the signs above every door in the stable. The intake desk
(`/ingest/`) is where you drop fresh letters off; the customer service window
(`/chat/`) is where you push a question through and get a delivery note back;
the trip-debrief window (`/feedback/`) is where supervisors pin verdicts to
yesterday's deliveries; the map room window (`/wiki/`) is where you peek at
the cartographer's paper map, the brochure rack, and the wall of red flags;
the inspector's bell (`/eval/`) is what you ring when you want every standard
test delivery driven and graded; the doorman's window (`/health/`) is for
checking the stable is awake before you start. Same building, six doors —
walk to whichever one matches the job you came to do.
