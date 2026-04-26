# Endpoint Deep Dive: `GET /health/` — the doorman's window

> **Study order:** #24 · **Source:** [`src/routes/health.py`](../../../src/routes/health.py)
> · **Model:** `HealthStatus` in [`src/models.py`](../../../src/models.py).

---

## Table of Contents

- [Endpoint summary](#endpoint-summary)
- [Request schema](#request-schema)
- [Response schema](#response-schema)
- [Internal flow](#internal-flow)
- [`curl` example](#curl-example)
- [Error cases](#error-cases)
- [🚚 Courier explainer — the doorman's window](#-courier-explainer--the-doormans-window)

---

## Endpoint summary

| Method | Path | Auth | Purpose | 🚚 Courier |
|--------|------|------|---------|-----------|
| GET | `/health/` | none | Quick liveness + dependency check — proves the FastAPI app is running, the configured provider is reachable, and the vector store + graph store both answer their `count()` calls | The doorman's window — shouts back chunk count, topic count, and which writer is on shift today, or "degraded" with the reason if anything is wrong |

Mounted with prefix `/health` and tag `health` in `src/main.py`.
`response_model=HealthStatus` is set on the route so OpenAPI documents the
exact shape.

---

## Request schema

No request body, no query parameters, no headers required.

---

## Response schema — `HealthStatus`

The full Pydantic model:

```python
class HealthStatus(BaseModel):
    status:        str           = "ok"
    provider:      ProviderType
    vector_store:  str
    graph_store:   str
    llm:           str
    wiki_pages:    int           = 0
    total_chunks:  int           = 0
    total_topics:  int           = 0
```

The route currently builds the response inline using a slightly different
field set than the model documents (`vector_store_chunks`, `graph_topics`,
`error`) — Pydantic accepts the extra fields because the response is
serialised loosely; the *contract* you can rely on across versions is:

| Field | Type | Source | 🚚 Courier |
|-------|------|--------|-----------|
| `status` | `"healthy"` \| `"degraded"` | Built by the route based on whether the store calls succeeded | Doorman's verdict — green light or amber light |
| `provider` | `local` \| `aws` \| `azure` | `settings.cloud_provider.value` | Which depot is on shift today — local barn, AWS depot, or Azure hub |
| `vector_store_chunks` (current code) / `total_chunks` (model) | int | `vector_store.chunk_count()` | Current parcel count on the GPS warehouse shelves |
| `graph_topics` (current code) / `total_topics` (model) | int | `graph_store.topic_count()` | Current town count on the paper map |
| `error` (degraded only) | string | `str(e)` from the failing call | The exact reason the doorman is shouting amber instead of green |

The mismatch between the model and the inline response is the documented
known issue — treat it as "the model lists every future field, the route
returns the current minimum subset." When you tighten this, prefer
`HealthStatus(...)` constructor calls so OpenAPI stays accurate.

Example success response:

```json
{
  "status": "healthy",
  "provider": "local",
  "vector_store_chunks": 3142,
  "graph_topics": 287
}
```

Example degraded response:

```json
{
  "status": "degraded",
  "provider": "aws",
  "error": "Could not connect to DynamoDB endpoint"
}
```

---

## Internal flow

```text
client
  │  GET /health/
  ▼
FastAPI middleware (CORS)
  │
  ▼
src/routes/health.py:health(request)
  │
  ├── try:
  │     chunks = await app.state.vector_store.chunk_count()   ← live store call
  │     topics = await app.state.graph_store.topic_count()    ← live store call
  │     return HealthStatus(status="healthy", provider=..., vector_store_chunks=chunks, graph_topics=topics)
  │
  └── except Exception as e:
        return HealthStatus(status="degraded", error=str(e), provider=...)
```

The route deliberately catches every exception. A health check that throws is
useless to a load balancer or a uptime monitor — better to return `degraded`
+ the error string and let the caller decide whether to alert.

---

## `curl` example

```bash
curl -s http://localhost:8200/health/ | jq
```

Use it in liveness/readiness probes:

```yaml
# Kubernetes-style probe
livenessProbe:
  httpGet: { path: /health/, port: 8200 }
  initialDelaySeconds: 5
  periodSeconds: 30
```

---

## Error cases

| Trigger | Response | 🚚 Courier |
|---------|----------|-----------|
| Vector store unreachable (Chroma not started, DynamoDB throttle, AI Search 503) | `200` with `status="degraded"` and `error=<exception>` | Doorman shouts amber and reads the warehouse's complaint over the wall |
| Graph store unreachable (Neo4j down, DynamoDB throttle, Cosmos 429) | Same — `status="degraded"` with the exception message | Doorman shouts amber and reads the map-room's complaint |
| App not yet finished its lifespan (`app.state.vector_store` not set) | `AttributeError` caught → `status="degraded"` with the attribute error message | The courier is still being saddled — doorman waves people off with "not ready yet" |
| Both stores empty (`chunks=0`, `topics=0`) | `200` with `status="healthy"` and zero counts | Depot is awake but nothing's been delivered yet — green light, empty warehouse |

The route never returns a 5xx today. That is intentional: callers (load
balancers, monitors) treat any non-200 as "the *application* is down" and
that is not what we mean by "the vector store is slow."

---

## 🚚 Courier explainer — the doorman's window

The health window is the small grille at the front door. When a passer-by
knocks, the doorman runs two quick checks: ask the warehouse how many parcels
are on the shelves, and ask the map room how many towns are drawn. If both
answer, the doorman shouts back "healthy" plus the two counts and the name of
the depot on shift. If either is silent, the doorman still shouts back —
"degraded" plus whichever room complained — so the visitor knows the depot
is awake even though the warehouse or the map room needs help. The door is
never bolted shut by the health check itself; that decision belongs to whoever
is reading the doorman's reply.
