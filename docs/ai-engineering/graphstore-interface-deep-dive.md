# Deep Dive: The Graph Store Interface

> **Study order:** #11 · **Difficulty:** ★★☆☆☆ (an ABC with seven methods — straightforward, but graph-flavoured)
>
> **Files:** [`src/graphstore/base.py`](../../src/graphstore/base.py), [`src/graphstore/factory.py`](../../src/graphstore/factory.py)
>
> **Prerequisite:** [#9 — Vector Store Interface](vectorstore-interface-deep-dive.md), [#8 — Graph Extractor Deep Dive](graph-extractor-deep-dive.md)
>
> **Companion:** [Graph Store Providers](graphstore-providers-deep-dive.md)

---

## Table of Contents

- [Why Decouple the Graph From the Vector Store](#why-decouple-the-graph-from-the-vector-store)
- [The Contract — `BaseGraphStore`](#the-contract--basegraphstore)
- [Method 1 — `upsert_topic(topic)`](#method-1--upsert_topictopic)
- [Method 2 — `upsert_relationship(rel)`](#method-2--upsert_relationshiprel)
- [Method 3 — `get_topic(topic_id)`](#method-3--get_topictopic_id)
- [Method 4 — `get_connected_topics(topic_id, max_hops)`](#method-4--get_connected_topicstopic_id-max_hops)
- [Method 5 — `get_all_topics()` and `get_full_graph()`](#method-5--get_all_topics-and-get_full_graph)
- [Method 6 — `topic_count()`](#method-6--topic_count)
- [The Factory — How Config Picks a Provider](#the-factory--how-config-picks-a-provider)
- [Invariants Every Provider Must Honour](#invariants-every-provider-must-honour)
- [Self-Test Questions](#self-test-questions)

---

## Why Decouple the Graph From the Vector Store

Vectors and graphs answer different questions. Vectors say "this chunk looks like the question"; graphs say "these concepts are connected to that concept". GraphRAG combines both — see [GraphRAG Concepts](graphrag-concepts.md) — but the storage layers are kept separate so each can scale, fail, and be priced on its own terms.

| Question type | Right tool | Wrong tool | 🫏 Donkey |
|---------------|------------|------------|-----------|
| "Find chunks similar to this question" | Vector store | Graph store | The donkey looks up GPS coordinates on the warehouse shelves, not on the paper map |
| "Show me concepts 2 hops from `embeddings`" | Graph store | Vector store | The donkey follows roads on the paper map; GPS coordinates don't tell you which towns connect |
| "Render the full knowledge map for the UI" | Graph store | Vector store | The cartographer hands over the whole map; the warehouse only knows individual shelves |
| "Confirm a topic exists by its slug ID" | Graph store | Vector store | The map index lookup is O(1); the warehouse would have to scan every shelf |

`BaseGraphStore` is the contract that lets Neo4j, DynamoDB adjacency lists, or Cosmos DB NoSQL all serve the chat engine and gap detector identically.

- 🫏 **Donkey:** The map-room rules. Any paper-map workshop that follows them can hang on the donkey's wall — Neo4j drawn in proper graph ink, DynamoDB rolled up as adjacency-list rows, Cosmos NoSQL pinned as document pages.

---

## The Contract — `BaseGraphStore`

The full file is 45 lines. From `src/graphstore/base.py`:

```python
class BaseGraphStore(ABC):

    @abstractmethod
    async def upsert_topic(self, topic: Topic) -> None: ...

    @abstractmethod
    async def upsert_relationship(self, rel: Relationship) -> None: ...

    @abstractmethod
    async def get_topic(self, topic_id: str) -> Topic | None: ...

    @abstractmethod
    async def get_connected_topics(self, topic_id: str, max_hops: int = 2) -> list[Topic]:
        """Traverse the graph to find related topics within N hops."""
        ...

    @abstractmethod
    async def get_all_topics(self) -> list[Topic]: ...

    @abstractmethod
    async def get_full_graph(self) -> KnowledgeGraph:
        """Return all topics and relationships for visualization."""
        ...

    @abstractmethod
    async def topic_count(self) -> int: ...
```

Seven methods — three writes (well, two writes and one count), four reads. No deletes today (deletion is intentionally manual; topics are cheap and pruning is rare).

| Method | Reads or writes | What it touches |
|--------|----------------|-----------------|
| `upsert_topic` | Write | One node |
| `upsert_relationship` | Write | One edge |
| `get_topic` | Read | One node |
| `get_connected_topics` | Read | Multi-hop traversal |
| `get_all_topics` | Read | All nodes |
| `get_full_graph` | Read | All nodes + all edges |
| `topic_count` | Read | Cardinality |

- 🫏 **Donkey:** Seven map-room rules — two for adding (towns and roads), four for asking (one town, neighbouring towns, all towns, all towns + roads), one for counting. Every map-room follows them or the donkey can't read the wall.

---

## Method 1 — `upsert_topic(topic)`

**Signature:** `async def upsert_topic(self, topic: Topic) -> None`

**Invariants:**

- Idempotent on `topic.id`. Two calls with the same `id` produce one node, not two — Neo4j uses `MERGE`, DynamoDB uses `put_item`, Cosmos uses `upsert_item`.
- All non-`id` fields (`name`, `description`, `source_repos`) get overwritten on the second call, so the latest extraction wins.
- Returns `None`, not the merged `Topic` — callers don't need a confirmation, the operation is fire-and-forget.

| Concern | Implementation note | 🫏 Donkey |
|---------|---------------------|-----------|
| Slug as primary key | `topic.id` is the lookup key everywhere | The town name on the official map is the only identifier — pencilling the same town twice doesn't double-list it |
| Last-write-wins on description | Neo4j `SET` clause / put_item semantics overwrite | If the cartographer rewrites a town's description, the new one replaces the old |
| No deletion in the contract | Topics are cheap; manual delete via the provider's admin console if needed | Towns rarely disappear off the map; if one needs erasing, the cartographer does it by hand |

- 🫏 **Donkey:** `upsert_topic` is the cartographer pencilling a town onto the map — first time it appears on a delivery note, the dot lands; later mentions update the town's caption.

---

## Method 2 — `upsert_relationship(rel)`

**Signature:** `async def upsert_relationship(self, rel: Relationship) -> None`

**Invariants:**

- Idempotent on the triple `(source_id, relation_type, target_id)`. Re-asserting the same edge overwrites instead of duplicating.
- `evidence` and `weight` get updated on each call — the latest sentence wins.
- Direction is preserved: `(A) -[USED_BY]-> (B)` is not the same edge as `(B) -[USED_BY]-> (A)`.

| Provider | How the triple becomes a key |
|----------|------------------------------|
| Neo4j | `MERGE (a)-[r:RELATION_TYPE]->(b)` matches on the pattern |
| DynamoDB | Composite `edge_id = f"{source_id}#{relation_type}#{target_id}"` is the partition key |
| Cosmos | `id = f"{source_id}__{relation_type}__{target_id}"` |

- 🫏 **Donkey:** `upsert_relationship` is the cartographer drawing a road between two towns, with a footnote on the road for the sentence that justified it. Drawing the same road again just refreshes the footnote.

---

## Method 3 — `get_topic(topic_id)`

**Signature:** `async def get_topic(self, topic_id: str) -> Topic | None`

**Returns:** the `Topic`, or `None` if the slug isn't in the graph.

This is the cheap point lookup — used by the chat engine's gap detector to confirm whether a topic the LLM mentioned actually exists in the corpus.

- 🫏 **Donkey:** The town index lookup — "is there a town called `embeddings` on the map?" Yes or no, fast.

---

## Method 4 — `get_connected_topics(topic_id, max_hops)`

**Signature:** `async def get_connected_topics(self, topic_id: str, max_hops: int = 2) -> list[Topic]`

**Returns:** distinct topics reachable from `topic_id` within `max_hops`, **excluding** `topic_id` itself.

This is the graph-side superpower of GraphRAG. After the vector store finds chunks about `embeddings`, the chat engine calls `get_connected_topics("embeddings", max_hops=2)` and adds those topics' chunks to the context — pulling in `vector-store`, `cosine-similarity`, `chunking`, etc., even if the user didn't mention them.

**Implementation realities:**

- Neo4j does this natively with `MATCH (start)-[*1..N]-(connected)` — proper variable-length pattern matching.
- DynamoDB and Cosmos implement **hop-1 only today** (they fetch direct neighbours via the edges table/container and stop). The `max_hops` parameter is accepted for contract compatibility but only affects Neo4j today. This is documented honesty: the cheap providers traded multi-hop traversal for cost.
- The result is **direction-agnostic**: edges in either direction count as a connection (a topic that *requires* you and one you *require* are both neighbours).

| Provider | Real `max_hops` support | 🫏 Donkey |
|----------|------------------------|-----------|
| Neo4j | Up to whatever you ask for; 2 is the default | The map-room actually walks the roads — second-hop towns appear too |
| DynamoDB | Hop-1 only (today) | The map only lists direct neighbours; further-out towns have to be fetched in a follow-up trip |
| Cosmos | Hop-1 only (today) | Same as DynamoDB — direct neighbours only |

> ⚠️ **The interface promises `max_hops`; only Neo4j honours `> 1` today.** Code paths that depend on multi-hop traversal degrade to hop-1 quality on AWS / Azure. Plan multi-hop fan-out client-side if you need it on those providers, or upgrade to a graph-native backend.

- 🫏 **Donkey:** `get_connected_topics` is the donkey's "what's nearby?" query. On the proper paper map (Neo4j) the donkey sees two roads ahead; on the rolled-up adjacency list (DynamoDB / Cosmos) the donkey only sees the towns directly adjacent.

---

## Method 5 — `get_all_topics()` and `get_full_graph()`

**Signatures:**

```python
async def get_all_topics(self) -> list[Topic]
async def get_full_graph(self) -> KnowledgeGraph     # topics + relationships
```

These power the wiki UI and the `/wiki/graph` endpoint. `get_full_graph` returns the full `KnowledgeGraph` Pydantic model (see `src/models.py`), which the frontend renders as a node-link diagram.

**Cost note:** both are O(N). On Neo4j they're a single `MATCH (t:Topic)` traversal; on DynamoDB/Cosmos they're a `scan` / `SELECT *`. For corpora in the low thousands of topics — the expected operating point — this is fine. Past ~10k topics, paginate or restrict by `source_repo`.

- 🫏 **Donkey:** "Hand me the whole map" and "list every town" — fine when the map fits on one wall, expensive when it doesn't.

---

## Method 6 — `topic_count()`

**Signature:** `async def topic_count() -> int`

Used by the `/health` endpoint to report graph size. Cheap on Neo4j (`count(t)`); on DynamoDB and Cosmos it's a `len(get_all_topics())` so the cost grows with the graph.

- 🫏 **Donkey:** "How many towns are on the map?" — the dashboard's heartbeat number.

---

## The Factory — How Config Picks a Provider

`src/graphstore/factory.py` mirrors the vector store factory exactly:

```python
def create_graph_store() -> BaseGraphStore:
    settings = get_settings()
    if settings.cloud_provider == CloudProvider.AWS:
        from src.graphstore.dynamodb_graph import DynamoDBGraphStore
        return DynamoDBGraphStore()
    elif settings.cloud_provider == CloudProvider.AZURE:
        from src.graphstore.cosmos_graph import CosmosGraphStore
        return CosmosGraphStore()
    else:
        from src.graphstore.neo4j_store import Neo4jGraphStore
        return Neo4jGraphStore()
```

Same lazy-import pattern, same `local`-by-default behaviour. **Critical:** the *same* `CLOUD_PROVIDER` setting picks both the vector and graph providers — you can't run Chroma + Cosmos or DynamoDB + Neo4j in production today. Local dev mixes them only because docker-compose runs Neo4j and ChromaDB side by side under `local`.

| Setting | Returned class |
|---------|----------------|
| `CLOUD_PROVIDER=local` (or unset) | `Neo4jGraphStore` |
| `CLOUD_PROVIDER=aws` | `DynamoDBGraphStore` |
| `CLOUD_PROVIDER=azure` | `CosmosGraphStore` |

- 🫏 **Donkey:** The yard sign at the gate also picks the map-room. Flip the sign and the donkey gets a new GPS warehouse *and* a new paper map — they always come as a pair.

---

## Invariants Every Provider Must Honour

| Invariant | Why | 🫏 Donkey |
|-----------|-----|-----------|
| `upsert_topic` is idempotent on `topic.id` | Re-ingest must not duplicate towns | The cartographer pencils once and only updates on subsequent visits |
| `upsert_relationship` is idempotent on `(source, type, target)` | Repeated extraction must not double the road | The road between two towns is drawn once, then footnotes are refreshed |
| `get_topic(missing_id)` returns `None`, not raises | Caller code stays simple | Looking up a town that doesn't exist returns "no such town" instead of crashing the trip |
| `get_connected_topics` excludes the start node | Otherwise traversal expansion would loop on the seed | The donkey doesn't list the starting town as one of the neighbours |
| `get_full_graph` returns a `KnowledgeGraph` Pydantic, not provider-native objects | UI and serialisation stay provider-agnostic | The cartographer hands over the map in a standard envelope, regardless of which workshop drew it |
| Edge direction is preserved | `USED_BY(A,B) ≠ USED_BY(B,A)` semantically | Roads are one-way drawings — the cartographer doesn't conflate them |
| All methods are async | FastAPI handlers don't block | The map-room never makes the donkey wait at the door |

- 🫏 **Donkey:** Seven house rules. Honour them and any new map-room can hang on the donkey's wall without changing the chat engine, gap detector, or wiki UI.

---

## Self-Test Questions

1. Why does the contract not include `delete_topic` or `delete_relationship`?
   *(Answer: deletions are rare and risky — losing a topic orphans every chunk that referenced it. Manual provider-side deletion forces a deliberate decision. Re-ingestion doesn't need delete because upserts overwrite.)*
2. The interface accepts `max_hops` on `get_connected_topics`. Two of three providers ignore it. Why is that ok in production?
   *(Answer: at this corpus size, hop-1 + LLM context stuffing covers most queries; the multi-hop superpower is reserved for the local Neo4j path used in dev/eval. Production AWS/Azure paths trade traversal depth for storage cost.)*
3. If you call `upsert_relationship` with a `source_id` that doesn't exist as a topic, what happens?
   *(Answer: depends on the provider — Neo4j's `MATCH ... MERGE` silently does nothing; DynamoDB/Cosmos write the edge anyway and you end up with a dangling reference. The graph extractor's dangling-edge filter is the upstream guard that prevents this.)*
4. Why is the same `CLOUD_PROVIDER` setting used to pick both stores?
   *(Answer: each provider trio is designed as a unit with matching cost and consistency stories. Mixing — e.g., DynamoDB vectors with Neo4j graph — is technically possible but adds two SDKs and two infra blueprints to a single deployment.)*
