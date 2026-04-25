# Deep Dive: Graph Store Providers

> **Study order:** #12 · **Difficulty:** ★★★★☆ (three radically different storage models behind one contract)
>
> **Files:** [`src/graphstore/neo4j_store.py`](../../src/graphstore/neo4j_store.py), [`src/graphstore/dynamodb_graph.py`](../../src/graphstore/dynamodb_graph.py), [`src/graphstore/cosmos_graph.py`](../../src/graphstore/cosmos_graph.py)
>
> **Prerequisite:** [#11 — Graph Store Interface](graphstore-interface-deep-dive.md)
>
> **Companion:** [Vector Store Providers](vectorstore-providers-deep-dive.md)

---

## Table of Contents

- [Three Map Workshops, One Contract](#three-map-workshops-one-contract)
- [Head-to-Head Comparison](#head-to-head-comparison)
- [Provider 1 — Neo4j (Local)](#provider-1--neo4j-local)
- [Provider 2 — DynamoDB Adjacency List (AWS)](#provider-2--dynamodb-adjacency-list-aws)
- [Provider 3 — Cosmos DB NoSQL (Azure)](#provider-3--cosmos-db-nosql-azure)
- [Choosing a Provider](#choosing-a-provider)
- [Self-Test Questions](#self-test-questions)

---

## Three Map Workshops, One Contract

All three providers implement [`BaseGraphStore`](graphstore-interface-deep-dive.md). The interface promises seven methods; the reality is that the *quality* of `get_connected_topics` differs sharply because only Neo4j is graph-native — DynamoDB and Cosmos store adjacency lists in tables / documents and emulate traversal.

| Dimension | Neo4j (local) | DynamoDB (AWS) | Cosmos DB NoSQL (Azure) |
|-----------|---------------|----------------|--------------------------|
| Backing tech | Neo4j Community Edition (Docker) | Two DynamoDB tables (topics, edges) | Two Cosmos containers (topics, edges) |
| Query language | Cypher | DynamoDB scan + Python filter | SQL-on-JSON |
| Real multi-hop traversal | ✅ Native, any hop count | ❌ Hop-1 only | ❌ Hop-1 only |
| Cost model | €0 (Docker on your laptop) | DynamoDB on-demand pay-per-request | Cosmos serverless (RU-per-request) |
| Practical scale | ~1M nodes before tuning | ~100k topics (scan cost) | ~100k topics (scan cost) |
| When to use | Dev, eval, anything needing multi-hop | AWS-native, hop-1 fan-out is enough | Azure-native, hop-1 fan-out is enough |

- 🫏 **Donkey:** Three paper maps. Neo4j is drawn in proper graph ink with all the roads visible at once. DynamoDB is the same map rolled up as two columns of "from–to" rows. Cosmos is the map pinned to the wall as one document per town and one per road.

---

## Head-to-Head Comparison

| Concern | Neo4j | DynamoDB | Cosmos | 🫏 Donkey |
|---------|-------|----------|--------|-----------|
| Setup time | `docker compose up -d neo4j` | `terraform apply` (two tables) | `terraform apply` (database + two containers) | The local map-room opens in seconds; AWS and Azure ones need a one-time blueprint |
| Hop-1 traversal cost | One Cypher query | One scan + N point reads | One SQL query + N point reads | All three work the same for the next-town question; only Neo4j scales gracefully past that |
| Hop-2+ traversal cost | One Cypher query (Neo4j walks for you) | Hop-1 only — manual fan-out from the application | Hop-1 only — manual fan-out from the application | The donkey can ask "what's two roads away?" only on the Neo4j map; the others need a return trip |
| `MERGE` semantics | Native | Emulated via `put_item` overwrite | Emulated via `upsert_item` | All three end up idempotent on the right key, just by different mechanisms |
| Edge identity | Pattern `(a)-[r:TYPE]->(b)` | Composite `f"{src}#{type}#{tgt}"` partition key | Composite `f"{src}__{type}__{tgt}"` document id | Same triple on the road label; three different ways of writing it on the shelf |
| Best at | Real graph queries, dev, eval | Cheap AWS deployment with shallow traversal | Cheap Azure deployment with shallow traversal | Pick the workshop that matches how deep the donkey needs to walk |

---

## Provider 1 — Neo4j (Local)

**File:** `src/graphstore/neo4j_store.py` (107 lines)

The only graph-native provider. Runs as Neo4j Community Edition in Docker (free, no licence) and supports all of Cypher.

**Construction (lines 16–21):** an async driver pointed at `bolt://localhost:7687` with the configured user/password.

**Topic upsert (lines 23–34):**

```cypher
MERGE (t:Topic {id: $id})
SET t.name = $name,
    t.description = $description,
    t.source_repos = $source_repos,
    t.updated_at = datetime()
```

`MERGE` is the native idempotent operation — find-or-create on `id`, then `SET` updates the rest. `updated_at = datetime()` is set every time, so the freshness of any topic is queryable.

**Relationship upsert (lines 36–44):** parameterises the relation type into the Cypher template:

```cypher
MATCH (a:Topic {id: $src}), (b:Topic {id: $tgt})
MERGE (a)-[r:RELATION_TYPE]->(b)
SET r.weight = $weight, r.evidence = $evidence
```

Note the **`MATCH` first**: if either endpoint doesn't exist, the `MERGE` silently does nothing. This is the in-store version of the graph extractor's dangling-edge filter — defence in depth.

**Connected topics (lines 59–72):**

```cypher
MATCH (start:Topic {id: $id})-[*1..max_hops]-(connected:Topic)
WHERE connected.id <> $id
RETURN DISTINCT connected
```

`[*1..max_hops]` is Cypher's variable-length path syntax — Neo4j walks the graph for you. This is the one operation that justifies running a graph database. `max_hops=2` typically returns the immediate "supporting cast" of a topic (e.g. `embeddings` → `vector-store`, `chunking`, `cosine-similarity`).

**Setup snippet:**

```bash
# .env
CLOUD_PROVIDER=local
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=knowledge123

# infra
docker compose up -d neo4j
# Browser at http://localhost:7474 to inspect the graph
```

| Strength | Caveat | 🫏 Donkey |
|----------|--------|-----------|
| Real multi-hop traversal | Single container — no replication for free tier | The proper paper map shows every road at every distance; if the workshop floods, you start over |
| Cypher is purpose-built for graphs | One more skill to learn for a Python team | The cartographer speaks the universal map dialect; new staff need a week to learn it |
| Free Community Edition | Enterprise features (clustering, RBAC) are paid | The free workshop is one room; bigger workshops cost a licence |
| `MATCH`-first edge upsert defends against dangling edges | Slightly slower than blind insert | The cartographer refuses to draw a road to a missing town; the check costs a beat |

- 🫏 **Donkey:** The local Neo4j map-room is the donkey's reference workshop — proper graph ink, every road visible, multi-hop traversal in one query.

---

## Provider 2 — DynamoDB Adjacency List (AWS)

**File:** `src/graphstore/dynamodb_graph.py` (107 lines)

The "no Neptune" play. Neptune costs €0.50–0.70/hour minimum even idle; an adjacency list in DynamoDB is **two tables** that cost cents at the corpus sizes we care about.

**Schema (lines 17–21):**

- `<dynamodb_graph_table>-topics` — partition key `topic_id`, attributes `name`, `description`, `source_repos`.
- `<dynamodb_graph_table>-edges` — partition key `edge_id` (composite `f"{source_id}#{relation_type}#{target_id}"`), attributes `source_id`, `target_id`, `relation_type`, `weight`, `evidence`.

The composite `edge_id` is the idempotency trick: re-asserting the same triple writes to the same item, overwriting the previous evidence and weight.

**Topic upsert (lines 23–32):** plain `put_item` — DynamoDB's `put_item` is overwrite-on-conflict, so it's `MERGE`-equivalent for the same `topic_id`.

**Relationship upsert (lines 34–45):** plain `put_item` to the edges table with the composite key. `weight` is stored as a **string** (`str(rel.weight)`) because DynamoDB's `Number` type via `boto3.resource` requires `Decimal`, and stringifying is simpler — converted back to `float` at read time.

**Connected topics (lines 59–80):** **hop-1 only.**

```python
result = self.edges_table.scan(
    FilterExpression=Attr("source_id").eq(topic_id) | Attr("target_id").eq(topic_id)
)
neighbour_ids = set()
for item in result.get("Items", []):
    if item["source_id"] != topic_id:
        neighbour_ids.add(item["source_id"])
    if item["target_id"] != topic_id:
        neighbour_ids.add(item["target_id"])
# Then point-read each neighbour from the topics table.
```

The `max_hops` parameter is accepted for contract compatibility but ignored — the implementation walks one ring of edges and returns. Multi-hop fan-out is the caller's job.

**Why a scan, not a query?** The edges table doesn't have a GSI on `source_id` / `target_id` today (each one would add ~30% storage cost). At sub-100k edges, a scan with on-demand pricing is cents per call.

**Full graph (lines 91–103):** scans both tables — fine for the dashboard, expensive at scale. The same scaling caveat applies: planned operating point is the low thousands of topics.

**Setup snippet:**

```bash
# .env
CLOUD_PROVIDER=aws
AWS_REGION=eu-central-1
DYNAMODB_GRAPH_TABLE=knowledge-engine-graph
# Two tables get created: knowledge-engine-graph-topics and knowledge-engine-graph-edges

# infra
cd terraform/aws && terraform apply
```

| Strength | Caveat | 🫏 Donkey |
|----------|--------|-----------|
| €0 idle, cents per active operation | Hop-1 only — multi-hop needs application-side fan-out | The rolled-up adjacency list shows direct neighbours instantly; further-out towns need a follow-up trip |
| No Neptune licence | Scans don't scale past ~100k topics | The cheap workshop replaces the conveyor belt with hand-walked aisles; brilliant at small scale, slow at warehouse-chain size |
| Composite `edge_id` makes upsert idempotent | Adding GSIs for traversal would raise storage cost ~30% | The same road label is one row no matter how many times it's re-drawn; aisle indexes would speed lookups but cost shelf space |

- 🫏 **Donkey:** The AWS workshop trades the proper paper map for a stack of "from–to" cards in two filing cabinets. Cheap, idempotent, and good enough for one ring of neighbours per question.

---

## Provider 3 — Cosmos DB NoSQL (Azure)

**File:** `src/graphstore/cosmos_graph.py` (120 lines)

The "no Gremlin / Graph API" play, mirroring the DynamoDB approach in spirit. Azure offers a Cosmos DB Gremlin API but it's pricier and locks you into a graph-only billing model. The NoSQL API gives the same raw storage at half the RU cost for our access pattern.

**Schema (lines 34–39):**

- Database `azure_cosmos_database` (default `knowledge-engine`).
- Container `topics` — document id = `topic.id`, partition key = id (single-document partitions; cheap for point reads).
- Container `edges` — document id = `f"{source_id}__{relation_type}__{target_id}"`.

**Topic upsert (lines 41–48):** `await self._topics.upsert_item(...)`. Cosmos's `upsert_item` is the documented idempotent operation — find-or-replace by `id`.

**Relationship upsert (lines 50–60):** same pattern with the composite `id`.

**Connected topics (lines 72–93):** **hop-1 only**, like DynamoDB:

```python
query = "SELECT * FROM c WHERE c.source_id = @id OR c.target_id = @id"
items = [item async for item in self._edges.query_items(
    query=query,
    parameters=[{"name": "@id", "value": topic_id}],
)]
# Build neighbour set, point-read each from topics container.
```

Cosmos charges in Request Units (RU). A point-read of a small document is ~1 RU; a SQL query that scans a container is `O(documents) × ~1 RU`. At sub-100k topics this is well within the serverless free tier on a calm day, and ~€0.25 per thousand RU after.

**Lazy container init (lines 34–39):** `_ensure_containers()` is awaited at the top of every public method. The first call wires up the container clients; subsequent calls are a single `if` check. This handles the "first request after deploy" case without an explicit init step.

**Full graph (lines 103–113):** two `SELECT * FROM c` queries — same scaling caveat as DynamoDB.

**Setup snippet:**

```bash
# .env
CLOUD_PROVIDER=azure
AZURE_COSMOS_ENDPOINT=https://<account>.documents.azure.com:443/
AZURE_COSMOS_KEY=<primary-key>
AZURE_COSMOS_DATABASE=knowledge-engine
# Two containers required: topics and edges

# infra
cd terraform/azure && terraform apply
# Create the database and the two containers (topics, edges) via the module.
```

| Strength | Caveat | 🫏 Donkey |
|----------|--------|-----------|
| Cheaper than Gremlin API for this access pattern | Hop-1 only, like the DynamoDB provider | The wall-pinned document-per-town map shows neighbours fast but doesn't reveal the wider road network |
| Auto-wires containers at first request | Manual schema migration if you change container layouts | The workshop opens its filing cabinets the first time the cartographer arrives; reorganising means closing the workshop |
| Serverless RU billing — cheap on idle days | RU bills can spike on full-graph dashboards | Pay-per-trip pricing rewards quiet weeks and punishes you for asking "give me the whole map" twice an hour |

- 🫏 **Donkey:** The Azure workshop pins the map as separate documents — one per town, one per road. Hop-1 is fast, hop-2 needs another trip, and the rent is paid by the question.

---

## Choosing a Provider

| Situation | Pick | Reason |
|-----------|------|--------|
| Building, demo-ing, eval-ing GraphRAG depth | Neo4j (local) | Only provider with real multi-hop traversal |
| AWS deployment, hop-1 traversal sufficient | DynamoDB adjacency | Cheapest by far at this scale; matches the vector store pricing story |
| AWS deployment, multi-hop required | Not in this repo today (Neptune was rejected on cost) | Adjacency-list emulation past hop-1 isn't competitive |
| Azure deployment, hop-1 traversal sufficient | Cosmos DB NoSQL | Cheapest Azure-native option; matches Azure AI Search story |
| Azure deployment, multi-hop required | Cosmos DB Gremlin API (would need a new provider) | Native graph queries, but pricier |

| Decision | 🫏 Donkey |
|----------|-----------|
| Neo4j locally, always | The donkey's reference paper map is always within reach for dev and eval |
| DynamoDB / Cosmos in cloud, hop-1 only | The donkey accepts a shallower map outdoors in exchange for no rent |
| Multi-hop in production = upgrade required | If the donkey needs to see two roads ahead in cloud, the workshop has to upgrade to a real graph backend |

- 🫏 **Donkey:** The contract guarantees the donkey can hang any of three maps on the wall. Pick the one whose ink — proper graph, adjacency rows, or document pages — fits the question shapes the donkey is asked most.

---

## Self-Test Questions

1. Why is `MATCH` used before `MERGE` in the Neo4j relationship upsert?
   *(Answer: it forces both endpoints to exist before the edge is drawn. If either is missing, the `MERGE` silently does nothing — defence in depth against the same dangling-edge problem the extractor's filter prevents.)*
2. The DynamoDB and Cosmos providers ignore `max_hops`. What does the chat engine actually get when it asks for hop-2?
   *(Answer: the same set as hop-1. Multi-hop fan-out has to be done client-side — issue another `get_connected_topics` for each first-hop neighbour and union the results.)*
3. Why store `weight` as a string in the DynamoDB provider?
   *(Answer: `boto3.resource` requires `Decimal` for the Number type, which is awkward to round-trip. Stringifying floats and parsing back is simpler at our scale.)*
4. Cosmos uses `__` between source/type/target in its composite id; DynamoDB uses `#`. Why different separators?
   *(Answer: pure convention — neither character can appear in a slug-format topic id. Both are stable for the lifetime of the data; just don't mix providers without re-indexing.)*
