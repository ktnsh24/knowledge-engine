# Endpoint Deep Dive: `/ingest/*` — the intake desk

> **Study order:** #20 · **Source:** [`src/routes/ingest.py`](../../../src/routes/ingest.py)
> · **Pipeline:** [`src/ingestion/scanner.py`](../../../src/ingestion/scanner.py),
> [`src/ingestion/graph_extractor.py`](../../../src/ingestion/graph_extractor.py)
> · **Stores written:** vector + graph (see the [Ingestion deep dive](../../ai-engineering/ingestion-pipeline-deep-dive.md)).

---

## Table of Contents

- [Endpoint summary](#endpoint-summary)
- [`POST /ingest/run` — kick off ingestion](#post-ingestrun--kick-off-ingestion)
- [`GET /ingest/status` — poll the stores](#get-ingeststatus--poll-the-stores)
- [Internal flow](#internal-flow)
- [`curl` examples](#curl-examples)
- [Error cases](#error-cases)
- [🫏 Donkey explainer — the intake desk](#-donkey-explainer--the-intake-desk)

---

## Endpoint summary

| Method | Path | Auth | Purpose | 🫏 Donkey |
|--------|------|------|---------|-----------|
| POST | `/ingest/run` | none | Schedule a background scan of all configured source repos; chunk every markdown file, embed the chunks into the vector store, and extract topics + relationships into the graph store | The intake desk — drop the day's letters; the back room starts pre-sorting in parallel while you walk away |
| GET | `/ingest/status` | none | Return the current chunk count and topic count from the two stores | A small window to count GPS-shelved parcels and paper-map towns without disturbing the back-room work |

Both routes are mounted under the `ingestion` tag in `src/main.py` with prefix
`/ingest`.

---

## `POST /ingest/run` — kick off ingestion

### Request schema

No request body. The route reads its parameters entirely from
[`src/config.py`](../../../src/config.py):

| Setting | Default | Effect |
|---------|---------|--------|
| `SOURCE_REPOS_PATH` | `../` | Root path the scanner walks |
| `SOURCE_REPOS` | `rag-chatbot,ai-gateway,ai-agent,ai-multi-agent,mcp-server,ai-engineering-field-guide` | Comma-list of repo folders under that root |
| `INCLUDE_PATTERNS` / `EXCLUDE_PATTERNS` | `**/*.md,**/*.txt` / node_modules, venv, etc. | File-path globbing |
| `RAG_CHUNK_SIZE` | 800 | Characters per chunk |
| `RAG_CHUNK_OVERLAP` | 100 | Character overlap between chunks |
| `CHUNK_STRATEGY` | `fixed` | `fixed` / `semantic` / `sentence` / `markdown-aware` (Tier-4 Lab 17) |

### Response schema

```json
{
  "status":  "started",
  "message": "Ingestion running in background"
}
```

The actual work runs in a FastAPI `BackgroundTasks` job — the HTTP response
returns immediately. Poll `GET /ingest/status` (or watch `structlog` output)
to see when it finishes.

---

## `GET /ingest/status` — poll the stores

### Request schema

No request body, no query parameters.

### Response schema

```json
{
  "chunks": 3142,
  "topics":  287
}
```

| Field | Type | Source |
|-------|------|--------|
| `chunks` | int | `vector_store.chunk_count()` — total documents in the GPS warehouse |
| `topics` | int | `graph_store.topic_count()` — total nodes on the paper map |

There is no per-repo breakdown today; if you need that, scan the structlog
output during the background run (`ingestion_started` and `ingestion_complete`
events).

---

## Internal flow

```text
client
  │  POST /ingest/run
  ▼
FastAPI middleware (CORS — wide open)
  │
  ▼
src/routes/ingest.py:run_ingestion(request, background_tasks)
  │   - reads vector_store, graph_store, llm from request.app.state
  │   - schedules _ingest_all(...) in BackgroundTasks
  │
  └──▶ returns {"status": "started"} immediately
       (HTTP request completes here)

       ── background ───────────────────────────────────────────────
       _ingest_all(vector_store, graph_store, llm)
         │
         ├── scan_repos()                                ← walks SOURCE_REPOS
         │
         └── for each path in files:
              │
              ├── chunk_document(path, RAG_CHUNK_SIZE,   ← src/ingestion/scanner.py
              │                  RAG_CHUNK_OVERLAP)
              │   ▼
              ├── vector_store.upsert(chunks)            ← embeds + stores
              │   ▼
              └── extract_and_store(text, graph_store,   ← LLM → topics + edges
                                    llm)                    src/ingestion/graph_extractor.py
       ── /background ──────────────────────────────────────────────
```

The status route is much shorter — a straight read against both stores.

---

## `curl` examples

```bash
# Kick off ingestion (returns immediately)
curl -X POST http://localhost:8200/ingest/run

# Poll until counts stop changing
watch -n 5 'curl -s http://localhost:8200/ingest/status | jq'
```

---

## Error cases

| Trigger | Response | 🫏 Donkey |
|---------|----------|-----------|
| `SOURCE_REPOS_PATH` does not exist on disk | Background task logs an error per missing repo and returns 0 chunks; the HTTP request still returns `started` | Intake desk accepts the empty mailbag — only the back-room sorter notices there were no letters |
| `vector_store.upsert` raises (Chroma down, DynamoDB throttling, AI Search throttling) | Logged via `structlog`; partial progress is preserved (each file is upserted independently) | One shelf in the warehouse is locked; remaining files keep landing on the open shelves |
| LLM call inside `extract_and_store` fails (Ollama not running, Bedrock timeout) | Per-file error logged; topic extraction skipped for that file but chunks still landed in vectors | The cartographer is out sick; the warehouse keeps stocking but no new towns get pencilled in for that letter |
| `GET /ingest/status` while a store is uninitialised | The store-method exception bubbles up as a 500 | The window operator can't reach the back room; the doorman returns a hard error rather than a guess |
| Two `POST /ingest/run` calls in quick succession | Both are accepted; both schedule independent background tasks | Two intake clerks running the same letters in parallel — duplicate uploads are deduplicated by the vector store's id key (`chunk.id`) |

The route does not currently prevent concurrent ingestion runs — if you need
that guard, add a module-level `asyncio.Lock`.

---

## 🫏 Donkey explainer — the intake desk

The intake desk is the loudest door in the stable. You drop a stack of fresh
letters in the basket and walk away — the clerk at the desk does not sort
them in front of you. Behind the wall, the post office walks the whole pile,
cuts each letter into pages of 800 characters with a 100-character overlap,
GPS-stamps every page and slides it onto a warehouse shelf, and then asks the
cartographer (the LLM) to read each letter and pencil any new towns or roads
onto the paper map. While that is happening you can knock on the small window
next door (`/ingest/status`) and the operator will shout back the current
shelf count and town count. When both numbers stop growing, the back-room
work is done and the next chat will use the freshly stocked warehouse and the
freshly redrawn map.
