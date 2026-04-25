# Deep Dive: The Vector Store Interface

> **Study order:** #9 · **Difficulty:** ★★☆☆☆ (an ABC with four methods — the contract is small)
>
> **Files:** [`src/vectorstore/base.py`](../../src/vectorstore/base.py), [`src/vectorstore/factory.py`](../../src/vectorstore/factory.py)
>
> **Prerequisite:** [#7 — Ingestion Pipeline Deep Dive](ingestion-pipeline-deep-dive.md)
>
> **Companion:** [Vector Store Providers](vectorstore-providers-deep-dive.md), [Graph Store Interface](graphstore-interface-deep-dive.md)

---

## Table of Contents

- [Why an Interface Instead of a Concrete Class](#why-an-interface-instead-of-a-concrete-class)
- [The Contract — `BaseVectorStore`](#the-contract--basevectorstore)
- [Method 1 — `upsert(chunks)`](#method-1--upsertchunks)
- [Method 2 — `search(query, top_k)`](#method-2--searchquery-top_k)
- [Method 3 — `chunk_count()`](#method-3--chunk_count)
- [Method 4 — `delete_by_source(source_file)`](#method-4--delete_by_sourcesource_file)
- [The Factory — How Config Picks a Provider](#the-factory--how-config-picks-a-provider)
- [Invariants Every Provider Must Honour](#invariants-every-provider-must-honour)
- [Self-Test Questions](#self-test-questions)

---

## Why an Interface Instead of a Concrete Class

The chat engine, ingestion pipeline, and gap detector all need to "store and search vectors". They do not need to know whether the vectors live in ChromaDB, DynamoDB, or Azure AI Search.

`BaseVectorStore` is the contract that lets any of those three (and any future fourth) be swapped in by changing one environment variable. The factory enforces "you get exactly one implementation per process".

| Without an interface | With `BaseVectorStore` | 🫏 Donkey |
|----------------------|------------------------|-----------|
| Every caller imports `chromadb` directly | Callers import `BaseVectorStore` and call abstract methods | The donkey learns one set of warehouse rules and walks into any of three warehouses without re-training |
| Provider switch = grep-and-rewrite across the codebase | Provider switch = `CLOUD_PROVIDER=azure` in `.env` | The yard manager flips one sign and the donkey reroutes to a different warehouse for the rest of the day |
| Tests need a real ChromaDB running | Tests use an in-memory mock that implements the four methods | The trainee donkey practises on a paper-cardboard warehouse before being trusted with the real one |

- 🫏 **Donkey:** The interface is the warehouse door rules — height of the loading bay, shape of the envelope shelves, where the search desk sits. Any GPS warehouse that follows them can serve the donkey, no extra training required.

---

## The Contract — `BaseVectorStore`

The full file is 25 lines. Here it is verbatim from `src/vectorstore/base.py`:

```python
from abc import ABC, abstractmethod
from src.models import DocumentChunk


class BaseVectorStore(ABC):

    @abstractmethod
    async def upsert(self, chunks: list[DocumentChunk]) -> int:
        """Store chunks with embeddings. Returns count upserted."""
        ...

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[DocumentChunk]:
        """Semantic search — returns top_k chunks sorted by relevance."""
        ...

    @abstractmethod
    async def chunk_count(self) -> int:
        ...

    @abstractmethod
    async def delete_by_source(self, source_file: str) -> int:
        """Remove all chunks from a given source file (for re-ingestion)."""
        ...
```

Four methods. No `__init__`. No optional helpers. Anything beyond these four is provider-specific (e.g. ChromaDB exposes `metadata={"hnsw:space": "cosine"}` knobs in its constructor; Azure AI Search owns its index lifecycle internally).

Three things to notice:

1. **Everything is `async`.** Even the local Chroma provider wraps its sync client in `run_in_executor` to honour the contract. This lets the FastAPI handlers `await` without blocking the event loop.
2. **`DocumentChunk` is the only data type crossing the boundary.** No raw vectors, no provider-specific result objects. `score: float` is a field on `DocumentChunk` and providers populate it on the way back out.
3. **Embedding is implicit, not a parameter.** Providers are responsible for embedding the chunks themselves — the caller never passes a vector. This keeps embedding model choice paired with the provider that owns it (Ollama for local, Bedrock Titan for AWS, Azure OpenAI `text-embedding-3-small` for Azure).

| Design choice | What it enables | 🫏 Donkey |
|---------------|-----------------|-----------|
| All methods async | FastAPI handlers don't block while a slow Bedrock call resolves | The donkey doesn't fall asleep at the warehouse door waiting for a slow clerk; the next delivery can be in flight already |
| `DocumentChunk` as wire format | One data shape from ingest to chat answer | Every envelope on every shelf has the same address card — no special-case handling per warehouse |
| Embedding hidden behind `upsert` | Caller never picks an embedding model | The donkey doesn't choose which GPS-coordinate format the warehouse uses; it just hands over the envelope |

- 🫏 **Donkey:** Four words on the warehouse door — `upsert`, `search`, `chunk_count`, `delete_by_source`. Anything else is internal warehouse business and the donkey doesn't care.

---

## Method 1 — `upsert(chunks)`

**Signature:** `async def upsert(self, chunks: list[DocumentChunk]) -> int`

**Returns:** number of chunks accepted (typically `len(chunks)` on success).

**Invariants every provider must honour:**

- Idempotent on `chunk.id`. Calling `upsert` twice with the same chunk produces one row, not two. ChromaDB uses `collection.upsert(...)`; DynamoDB uses `put_item` keyed on `chunk_id`; Azure AI Search uses `upload_documents` keyed on `chunk_id`.
- Embedding is generated from `chunk.text` inside the provider — the caller does not pre-embed.
- All metadata fields on `DocumentChunk` (`source_file`, `source_repo`, `heading`, `chunk_index`) are persisted alongside the vector so `delete_by_source` and result reconstruction can find them later.
- Returns the integer count, not the list. Callers who want a list back have to keep their own.

| Provider | Where embedding happens | Where the row lands |
|----------|-------------------------|---------------------|
| Chroma | `OllamaEmbeddingFunction` attached to the collection | ChromaDB collection `knowledge_engine` |
| DynamoDB | `_embed_text` → Bedrock Titan in `_sync_upsert` | DynamoDB table from `dynamodb_vector_table` setting |
| Azure AI Search | `self.openai_client.embeddings.create` in `_embed` | Azure AI Search index `knowledge-engine-vectors` |

- 🫏 **Donkey:** `upsert` is the loading bay. The donkey hands over a batch of envelopes; the warehouse stamps each with GPS coordinates, files them by barcode, and shouts back the count.

---

## Method 2 — `search(query, top_k)`

**Signature:** `async def search(self, query: str, top_k: int = 5) -> list[DocumentChunk]`

**Returns:** at most `top_k` chunks, sorted by descending relevance, with the `score` field populated.

**Invariants:**

- Caller passes a **string query, not a vector.** The provider embeds the query using the same model it embedded the chunks with — a guarantee the contract requires but does not police; mismatched embeddings here would silently destroy retrieval quality.
- `top_k` is a *cap*, not a guarantee. Returning fewer chunks (e.g. when the store has fewer than `top_k` rows) is allowed and explicitly handled in the DynamoDB provider via `safe_k = min(top_k, len(ranked))`.
- `score` should be a higher-is-better float. Chroma converts cosine distance → similarity (`1 - distance`). DynamoDB applies min-max normalisation across the result set (the Titan low-score fix carried over from rag-chatbot lessons). Azure AI Search returns its native `@search.score`. Each provider picks an honest mapping; cross-provider score *values* are not directly comparable, but ordering and "higher = better" is always honoured.
- The returned `DocumentChunk` objects are the same shape `upsert` accepted — `source_file`, `source_repo`, `heading`, `chunk_index`, `text` all populated from storage.

| Concern | Local Chroma | AWS DynamoDB | Azure AI Search |
|---------|--------------|--------------|-----------------|
| Index type | HNSW (cosine space) | None — full-table scan + Python cosine | HNSW (Azure built-in) |
| Embedder used at search | Ollama nomic-embed-text | Bedrock Titan v2 | Azure OpenAI `text-embedding-3-small` |
| Score normalisation | `1 - cosine_distance` | min-max over the result set | native `@search.score` |
| Practical scale | ~1M chunks before HNSW tuning matters | ~100k chunks (scan cost) | tens of millions |

- 🫏 **Donkey:** `search` is the warehouse search desk. The donkey arrives with a written question; the clerk turns it into GPS coordinates, fetches the closest envelopes, and hands back a stack ranked by closeness.

---

## Method 3 — `chunk_count()`

**Signature:** `async def chunk_count() -> int`

**Returns:** total number of chunks currently stored.

This is what the `/health` endpoint and the Streamlit dashboard call. Cheap and exact for Chroma (`collection.count()`), one DynamoDB `scan(Select="COUNT")` for AWS, one `get_document_count()` for Azure AI Search.

- 🫏 **Donkey:** The shelf-counter — how many envelopes are currently on the warehouse shelves.

---

## Method 4 — `delete_by_source(source_file)`

**Signature:** `async def delete_by_source(self, source_file: str) -> int`

**Returns:** number of chunks removed.

The "I'm about to re-ingest this file" hook. Implementation pattern is the same across providers:

1. Find every row where `source_file == <argument>`.
2. Delete them in a batch.
3. Return the count.

Chroma uses `collection.get(where={"source_file": ...})`. DynamoDB scans with a Python filter. Azure AI Search uses an OData filter `source_file eq '...'`. None of them are O(1) — they all touch every chunk for that file. Cheap because chunks-per-file is small; not cheap if you call it for every file in a re-ingest loop, so the ingestion path uses it selectively.

- 🫏 **Donkey:** `delete_by_source` is the warehouse clear-out request — "any envelope from this letter, off the shelves please" — so the next pre-sort doesn't pile new envelopes on top of stale ones.

---

## The Factory — How Config Picks a Provider

`src/vectorstore/factory.py` is 16 lines:

```python
def create_vector_store() -> BaseVectorStore:
    settings = get_settings()
    if settings.cloud_provider == CloudProvider.AWS:
        from src.vectorstore.dynamodb import DynamoDBVectorStore
        return DynamoDBVectorStore()
    elif settings.cloud_provider == CloudProvider.AZURE:
        from src.vectorstore.azure_search import AzureSearchVectorStore
        return AzureSearchVectorStore()
    else:
        from src.vectorstore.chroma import ChromaVectorStore
        return ChromaVectorStore()
```

Three properties worth highlighting:

- **Lazy imports.** Provider modules are imported only when selected. Running locally never imports `boto3` or the Azure SDK; a missing cloud SDK does not break local dev.
- **`local` is the default.** Anything other than `aws` or `azure` (including unset) returns the Chroma provider. This is friendly for first-time clones — `docker compose up -d chromadb neo4j` is enough.
- **Single point of construction.** Every place in the codebase that needs a vector store calls `create_vector_store()`, so swap-in is one flag change.

| Setting | Returned class |
|---------|----------------|
| `CLOUD_PROVIDER=local` (or unset) | `ChromaVectorStore` |
| `CLOUD_PROVIDER=aws` | `DynamoDBVectorStore` |
| `CLOUD_PROVIDER=azure` | `AzureSearchVectorStore` |

- 🫏 **Donkey:** The factory is the yard sign at the gate — it tells the donkey which warehouse to walk into today. Flip the sign, the donkey reroutes; the warehouse rules (the four methods) are identical inside.

---

## Invariants Every Provider Must Honour

If you ever add a fourth provider (Pinecone, Qdrant, OpenSearch, …), this is the test sheet:

| Invariant | Why | 🫏 Donkey |
|-----------|-----|-----------|
| `upsert` is idempotent on `chunk.id` | Re-ingest must not duplicate | Re-walking the route does not pile up duplicate envelopes |
| Embedding model used at `upsert` and `search` is the same | Mismatched models silently destroy recall | The warehouse uses one GPS-coordinate format on the loading bay and the search desk |
| `search` returns `DocumentChunk` with `score` populated, higher = better | Chat engine and gap detector compare scores across results | Every returned envelope carries a closeness stamp the donkey can sort on |
| `top_k` is a cap, not a guarantee | Sparse stores must not crash | The donkey accepts "I only have 3 envelopes that fit" without complaining |
| All metadata fields persisted at `upsert` are restored on `search` | `source_file`, `heading`, etc. are needed for citations and `delete_by_source` | Every envelope keeps its address card from loading bay to search desk |
| `delete_by_source(file)` removes every chunk whose `source_file == file`, returns the count | Re-ingestion needs this to avoid pile-up | The warehouse clears out every envelope from a given letter on request |

- 🫏 **Donkey:** Six warehouse-door rules. Honour them and any new GPS warehouse can serve the donkey on day one without changing the chat engine, gap detector, or ingestion code.

---

## Self-Test Questions

1. Why is `embedding` a field on `DocumentChunk` but never populated by callers before `upsert`?
   *(Answer: each provider owns its embedder; pre-computing in the caller would force one model on everyone. The field exists for cases where the provider chooses to round-trip vectors back to callers.)*
2. Could two different providers return scores that mean different things for the same query?
   *(Answer: yes — Chroma returns `1 - cosine_distance`, DynamoDB returns min-max normalised cosine, Azure returns its native score. Ordering is comparable; absolute values are not.)*
3. The factory uses lazy imports. What breaks if you switch them all to top-of-file imports?
   *(Answer: local dev requires installing `boto3` and the Azure SDK to start the app — the friendly first-run experience disappears.)*
4. If you wanted to add a Pinecone provider, what is the minimum you must implement?
   *(Answer: a class extending `BaseVectorStore` with the four async methods, plus one branch in the factory and one new `CloudProvider` enum value.)*
