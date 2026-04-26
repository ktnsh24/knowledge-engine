# Endpoint Deep Dive: `/wiki/*` — the map room

> **Study order:** #21 · **Source:** [`src/routes/wiki.py`](../../../src/routes/wiki.py)
> · **Components:** [Wiki Generator](../../ai-engineering/wiki-generator-deep-dive.md),
> [Gap Detector](../../ai-engineering/gap-detector-deep-dive.md),
> [Candidate Store](../../ai-engineering/feedback-loop-deep-dive.md#circuit-2--candidates-from-gap-answers).

---

## Table of Contents

- [Endpoint summary](#endpoint-summary)
- [Topic + graph + rebuild routes](#topic--graph--rebuild-routes)
- [Gap routes](#gap-routes)
- [Candidate routes](#candidate-routes)
- [Internal flow](#internal-flow)
- [`curl` examples](#curl-examples)
- [Error cases](#error-cases)
- [🚚 Courier explainer — the map room window](#-courier-explainer--the-map-room-window)

---

## Endpoint summary

| Method | Path | Auth | Purpose | 🚚 Courier |
|--------|------|------|---------|-----------|
| POST | `/wiki/rebuild` | none | Regenerate every per-topic markdown article + the index from the current graph + vectors | Reprint every brochure in the rack from today's paper map and warehouse contents |
| GET | `/wiki/topics` | none | Return every `Topic` in the graph (id, name, description, source repos) | Read the cartographer's full town register through the window |
| GET | `/wiki/graph` | none | Return the entire `KnowledgeGraph` (topics + relationships) | Hand the whole paper map out the window for inspection |
| GET | `/wiki/gaps` | none | Return current gap summary + per-gap entries; optional `?status=open\|resolved` filter | Read every red and yellow flag the auditor has pinned to the wall |
| DELETE | `/wiki/gaps/{gap_id}` | none | Mark a gap as `resolved`; preserves the row, stamps `resolved_at` | Supervisor crosses a flag off the wall once the missing road is built |
| GET | `/wiki/candidates` | none | Return every off-doc LLM answer awaiting review; default `?status=pending` | Read every off-road note clipped to the supervisor's clipboard |
| POST | `/wiki/candidates/{id}/promote` | none | Append the candidate's Q&A to `verified-answers.md`; flip status to `promoted` | Promote an off-road note to a real road; the next pre-sort indexes it |
| POST | `/wiki/candidates/{id}/discard` | none | Flip status to `discarded`; gap stays open | Reject an off-road note; the red flag stays on the wall |

The `wiki.router` is mounted with prefix `/wiki` and tag `wiki` in
`src/main.py`.

---

## Topic + graph + rebuild routes

### `POST /wiki/rebuild`

| Field | Value |
|-------|-------|
| Body | none |
| Calls | `app.state.wiki_gen.generate_all()` (full deep dive: [Wiki Generator](../../ai-engineering/wiki-generator-deep-dive.md)) |
| Response | `{ "status": "ok", "pages_generated": <int> }` |
| Errors | Any exception in the generator surfaces as `500` with `detail=str(e)` |

### `GET /wiki/topics`

| Field | Value |
|-------|-------|
| Body | none |
| Calls | `app.state.graph_store.get_all_topics()` |
| Response | `{ "topics": [Topic, ...] }` where each item is a `Topic.model_dump()` (id, name, description, source_repos, source_files, created_at, updated_at) |

### `GET /wiki/graph`

| Field | Value |
|-------|-------|
| Body | none |
| Calls | `app.state.graph_store.get_full_graph()` |
| Response | A `KnowledgeGraph.model_dump()` — `{ "topics": [...], "relationships": [...] }` |
| Notes | Heavy on a large graph — paginate yourself by walking topics first, then querying neighbours |

---

## Gap routes

### `GET /wiki/gaps?status=open|resolved`

| Field | Value |
|-------|-------|
| Query | `status` (optional) — filters by `open` or `resolved` |
| Calls | `_gap_detector.list_gaps(status_filter=status)` + `_gap_detector.gap_summary()` |
| Response | `{ "summary": {...}, "gaps": [KnowledgeGap, ...] }` — see the [Gap Detector deep dive](../../ai-engineering/gap-detector-deep-dive.md#the-summary-panel) for the `summary` shape |

### `DELETE /wiki/gaps/{gap_id}`

| Field | Value |
|-------|-------|
| Path | `gap_id` (8-char hex) |
| Calls | `_gap_detector.resolve_gap(gap_id)` |
| Response on success | `{ "status": "resolved", "gap_id": "<id>" }` |
| Response on miss | `404` with `detail="Gap '<id>' not found"` |

The detector instance is created at module import (`_gap_detector =
GapDetector()`) — same files on disk are read by every request.

---

## Candidate routes

### `GET /wiki/candidates?status=pending|promoted|discarded`

| Field | Value |
|-------|-------|
| Query | `status` (optional, default `pending`) |
| Calls | `_candidate_store.list_candidates(status_filter=status)` + `_candidate_store.summary()` |
| Response | `{ "summary": {pending, promoted, discarded, total}, "candidates": [WikiCandidate, ...] }` |

### `POST /wiki/candidates/{candidate_id}/promote`

| Field | Value |
|-------|-------|
| Path | `candidate_id` (8-char hex) |
| Calls | `_candidate_store.promote(candidate_id)` — appends Q&A to `wiki/feedback/verified-answers.md`, flips status to `promoted`, stamps `promoted_at` |
| Response on success | `{ "status": "promoted", "candidate_id": "...", "next_step": "Run POST /ingest/run to absorb this answer into the knowledge base" }` |
| Response on miss | `404` with `detail="Candidate '<id>' not found or not pending"` |

### `POST /wiki/candidates/{candidate_id}/discard`

| Field | Value |
|-------|-------|
| Path | `candidate_id` |
| Calls | `_candidate_store.discard(candidate_id)` — flips status to `discarded`, leaves the gap open |
| Response on success | `{ "status": "discarded", "candidate_id": "..." }` |
| Response on miss | `404` |

---

## Internal flow

```text
client
  │  any /wiki/* request
  ▼
FastAPI middleware (CORS)
  │
  ▼
src/routes/wiki.py route handler
  │
  ├── topic / graph / rebuild  → app.state.graph_store / app.state.wiki_gen
  │
  ├── gaps                     → module-level _gap_detector  (reads/writes wiki/gaps/*)
  │
  └── candidates               → module-level _candidate_store
                                  ├── list / summary  → reads wiki/candidates/*.jsonl
                                  ├── promote         → writes wiki/feedback/verified-answers.md
                                  └── discard         → flips status in candidates.jsonl
```

The two module-level singletons are intentional — gaps and candidates are
file-backed, so multiple route invocations against the same files just need
shared `Path` handles, not shared in-memory state.

---

## `curl` examples

```bash
# Reprint every brochure
curl -X POST http://localhost:8200/wiki/rebuild

# Read the full town register
curl http://localhost:8200/wiki/topics | jq '.topics | length'

# Read open gaps
curl 'http://localhost:8200/wiki/gaps?status=open' | jq '.summary'

# Close a gap by id
curl -X DELETE http://localhost:8200/wiki/gaps/ab12cd34

# List pending candidates and promote one
curl 'http://localhost:8200/wiki/candidates?status=pending' | jq '.candidates[0]'
curl -X POST http://localhost:8200/wiki/candidates/ab12cd34/promote
```

---

## Error cases

| Trigger | Response | 🚚 Courier |
|---------|----------|-----------|
| `POST /wiki/rebuild` while no topics exist (graph is empty) | `200` with `pages_generated: 0` | The brochure printer ran but had no town list, so no brochures were printed |
| `POST /wiki/rebuild` while LLM is unreachable | `500` with `detail=<exception message>` | The writer at the desk is unavailable; the printer halts and shouts the reason out the window |
| `DELETE /wiki/gaps/<unknown id>` | `404` `Gap '<id>' not found` | Supervisor tried to cross off a flag that was never on the wall |
| `POST /wiki/candidates/<id>/promote` on a candidate already promoted or discarded | `404` `Candidate '<id>' not found or not pending` | Off-road note already framed (or already binned) — cannot promote it twice |
| `GET /wiki/graph` against a very large graph | `200` but a slow response and a heavy JSON payload | Handing the entire paper map out the window — fine for small maps, painful for large ones |
| Underlying graph/vector store unreachable | `500` from the store call | The map room is closed; the window operator returns the storeroom's actual error |

---

## 🚚 Courier explainer — the map room window

The wiki window is the wall of the depot that lets you see the cartographer's
work without going inside. Through the topic window you can read every town
the cartographer has registered; through the graph window you can pull the
entire paper map out for inspection; through the rebuild lever you can ask
the brochure printer to reprint a tourist guide for every town from the
current map and warehouse contents. To the right of the rack are two extra
windows: the wall of red and yellow flags listing every trip the auditor
flagged as needing more docs, and the supervisor's clipboard with the off-road
notes the courier wrote from memory. You can promote good clipboard notes
(they get framed and re-shelved on the next pre-sort) or discard the bad ones
(the red flag stays). The whole map room is read-mostly — none of these
endpoints write to the corpus directly except `promote`, and even then the
real work happens on the next `/ingest/run`.
