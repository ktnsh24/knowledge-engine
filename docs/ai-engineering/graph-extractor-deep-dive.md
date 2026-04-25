# Deep Dive: The Graph Extractor

> **Study order:** #8 · **Difficulty:** ★★★★☆ (LLM I/O + JSON parsing + edge hygiene)
>
> **Files:** [`src/ingestion/graph_extractor.py`](../../src/ingestion/graph_extractor.py), [`src/llm/ollama.py`](../../src/llm/ollama.py), [`src/llm/bedrock.py`](../../src/llm/bedrock.py), [`src/llm/azure_openai.py`](../../src/llm/azure_openai.py)
>
> **Prerequisite:** [#7 — Ingestion Pipeline Deep Dive](ingestion-pipeline-deep-dive.md)
>
> **Companion:** [Graph Store Interface](graphstore-interface-deep-dive.md)

---

## Table of Contents

- [Why Extract a Graph at Ingest Time](#why-extract-a-graph-at-ingest-time)
- [The Contract: `extract_topics_and_relations`](#the-contract-extract_topics_and_relations)
- [The Prompt That Drives Extraction](#the-prompt-that-drives-extraction)
- [What Counts as a Topic vs a Relationship](#what-counts-as-a-topic-vs-a-relationship)
- [Edge Hygiene: The Dangling-Edge Filter](#edge-hygiene-the-dangling-edge-filter)
- [Confidence and Deduplication — What Actually Happens](#confidence-and-deduplication--what-actually-happens)
- [Cost Per File — Rough Numbers](#cost-per-file--rough-numbers)
- [Failure Modes](#failure-modes)
- [Self-Test Questions](#self-test-questions)

---

## Why Extract a Graph at Ingest Time

The vector store is built for "find chunks that look like this question". The graph is built for "what other concepts are connected to this concept?". Both views are useful; together they answer questions vectors alone can't (`"what depends on chunking?"` is a graph query, not a vector query).

The graph extractor is the cartographer who reads every envelope as it goes through pre-sort and pencils the relationships onto the paper map. It runs once at ingest time so chat-time queries can be cheap graph traversals instead of fresh LLM calls.

| Question vectors handle well | Question the graph handles well | 🫏 Donkey |
|------------------------------|--------------------------------|-----------|
| "Show me chunks about embeddings" | "What concepts are 2 hops from embeddings?" | The GPS warehouse finds the right shelf; the paper map finds the connecting roads to neighbouring towns the donkey didn't even ask about |
| "What does the docs say about chunking?" | "Which topics depend on chunking?" | The warehouse pulls envelopes mentioning chunking; the map shows which towns have a `REQUIRED_BY` road into it |
| "Find similar passages" | "Which two topics share the same evidence sentence?" | The warehouse ranks envelopes by GPS proximity; the map links towns by the footnoted road that justifies the connection |

- 🫏 **Donkey:** The cartographer at pre-sort is what turns "the donkey can find chunks" into "the donkey can also follow the roads between concepts". One extra LLM call per chunk at ingest time saves dozens of LLM calls per question at chat time.

---

## The Contract: `extract_topics_and_relations`

Every LLM provider implements this method (declared abstract on `BaseLLM`, see `src/llm/base.py` line 119):

```python
async def extract_topics_and_relations(self, text: str) -> dict:
    """
    Returns: {"topics": [...], "relationships": [...]}
    """
```

The orchestrator that calls it (`src/ingestion/graph_extractor.py`) is provider-agnostic:

```python
async def extract_and_store(text, graph_store, llm) -> dict:
    result = await llm.extract_topics_and_relations(text)
    topics = result.get("topics", [])
    relationships = result.get("relationships", [])

    topic_ids = set()
    for t in topics:
        topic = Topic(id=t["id"], name=t["name"], description=t.get("description", ""))
        await graph_store.upsert_topic(topic)
        topic_ids.add(t["id"])

    rel_count = 0
    for r in relationships:
        if r["source_id"] in topic_ids and r["target_id"] in topic_ids:
            rel = Relationship(
                source_id=r["source_id"],
                target_id=r["target_id"],
                relation_type=r.get("relation_type", "RELATED_TO"),
                evidence=r.get("evidence", ""),
            )
            await graph_store.upsert_relationship(rel)
            rel_count += 1

    return {"topics": len(topics), "relationships": rel_count}
```

That's the entire orchestration. Every provider boils down to "call the LLM, parse JSON, return the dict". The intelligence lives in the prompt.

| Concern | Where it lives | 🫏 Donkey |
|---------|----------------|-----------|
| What to extract | Provider prompt (next section) | The cartographer's notebook of what symbols mean — towns, roads, road types |
| Where to write it | `graph_store.upsert_topic` / `upsert_relationship` | The pencil that puts the new town and road onto the official paper map |
| Edge hygiene | The `if source_id in topic_ids and target_id in topic_ids` filter | The cartographer's rule: never draw a road to a town that wasn't surveyed today |
| Default relation type | Falls back to `"RELATED_TO"` if missing | If the cartographer didn't label the road, it's marked as a generic connection rather than dropped |

- 🫏 **Donkey:** The orchestrator is the cartographer's clerk — handles the paperwork, defends edge hygiene, and lets the cartographer (the LLM) focus on the actual reading and drawing.

---

## The Prompt That Drives Extraction

From `src/llm/ollama.py` (lines 28–46) — the Bedrock and Azure OpenAI providers use the same shape with provider-specific JSON-mode toggles:

```text
Extract topics and relationships from this text.
Return JSON only, no explanation:
{
  "topics": [{"id": "slug-name", "name": "Human Name", "description": "1 sentence"}],
  "relationships": [
    {
      "source_id": "...",
      "target_id": "...",
      "relation_type": "USED_BY|STORED_IN|REQUIRED_BY|PART_OF|RELATED_TO",
      "evidence": "sentence"
    }
  ]
}

TEXT:
{text[:3000]}
```

A separate one-line system prompt (`"You extract structured data. Return JSON only."`) overrides the default donkey-analogy prompt — at extraction time we want a JSON robot, not a storyteller.

After the LLM returns, the parser does:

```python
start = result.find("{")
end = result.rfind("}") + 1
return json.loads(result[start:end])
```

…and falls back to `{"topics": [], "relationships": []}` on any exception. That's the "dumb but safe" parser — if the LLM wrapped its JSON in prose, the brace-slicing rescues it; if the JSON is genuinely malformed, the chunk simply contributes nothing to the graph this run.

> ⚠️ **Text is truncated to 3000 chars before the prompt.** Long chunks (the chunker emits ~800-word chunks ≈ 4–6 KB) get clipped here. This is a deliberate cost guard for the local Ollama path; the cloud providers can override their own truncation in their providers if needed.

| Prompt element | Why it's there | 🫏 Donkey |
|----------------|----------------|-----------|
| Closed enum of `relation_type` | Keeps the graph traversable — five types you can query, not 50 free-form labels | The cartographer's pencil only has five colours; no "magenta-ish" roads sneak onto the official map |
| `id: "slug-name"` schema | Turns "Vector Store" and "vector store" into the same node `vector-store` across files | The town has one official name on the map regardless of how each delivery note spells it |
| `evidence: "sentence"` field | Audit trail — every edge can point to the sentence that justified it | Every road on the map has a footnote with the sentence the cartographer copied from the envelope |
| `Return JSON only` system prompt | Disables the global donkey storyteller mode for this call | The cartographer puts down the storybook and picks up the surveyor's tablet |
| `text[:3000]` truncation | Cost cap for the local model | The cartographer reads the first three pages of a long letter and trusts the chunker to cover the rest |

- 🫏 **Donkey:** The prompt is the cartographer's standing brief — five road colours, one official town name format, and a footnote on every road. Anything outside that brief gets thrown out by the parser.

---

## What Counts as a Topic vs a Relationship

The chunker has already cut documents into 800-word windows with a nearest-heading hint. So when the LLM sees a chunk, it's typically one section of one doc. From that, the LLM is asked to surface:

- **Topics** — proper-noun-ish AI-engineering concepts (`embeddings`, `vector-store`, `chunking-strategy`, `hnsw-index`, `feedback-loop`). Each gets a stable slug `id`, a human `name`, and a one-sentence `description`.
- **Relationships** — typed directed edges between two topics extracted in this same call:
  - `USED_BY` — concept A is consumed by concept B.
  - `STORED_IN` — concept A persists into B (e.g., `embeddings` STORED_IN `vector-store`).
  - `REQUIRED_BY` — B can't exist without A.
  - `PART_OF` — A is a component of B.
  - `RELATED_TO` — generic catch-all, also the default if the LLM omits the type.

The `Topic` and `Relationship` Pydantic models (see `src/models.py`) carry extra fields like `weight`, `source_repos`, and `created_at` that the LLM does not need to populate — defaults handle them.

- 🫏 **Donkey:** Topics are the towns on the paper map; relationships are the roads between them. Five road colours keep the map readable; everything else falls back to a generic grey road.

---

## Edge Hygiene: The Dangling-Edge Filter

This single line in `extract_and_store` is the most important quality control in the whole pipeline:

```python
if r["source_id"] in topic_ids and r["target_id"] in topic_ids:
```

Why it matters:

- LLMs love to hallucinate edges to entities they "know exist" from training but didn't actually extract from this chunk. Without the filter, the graph would slowly fill with edges to ghost nodes.
- Limiting edges to **topics surveyed in the same chunk** ties the relationship's `evidence` field to the literal text the LLM was reading. That's the audit trail that lets a human ask "where did this edge come from?" and see a real sentence.
- It does NOT prevent two chunks from contributing to the same node — `upsert_topic` is a `MERGE` in Neo4j and a `put_item` in DynamoDB / Cosmos, so the same `topic_id` extracted from chunk A and chunk B converges on one node.

| Without the filter | With the filter | 🫏 Donkey |
|--------------------|-----------------|-----------|
| Edges point to topics nobody surveyed | Every edge has both endpoints surveyed in the same call | The cartographer doesn't draw roads to towns nobody visited today |
| `evidence` cites a sentence about A but the edge connects to a phantom B | `evidence` actually mentions both A and B (because both were extracted from the same text window) | Every road footnote references both towns it connects |
| Graph traversal lands on stub nodes with no description | Every traversal lands on real nodes with names and descriptions | The donkey never arrives at a town with a blank signpost |

- 🫏 **Donkey:** The dangling-edge filter is the cartographer's professional ethic: "I do not draw roads to towns I did not survey." Costs one `set` membership check, saves the entire graph from rot.

---

## Confidence and Deduplication — What Actually Happens

The current implementation deliberately keeps both *light*:

- **No explicit confidence scoring per topic or edge.** The `Relationship.weight` field defaults to `1.0` and is not populated by the extractor today. If the LLM emits the same edge twice (across two chunks), the graph store's upsert overwrites the previous row at `1.0` — there's no "seen N times → weight = N" counter yet.
- **Topic deduplication is identity-based, not similarity-based.** Two chunks producing `id: "vector-store"` collapse into one node because the graph store treats `id` as the primary key. Two chunks producing `id: "vectorstore"` and `id: "vector-store"` would create two distinct nodes — the LLM is responsible for slugging consistently. In practice, the same prompt + the same model on similar text reliably produces the same slugs.
- **Relationship deduplication** uses the composite `f"{source_id}#{relation_type}#{target_id}"` (DynamoDB) / matching `source_id`/`target_id`/`relation_type` (Neo4j `MERGE`) / `f"{source_id}__{relation_type}__{target_id}"` (Cosmos). Same triple from two chunks converges on one edge; the second `evidence` overwrites the first.

This is intentional: keeping the graph layer simple lets the chat engine and gap detector use it as a stable substrate. Confidence-as-weight is a planned future extension; today it's a `1.0` everywhere placeholder.

| Aspect | Today | Planned/possible | 🫏 Donkey |
|--------|-------|------------------|-----------|
| Topic dedup | By exact `id` slug | LLM-side canonical-name lookup before extraction | The cartographer's town index is a strict spelling check; "Embeddings-Town" and "embeddings-town" are filed separately until a typo gets corrected |
| Edge dedup | By `(source, type, target)` triple | Could count occurrences and update `weight` | The cartographer overwrites the road's footnote each time a fresh sentence justifies the same connection |
| Confidence scoring | Not computed; `weight = 1.0` everywhere | Could be wired into traversal ranking | Every road is currently a single solid line; future maps may have thicker lines for roads paved by many delivery notes |

- 🫏 **Donkey:** The cartographer is honest but not yet quantitative — every road exists or doesn't, but none are marked "well-trodden" vs "anecdotal" yet.

---

## Cost Per File — Rough Numbers

A single chunk extraction is one LLM call with input ≈ 3000 chars (≈ 750 tokens) and output ≈ 200–500 tokens of JSON. A typical 800-word chunk is ≈ 4–6 KB, so the truncation kicks in for some chunks.

For one mid-size markdown file (≈ 5–10 chunks at default settings):

| Provider | Model | Input tokens | Output tokens | Approx cost / file |
|----------|-------|-------------:|--------------:|-------------------:|
| Local (Ollama) | `llama3.2` | ~7,500 | ~3,000 | €0 (CPU/GPU time only) |
| AWS Bedrock | `claude-haiku-4-5` | ~7,500 | ~3,000 | ~€0.003 (input ~$0.0001/1k, output ~$0.0005/1k) |
| Azure OpenAI | `gpt-4o-mini` | ~7,500 | ~3,000 | ~€0.002 |

Multiply by file count to size a full ingest. Ingesting six sibling repos with ~200 markdown files each ≈ 1,200 files × ~€0.003 = **~€3.60** per full re-ingest on AWS. That's why deterministic chunk IDs and dangling-edge filtering matter — running the pipeline frequently has to stay cheap.

| Cost lever | How to pull it | 🫏 Donkey |
|------------|----------------|-----------|
| Chunk size | `RAG_CHUNK_SIZE` ↑ → fewer chunks → fewer LLM calls per file | Bigger envelopes mean fewer cartographer reads per letter — but each read is bigger |
| Truncation cap | `text[:3000]` in the prompt | The cartographer reads only the first three pages of any one chunk; bigger chunks lose more context |
| Provider choice | Local for dev, Haiku for staging, GPT-4o-mini for Azure | Choose which cartographer you're paying — local apprentice is free but slow |
| Re-ingest discipline | Use `delete_by_source` + `upsert_topic` (idempotent) before re-ingesting changed files | The cartographer doesn't re-survey towns that haven't changed |

- 🫏 **Donkey:** Each ingest is a billable cartographer shift. Bigger envelopes, fewer letters, and a cheaper cartographer all reduce the bill — but they trade for context, granularity, and quality respectively.

---

## Failure Modes

| Failure | Behaviour | Recovery |
|---------|-----------|----------|
| LLM returns prose, no JSON | Brace-slicing fails → exception → fallback `{"topics": [], "relationships": []}` | Re-run; or switch provider for that file |
| LLM emits relationship with one bad endpoint | Filter drops the edge silently | Intentional — keep the map honest |
| LLM emits same topic twice in one call | Both `upsert_topic` calls hit the same key; second overwrites first | Harmless — same slug, same `MERGE` |
| LLM emits new `relation_type` outside the enum | Stored as-is on the edge | Harmless but pollutes the graph; tighten the prompt or post-validate if needed |
| Network failure mid-extraction | The orchestrator raises; chunks already extracted are persisted | Re-run the ingest — idempotent |

- 🫏 **Donkey:** Every failure mode degrades to "no edges drawn this round" rather than "wrong edges drawn". The dangling-edge filter and the `id`-as-key model make the cartographer's mistakes invisible to the next traversal.

---

## Self-Test Questions

1. Why is the relationship `relation_type` enumerated to five values instead of free-form?
   *(Answer: traversal predictability. The chat engine and gap detector can ask "give me everything `REQUIRED_BY` X" because the labels are bounded.)*
2. If the LLM extracts the topic `vector-store` from chunk A and `vectorstore` from chunk B, do you get one node or two?
   *(Answer: two — dedup is `id`-based. Tighten the prompt or add a post-extraction normaliser if this becomes a problem.)*
3. The dangling-edge filter rejects an edge to a topic that wasn't extracted in the same call. What happens if the same edge is extracted later from a different chunk where both endpoints ARE present?
   *(Answer: it lands cleanly. The filter is per-call, not global — it just refuses to take the LLM's word for an unverified endpoint.)*
4. Why is `text[:3000]` not a problem for our 800-word chunks?
   *(Answer: 800 words ≈ 4 800 chars on average — most chunks fit, the heaviest ones get clipped. Re-tune `RAG_CHUNK_SIZE` down or raise the truncation cap if your corpus is dense.)*
