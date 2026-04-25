# Deep Dive: Ingestion Pipeline

> **Study order:** #7 · **Difficulty:** ★★★☆☆
>
> **Files:** [`src/ingestion/scanner.py`](../../src/ingestion/scanner.py), [`src/ingestion/graph_extractor.py`](../../src/ingestion/graph_extractor.py)
>
> **Prerequisite:** [#2 — GraphRAG Concepts](graphrag-concepts.md), [#3 — Architecture](../architecture.md)
>
> **Companion:** [Vector Store Interface](vectorstore-interface-deep-dive.md), [Graph Extractor Deep Dive](graph-extractor-deep-dive.md)

---

## Table of Contents

- [Why This Pipeline Exists](#why-this-pipeline-exists)
- [End-to-End Flow](#end-to-end-flow)
- [Stage 1 — Scanner: Walking the Repos](#stage-1--scanner-walking-the-repos)
- [Stage 2 — Chunker: Cutting Each File](#stage-2--chunker-cutting-each-file)
- [Stage 3 — Vector Upsert: Embedding + Storing](#stage-3--vector-upsert-embedding--storing)
- [Stage 4 — Graph Extraction: Topics + Relationships](#stage-4--graph-extraction-topics--relationships)
- [Environment Variables That Control Ingestion](#environment-variables-that-control-ingestion)
- [Failure Modes and Recovery](#failure-modes-and-recovery)
- [What Ingestion Does NOT Do](#what-ingestion-does-not-do)
- [Self-Test Questions](#self-test-questions)

---

## Why This Pipeline Exists

Plain RAG ingestion ends with "embed the chunks, store the vectors". GraphRAG ingestion does that **and** extracts a typed graph from the same text in a single pass, so the chat engine can later answer with `vector_hits + graph_neighbours` instead of vectors alone.

This doc covers the part that runs *before* anyone asks a question — the post office pre-sort.

| Concept | What it produces | 🫏 Donkey |
|---------|------------------|-----------|
| Scanner | A list of markdown/text file paths across all configured repos | The mail clerk walking every shelf in every stable across the yard, copying down every letter that needs delivering |
| Chunker | Overlapping `DocumentChunk` records with nearest-heading metadata | The pre-sort clerk slicing each long letter into envelopes the donkey can fit into one backpack pocket |
| Vector upsert | Each chunk embedded and stored in the GPS warehouse | The clerk stamping every envelope with GPS coordinates so the donkey can find it later by location, not name |
| Graph extraction | Topics + relationships pulled from the chunk text by the LLM | The town-cartographer reading every envelope and pencilling new towns and roads onto the official paper map |

- 🫏 **Donkey:** Ingestion is the post office pre-sort *and* the cartographer's afternoon shift, both happening at the same desk so the donkey has a full GPS warehouse and a full paper map before anyone asks for a delivery.

---

## End-to-End Flow

```
SOURCE_REPOS_PATH (e.g. ../)
        │
        ▼
┌─────────────────────┐
│ scan_repos()        │  ← src/ingestion/scanner.py
│ glob include_patterns│
│ skip exclude_patterns│
└─────────┬───────────┘
          │ list[Path]
          ▼
┌─────────────────────┐
│ chunk_document()    │  ← src/ingestion/scanner.py
│ word-window split   │
│ + nearest heading   │
└─────────┬───────────┘
          │ list[DocumentChunk]
          ├──────────────────────────┐
          ▼                          ▼
┌─────────────────────┐   ┌─────────────────────────┐
│ vector_store.upsert │   │ extract_and_store()     │
│ (embed + write)     │   │ (LLM → topics + edges)  │
│ chroma / dynamodb / │   │ → graph_store.upsert_*  │
│ azure_search        │   │ neo4j / dynamodb / cosmos│
└─────────────────────┘   └─────────────────────────┘
```

Both stores are written from the **same chunk stream**. Nothing forces them to be in lock-step transactionally — if graph extraction fails for a chunk, the vector for that chunk still lands. This is by design; see [Failure Modes](#failure-modes-and-recovery).

- 🫏 **Donkey:** One pile of envelopes goes through two stations in parallel — GPS-stamping at the warehouse desk and town-pencilling at the cartographer's desk. If the cartographer drops one, the warehouse copy is still on the shelf.

---

## Stage 1 — Scanner: Walking the Repos

`scan_repos()` (lines 13–33 of `scanner.py`) walks every entry in `SOURCE_REPOS` under `SOURCE_REPOS_PATH` and globs for files matching `INCLUDE_PATTERNS`, skipping anything matching `EXCLUDE_PATTERNS`.

Default behaviour:

| Setting | Default value | Effect |
|---------|---------------|--------|
| `source_repos_path` | `../` | Treats the parent directory as the workspace root (sibling repos pattern) |
| `source_repos` | `rag-chatbot,ai-gateway,ai-agent,ai-multi-agent,mcp-server,ai-engineering-field-guide` | Six sibling portfolio repos |
| `include_patterns` | `**/*.md,**/*.txt` | Markdown and plain text only — no source code |
| `exclude_patterns` | `**/node_modules/**,**/.venv/**,**/site/**,**/__pycache__/**` | Skip vendored/built artefacts |

What it does NOT do:

- No PDF, DOCX, HTML, or code parsing — markdown only.
- No symlink resolution beyond what `Path.glob` provides.
- No incremental "only changed files" mode — every run re-scans the full set.
- Missing repos log a `repo_not_found` warning and are skipped silently.

| Field | What it controls | 🫏 Donkey |
|-------|------------------|-----------|
| `source_repos_path` | Where the scanner starts walking | The address of the yard where every stable being mailed is parked — change it and the donkey delivers to a different town |
| `include_patterns` | Which files count as "documents" | The list of envelope shapes the clerk is allowed to touch — markdown letters and plain notes only |
| `exclude_patterns` | Junk to skip | The "do not enter" stickers on shelves full of build artefacts and dependency junk |

- 🫏 **Donkey:** The scanner is the mail clerk who only picks up handwritten letters (`.md`, `.txt`) from the right stables and refuses to touch the rubbish bins (`node_modules`, `.venv`, `site`, `__pycache__`).

---

## Stage 2 — Chunker: Cutting Each File

`chunk_document(path, chunk_size, overlap)` (lines 36–82 of `scanner.py`) is a **word-window splitter with heading propagation**:

1. Read the file as UTF-8, ignoring decode errors.
2. Tokenise by `str.split()` (whitespace-delimited words, not LLM tokens).
3. Slide a window of `chunk_size` *words* with a step of `chunk_size - overlap` words.
4. For each chunk, walk the original lines until the cursor passes the chunk's start position and remember the last line that begins with `#` — that becomes the chunk's `heading`.
5. Compute a deterministic 12-char `chunk_id = md5(f"{path}:{chunk_index}")[:12]`.
6. Derive `source_repo` from the third-from-last path segment.

Defaults from `config.py`: `RAG_CHUNK_SIZE=800`, `RAG_CHUNK_OVERLAP=100`. The default function signature uses the same numbers so callers that don't pass them get the production defaults.

> ⚠️ **`chunk_size` here means words, not characters and not LLM tokens.** Lab #1 (Tier 1 chunk-size sweep) sweeps this dimension, but interpret the values as word-counts when reading the lab tables.

| Step | Code reference | 🫏 Donkey |
|------|----------------|-----------|
| Word tokenisation | `text.split()` on line 49 | The clerk treats every space as a perforation line on the letter |
| Sliding window | `i += chunk_size - overlap` on line 79 | Each envelope shares its last 100 words with the next envelope's first 100 — so a sentence cut in the middle still arrives in one piece |
| Heading propagation | Lines 60–69 walk lines until `char_count > char_pos` | Each envelope is stamped with the section title above it so the donkey knows which chapter it belongs to |
| Deterministic ID | `md5(f"{path}:{chunk_index}")[:12]` line 58 | A re-ingest of the same file produces the same envelope barcodes — the GPS warehouse `upsert` overwrites in place instead of duplicating |

- 🫏 **Donkey:** The chunker is the pre-sort station: every long letter becomes a stack of overlapping envelopes, each labelled with the section heading and a stable barcode so re-deliveries don't pile up duplicates.

---

## Stage 3 — Vector Upsert: Embedding + Storing

The chunks produced by stage 2 are passed to `vector_store.upsert(chunks)`. The vector store is whichever provider `create_vector_store()` returned (see [Vector Store Interface](vectorstore-interface-deep-dive.md)).

What happens inside `upsert` is provider-specific, but the contract is the same:

1. Generate an embedding for each chunk's `text` (Ollama for local, Bedrock Titan for AWS, Azure OpenAI `text-embedding-3-small` for Azure).
2. Write the chunk metadata (`source_file`, `source_repo`, `heading`, `chunk_index`) alongside the vector.
3. Use the chunk's `id` as the primary key so a re-ingest overwrites in place.

Ingestion does NOT pre-compute embeddings on the chunk objects — the `embedding: list[float] = []` field on `DocumentChunk` (see `models.py`) is intentionally left empty here. Each provider embeds at upsert time using its own client. This keeps embedding costs and dimensions inside the provider that owns them.

- 🫏 **Donkey:** The vector upsert step hands the envelope stack to whichever GPS warehouse is on duty (local barn, AWS depot, or Azure hub). Each warehouse stamps coordinates in its own format — same envelope, three coordinate systems.

---

## Stage 4 — Graph Extraction: Topics + Relationships

After (or alongside) the vector upsert, each chunk's `text` is passed to `extract_and_store(text, graph_store, llm)` in `src/ingestion/graph_extractor.py`. That function:

1. Calls `llm.extract_topics_and_relations(text)` and expects a dict shaped `{"topics": [...], "relationships": [...]}`.
2. Builds a `Topic` for every entry in `topics` and `await graph_store.upsert_topic(topic)`.
3. **Filters relationships:** only adds an edge when *both* `source_id` and `target_id` were emitted as topics in the same call — no dangling edges.
4. Logs `graph_extracted` with the topic and relationship counts.

The actual prompt and JSON parsing live in the LLM provider (see [Graph Extractor Deep Dive](graph-extractor-deep-dive.md) and `src/llm/ollama.py`, `src/llm/bedrock.py`, `src/llm/azure_openai.py`).

| Element | Source | 🫏 Donkey |
|---------|--------|-----------|
| Topic node | `Topic(id, name, description)` from the LLM JSON | A new town pencilled onto the paper map with its slug-name and a one-line description |
| Relationship edge | `Relationship(source_id, target_id, relation_type, evidence)` | A road drawn between two towns, labelled `USED_BY` / `STORED_IN` / `REQUIRED_BY` and footnoted with the sentence that justified it |
| Dangling-edge filter | The `if r["source_id"] in topic_ids and r["target_id"] in topic_ids` guard on line 28 | The cartographer refuses to draw a road to a town that wasn't surveyed in the same trip — keeps the map honest |

- 🫏 **Donkey:** Graph extraction is the cartographer reading each envelope, pencilling any new towns onto the paper map and drawing roads only between towns surveyed on the same delivery run.

---

## Environment Variables That Control Ingestion

All settings come from `src/config.py` via Pydantic. Override via `.env`.

| Variable | Default | What it controls | 🫏 Donkey |
|----------|---------|------------------|-----------|
| `SOURCE_REPOS_PATH` | `../` | Yard root the scanner walks from | The address of the depot where every stable is parked |
| `SOURCE_REPOS` | six sibling repos | CSV of repo folder names to scan | The list of stables the mail clerk is allowed to enter |
| `INCLUDE_PATTERNS` | `**/*.md,**/*.txt` | Glob shapes that count as documents | The two envelope shapes the clerk is licensed to handle |
| `EXCLUDE_PATTERNS` | `node_modules`, `.venv`, `site`, `__pycache__` | Glob shapes to skip | The "do not enter" stickers on rubbish shelves |
| `RAG_CHUNK_SIZE` | `800` | Words per chunk window | The size of each envelope — bigger envelope, fewer cuts, more words per pocket |
| `RAG_CHUNK_OVERLAP` | `100` | Words shared between neighbours | The size of the perforated overlap so a sentence split in two still arrives whole |
| `CHUNK_STRATEGY` | `fixed` | Tier-4 lab knob — currently only `fixed` is wired | Which cutting jig the clerk uses; only the straight-edge jig is bolted to the bench today |
| `CLOUD_PROVIDER` | `local` | Selects Chroma+Neo4j vs DynamoDB×2 vs Azure Search+Cosmos | Which two warehouses (GPS + paper map) the envelopes are routed to |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Local embedding model | Which GPS-coordinate format the local barn stamps |
| `AWS_BEDROCK_EMBED_MODEL` | `amazon.titan-embed-text-v2:0` | AWS embedding model | The AWS depot's GPS-coordinate format (1024-d) |
| `AZURE_OPENAI_EMBED_DEPLOYMENT` | `text-embedding-3-small` | Azure embedding deployment | The Azure hub's GPS-coordinate format (1536-d) |

---

## Failure Modes and Recovery

Ingestion is **best-effort and idempotent**, not transactional.

| Failure | Behaviour | Recovery |
|---------|-----------|----------|
| A repo in `SOURCE_REPOS` doesn't exist on disk | Scanner logs `repo_not_found` and skips | Add the repo or remove it from the CSV |
| A markdown file is unreadable / bad encoding | `read_text(errors="ignore")` drops bad bytes | None needed — content survives, just a few characters dropped |
| LLM returns malformed JSON for graph extraction | `OllamaLLM.extract_topics_and_relations` catches `Exception` and returns `{"topics": [], "relationships": []}` | The chunk's vector still landed; re-ingest later when the LLM is happier |
| Graph extraction emits an edge to a topic that wasn't extracted in the same call | `extract_and_store` filters it out before writing | Intentional — keeps the graph free of dangling edges |
| Vector store upsert fails mid-batch | Provider raises; the loop above stops | Re-run ingestion — `chunk_id` is deterministic so survivors are overwritten in place, not duplicated |
| `chunk_document` receives an empty file | Returns `[]` immediately (line 50–51) | None needed |

| Failure mode | 🫏 Donkey |
|--------------|-----------|
| Missing repo | The mail clerk shrugs at the empty stable, jots a note in the logbook, and walks on |
| Bad encoding | The clerk smudges over the unreadable letters and copies the rest |
| LLM JSON fails | The cartographer can't read the envelope's handwriting today, so no new towns get pencilled — the GPS-stamped envelope still made it onto the warehouse shelf |
| Dangling edge | The cartographer refuses to draw a road to a town nobody surveyed |
| Mid-batch crash | Re-running the route is safe because every envelope has a stable barcode |

- 🫏 **Donkey:** Nothing in this pipeline is transactional. The barcode-as-key trick (`md5(path:index)`) means the donkey can re-walk the route any number of times and the warehouse never grows duplicate envelopes.

---

## What Ingestion Does NOT Do

- ❌ No incremental / changed-files-only mode — every `/ingest/run` re-scans everything.
- ❌ No automatic gap detection at ingest time — gap detection is a chat-time concern (see Gap Detector Deep Dive in batch C).
- ❌ No wiki page generation — that's the wiki generator (also batch C).
- ❌ No deduplication of topics across files — same topic ID extracted from two files just `MERGE`s into the same node, which is the desired behaviour.
- ❌ No PDF / DOCX / source-code parsing — markdown only.

- 🫏 **Donkey:** Ingestion is just the pre-sort. Quality reports, brochure writing, and "is this worth delivering?" judgements happen elsewhere — keeps the pre-sort station fast and dumb.

---

## Self-Test Questions

1. If you change `RAG_CHUNK_SIZE` from 800 to 400 and re-ingest, will the existing chunk IDs still resolve?
   *(Answer: yes for the prefix that fits in both windows, no for ones whose `chunk_index` no longer exists — leftover larger chunks remain in the store unless you call `delete_by_source` first. Running `delete_by_source` for every file before re-ingestion is the safe pattern.)*
2. Why does `extract_and_store` filter relationships against `topic_ids` from the same call, instead of all topics in the graph?
   *(Answer: it keeps the LLM honest — a relation is only stored when the LLM explicitly surveyed both endpoints in the same chunk, which keeps `evidence` meaningful.)*
3. What happens to the embedding when ingestion runs against the AWS provider but the Bedrock model isn't enabled in your region?
   *(Answer: the Bedrock client raises, the upsert fails for that batch; existing chunks remain untouched thanks to the deterministic key.)*
4. Could you point this pipeline at a single repo to ingest just that one?
   *(Answer: yes — set `SOURCE_REPOS=rag-chatbot` in `.env` and re-run. The scanner only walks what's in the CSV.)*
