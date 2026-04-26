# Deep Dive: Vector Store Providers

> **Study order:** #10 · **Difficulty:** ★★★☆☆ (three concrete implementations, three cost models)
>
> **Files:** [`src/vectorstore/chroma.py`](../../src/vectorstore/chroma.py), [`src/vectorstore/dynamodb.py`](../../src/vectorstore/dynamodb.py), [`src/vectorstore/azure_search.py`](../../src/vectorstore/azure_search.py)
>
> **Prerequisite:** [#9 — Vector Store Interface](vectorstore-interface-deep-dive.md)
>
> **Companion:** [Graph Store Providers](graphstore-providers-deep-dive.md)

---

## Table of Contents

- [Three Warehouses, One Contract](#three-warehouses-one-contract)
- [Head-to-Head Comparison](#head-to-head-comparison)
- [Provider 1 — ChromaDB (Local)](#provider-1--chromadb-local)
- [Provider 2 — DynamoDB (AWS)](#provider-2--dynamodb-aws)
- [Provider 3 — Azure AI Search (Azure)](#provider-3--azure-ai-search-azure)
- [Choosing a Provider](#choosing-a-provider)
- [Self-Test Questions](#self-test-questions)

---

## Three Warehouses, One Contract

All three providers implement [`BaseVectorStore`](vectorstore-interface-deep-dive.md). The interface is identical; the trade-offs are not. This doc lays them side-by-side.

| Dimension | ChromaDB (local) | DynamoDB (AWS) | Azure AI Search (Azure) |
|-----------|------------------|----------------|--------------------------|
| Backing tech | ChromaDB HTTP server in Docker | DynamoDB table + Python cosine | Azure AI Search index, native HNSW |
| Index | HNSW (cosine space) | None — full-table scan | HNSW (Azure built-in) |
| Embedder | Ollama (`nomic-embed-text`) | Bedrock Titan v2 (1024-d) | Azure OpenAI `text-embedding-3-small` (1536-d) |
| Cost model | €0 (Docker on your laptop) | DynamoDB on-demand + Bedrock per-token | Search SKU + Azure OpenAI per-token |
| Practical scale | ~1M chunks before tuning | ~100k chunks (scan cost dominates) | tens of millions of vectors |
| Score returned | `1 - cosine_distance` | min-max normalised cosine | native `@search.score` |
| When to use | Dev, demos, offline work | AWS-native, cheap-at-small-scale | Azure-native, large corpora |

- 🚚 **Courier:** Three GPS warehouses with the same loading-bay rules. The local barn is free but small; the AWS depot trades search speed for being dirt cheap; the Azure hub is a proper hyperscale warehouse with HNSW conveyor belts built in.

---

## Head-to-Head Comparison

| Concern | Chroma | DynamoDB | Azure AI Search | 🚚 Courier |
|---------|--------|----------|-----------------|-----------|
| Setup time | `docker compose up -d chromadb` | `terraform apply` (one DynamoDB table) | `terraform apply` (Search service + index auto-created on first upsert) | Local barn opens in seconds; AWS depot needs a one-time blueprint; Azure hub needs a building permit but auto-arranges the shelves on first use |
| Cold-start latency | None (already running) | None (REST call) | None (REST call) | All three warehouses are open 24/7 |
| Per-query cost | €0 | ~€0.0001 (one Titan embed + DynamoDB scan units) | ~€0.00002 (one OpenAI embed + Search query units) | Local trip is free; AWS trip is a few cents per thousand; Azure trip is sub-cent per thousand |
| Per-upsert cost | €0 | ~€0.0001 (Titan embed + DynamoDB write units) | ~€0.00002 (OpenAI embed + Search write units) | Same per-trip economics on the loading bay as the search desk |
| Auto-scales | No (single Docker container) | Yes (DynamoDB on-demand) | Yes (replica + partition counts) | Local barn has fixed capacity; the cloud depots and hubs grow on demand |
| Eventual consistency | Strongly consistent | Eventually consistent for the scan | Near-real-time index | The local barn's shelves are always in sync; the cloud warehouses may take a moment to show new envelopes |
| Best at | Iterating on chunking + embedding choices | Sub-100k corpora at AWS-cheap rates | Hybrid search, faceting, filters at scale | Pick the warehouse that matches the kind of trips the courier makes most |

---

## Provider 1 — ChromaDB (Local)

**File:** `src/vectorstore/chroma.py` (88 lines)

ChromaDB runs as an HTTP server inside Docker (`chromadb` service in `docker compose`). The provider talks to it over HTTP, so the Python process and the vector store are decoupled — kill and restart the API without losing the index.

**Construction (lines 14–28):**

```python
self.client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
ef = embedding_functions.OllamaEmbeddingFunction(
    url=f"{settings.ollama_base_url}/api/embeddings",
    model_name=settings.ollama_embed_model,
)
self.collection = self.client.get_or_create_collection(
    name="knowledge_engine",
    embedding_function=ef,
    metadata={"hnsw:space": "cosine"},
)
```

Three things happen here:

- One collection (`knowledge_engine`) backs the whole store. There is no per-repo or per-source partitioning — `source_repo` lives in the metadata.
- The embedding function is bound to the collection. ChromaDB calls Ollama on every `upsert` and `query` automatically — the provider never embeds explicitly.
- HNSW is configured for cosine space at collection creation time. Once set, it persists; changing it requires deleting and re-creating the collection.

**Search (lines 51–78):** the sync helper calls `collection.query(query_texts=[query], n_results=top_k, include=[...])`, then converts cosine *distance* into similarity with `score = max(0.0, 1.0 - distance)`.

**Async wrapping:** the Chroma Python client is sync, so every async method delegates to `run_in_executor(None, self._sync_…)`. This honours the `async` contract on `BaseVectorStore` without blocking the FastAPI event loop.

**Setup snippet:**

```bash
# .env
CLOUD_PROVIDER=local
CHROMA_HOST=localhost
CHROMA_PORT=8000
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text

# infra
docker compose up -d chromadb
ollama pull nomic-embed-text
```

| Strength | Caveat | 🚚 Courier |
|----------|--------|-----------|
| Free, fast, runs offline | Single container — no replication | The local barn is great for the courier's apprenticeship — no rent, no internet, but if the barn floods you start over |
| HNSW from day one | One collection — no multi-tenant story | The conveyor belt is fancy but there's only one warehouse floor for everything |
| Bound embedder = no model mismatch | If Ollama is down, both upsert and search fail | The same GPS-coordinate stamp is used at both desks; if the stamper is broken, nothing moves |

- 🚚 **Courier:** The local barn is the courier's training ground — same loading bay and search desk as the cloud warehouses, but free, single-container, and offline-friendly.

---

## Provider 2 — DynamoDB (AWS)

**File:** `src/vectorstore/dynamodb.py` (148 lines)

The "no Neptune, no OpenSearch" cost play: store embeddings as JSON-encoded float lists in a regular DynamoDB table, do cosine in Python.

**Why this works:** for the knowledge-engine corpus (sub-100k chunks), a full-table scan + brute-force cosine is ~1–2 seconds end-to-end and costs cents per query. OpenSearch Serverless is ~€0.24/OCU/hour minimum. DynamoDB on-demand is ~€1.25 / million write requests. The math heavily favours DynamoDB at this scale.

**Construction (lines 44–58):**

```python
self.dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
self.table = self.dynamodb.Table(settings.dynamodb_vector_table)
# Bedrock embeddings client is lazy-init via _get_embedder()
```

**Upsert (lines 77–90):** for each chunk, embed via `_embed_text` (Bedrock Titan v2), `json.dumps` the embedding into a string attribute, and `batch_writer().put_item(...)`.

**Search (lines 97–132):** four steps:

1. Embed the query string with Titan v2.
2. **Full-table scan** with `ExclusiveStartKey` pagination to handle tables larger than 1 MB per page.
3. Compute cosine for each row in Python (`_cosine` is hand-rolled — no NumPy dependency).
4. Apply **min-max normalisation** (`_normalize_scores`) so the best match becomes `1.0`. This is the same fix carried over from rag-chatbot — Titan cosine scores cluster in the 0.04–0.37 range, which makes raw thresholds useless. Min-max rescales them into a usable 0..1 band.
5. Sort, clip to `top_k` (using `safe_k = min(top_k, len(ranked))` so a sparse store never crashes), reconstruct `DocumentChunk` objects.

**Why min-max and not a fixed cosine threshold?** Cosine values from Titan v2 don't span the full 0..1 range, so a static `score >= 0.7` filter would reject everything. Min-max says "the best chunk this query found is 1.0; everything else is rescaled relative to it" — a per-query honest yardstick.

**Setup snippet:**

```bash
# .env
CLOUD_PROVIDER=aws
AWS_REGION=eu-central-1
AWS_BEDROCK_EMBED_MODEL=amazon.titan-embed-text-v2:0
DYNAMODB_VECTORS_TABLE=knowledge-engine-vectors

# infra
cd terraform/aws && terraform apply
# Bedrock model access for Titan must be granted in the AWS console once.
```

| Strength | Caveat | 🚚 Courier |
|----------|--------|-----------|
| Cents per query at small scale | Full-table scan — costs grow with corpus size | The AWS depot search clerk reads every shelf for every question; fine for a small depot, brutal at warehouse-chain scale |
| No Neptune / OpenSearch / OCU bills | Manual cosine = no HNSW recall benefits | The depot has no conveyor belt, just hand-carting; cheaper rent, slower per-trip |
| Min-max normalisation fixes Titan low-score problem | Scores are not comparable across queries (each is rescaled to its own max) | The closeness stamps are honest *within one trip* but you can't compare today's stamps against last week's |

- 🚚 **Courier:** The AWS depot is the cheapest cloud warehouse the courier can use because we skipped buying the conveyor belt (Neptune / OpenSearch). The courier carts envelopes by hand — fine until the depot grows past ~100k envelopes.

---

## Provider 3 — Azure AI Search (Azure)

**File:** `src/vectorstore/azure_search.py` (149 lines)

Real HNSW vector search on Azure-native infrastructure. The provider owns the index lifecycle: it creates the index on first upsert if missing, with the right schema and HNSW config wired up.

**Construction (lines 33–50):** three clients — `SearchClient` for queries, `SearchIndexClient` for index management, `AsyncAzureOpenAI` for embeddings (`text-embedding-3-small`, 1536-d).

**Index schema (lines 52–80):** keyed on `chunk_id`, with `text`, `source_file`, `source_repo`, `heading`, `chunk_index`, and an `embedding` field configured as a 1536-dimensional vector with HNSW algorithm. `source_file` and `source_repo` are marked filterable so `delete_by_source` and metadata filters work.

```python
SearchField(
    name="embedding",
    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
    searchable=True,
    vector_search_dimensions=1536,
    vector_search_profile_name="default",
),
vector_search=VectorSearch(
    profiles=[VectorSearchProfile(name="default", algorithm_configuration_name="hnsw")],
    algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
),
```

**Search (lines 106–131):** embed the query → wrap in `VectorizedQuery(vector=..., k_nearest_neighbors=top_k, fields="embedding")` → `search_client.search(search_text=None, vector_queries=[query], top=top_k)`. Azure's HNSW index returns candidates in score order; `@search.score` is taken as-is.

**Delete by source (lines 140–149):** uses an OData filter `source_file eq '<path>'` to find IDs, then `delete_documents`. This relies on `source_file` being marked `filterable=True` in the schema.

**Setup snippet:**

```bash
# .env
CLOUD_PROVIDER=azure
AZURE_SEARCH_ENDPOINT=https://<service>.search.windows.net
AZURE_SEARCH_API_KEY=<key>
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_EMBED_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_API_VERSION=2024-02-01

# infra
cd terraform/azure && terraform apply
# Index is auto-created on first /ingest/run.
```

| Strength | Caveat | 🚚 Courier |
|----------|--------|-----------|
| HNSW from day one, scales to tens of millions | Search SKU has a monthly minimum even idle | The Azure hub is a proper hyperscale warehouse with conveyor belts — but you pay rent even when no trips are happening |
| Auto-creates the index with the right schema | Schema change = drop and re-create the index | The warehouse arranges its own shelves on opening day; renovating means closing the floor |
| Filters and faceting on metadata | Filter syntax is OData, not Python | Aisle-by-aisle search filters work, but you have to learn the warehouse's local dialect |

- 🚚 **Courier:** The Azure hub is the proper hyperscale warehouse — the courier gets a real conveyor belt (HNSW) and aisle filters, in exchange for a fixed monthly rent.

---

## Choosing a Provider

| Situation | Pick | Reason |
|-----------|------|--------|
| Building, demo-ing, iterating on chunking | Chroma (local) | Zero cost, fast feedback loop |
| AWS deployment, < 100k chunks, cost-sensitive | DynamoDB | Cheapest by far at this scale |
| AWS deployment, > 100k chunks, latency-sensitive | (Not in this repo today — would need OpenSearch Serverless) | Scan cost dominates beyond 100k |
| Azure deployment, any scale | Azure AI Search | The native HNSW path is correctly priced for any size |
| Hybrid keyword + vector search needed | Azure AI Search | Built in; not implemented in the others today |

| Decision | 🚚 Courier |
|----------|-----------|
| Local barn for everyday training | The courier practises in the free barn before going on real trips |
| AWS depot for small AWS deployments | When AWS is the yard, the cheap depot is the right warehouse for a few thousand envelopes |
| Azure hub for any Azure deployment | When Azure is the yard, the conveyor-belt hub is the only one that scales without surprise bills |

- 🚚 **Courier:** The contract guarantees the courier can walk into any of the three. Pick the warehouse whose rent and shelf-count match your trip volume.

---

## Self-Test Questions

1. Why does the DynamoDB provider min-max normalise scores instead of returning raw cosine?
   *(Answer: Titan v2 cosine scores cluster in 0.04–0.37; raw values make a fixed threshold useless. Min-max rescales the best result to 1.0 within each query.)*
2. The Chroma provider passes its embedder to the collection at construction. What happens if you change `OLLAMA_EMBED_MODEL` and restart the API without re-ingesting?
   *(Answer: search will embed queries with the new model but the stored vectors were embedded with the old one — silent recall collapse. Drop and re-create the collection on embed-model change.)*
3. Why does the Azure provider call `_ensure_index()` at the top of every operation, not just at construction?
   *(Answer: it's a self-healing pattern — the first call after a fresh terraform apply creates the index lazily, so the API doesn't fail if you start it before infra is ready.)*
4. What's the practical reason DynamoDB scales out around 100k chunks?
   *(Answer: a full-table scan + Python cosine is O(N). Past ~100k rows the scan starts dominating query latency and DynamoDB read-capacity units.)*
