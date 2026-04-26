# Deep Dive: The Wiki Generator — `src/wiki/generator.py`

> **Study order:** #16 · **Difficulty:** ★★★☆☆ — short file, but it is the
> component that turns the knowledge graph into *human-readable* per-topic
> articles that re-enter the corpus on the next ingest.
>
> **File:** [`src/wiki/generator.py`](../../src/wiki/generator.py) · **Calls into:**
> [LLM](llm-interface-deep-dive.md) (`generate_wiki_page`),
> [Vector store](vectorstore-interface-deep-dive.md) (`search`),
> [Graph store](graphstore-interface-deep-dive.md) (`get_all_topics`,
> `get_connected_topics`) · **Triggered by:** [`POST /wiki/rebuild`](../architecture-and-design/api-routes/wiki-endpoint-explained.md).

---

## Table of Contents

- [Why this file matters](#why-this-file-matters)
- [The two-method API](#the-two-method-api)
- [Where pages go on disk](#where-pages-go-on-disk)
- [The per-page recipe](#the-per-page-recipe)
- [Cost per generation](#cost-per-generation)
- [When to trigger a rebuild](#when-to-trigger-a-rebuild)
- [🚚 Courier explainer — the brochure printer](#-courier-explainer--the-brochure-printer)
- [Self-test questions](#self-test-questions)
- [What to read next](#what-to-read-next)

---

## Why this file matters

The wiki generator is the project's flywheel. It reads the *graph* (which
topics exist) and the *vector store* (which chunks describe each topic) and
asks the LLM to write a markdown article per topic. Those articles land in
`wiki-output/topics/*.md`. The next time `POST /ingest/run` fires, the wiki
folder is one of the source repos — meaning the wiki *itself* gets chunked,
embedded, and graphed alongside the original docs.

This is what makes the system "self-improving":

```text
human docs → ingestion → graph + vectors → wiki pages → re-ingestion →
            denser graph + better answers → better wiki on next rebuild
```

Without the wiki generator, all the gap-detection and feedback machinery would
have nowhere to deposit improvements. With it, every promoted candidate, every
👍 verified answer, and every newly-extracted relationship eventually shows up
as polished prose the next reader will find when they ask a question.

---

## The two-method API

```python
class WikiGenerator:
    def __init__(self, llm, vector_store, graph_store): ...
    async def generate_all(self) -> list[WikiPage]: ...
    async def generate_page(self, topic: Topic) -> WikiPage: ...
```

| Method | When it runs | What it does | 🚚 Courier |
|--------|--------------|--------------|-----------|
| `generate_all()` | Called by `POST /wiki/rebuild`; iterates over every topic in the graph and calls `generate_page()` per topic, then writes an index | Full rebuild — one article per known town plus a table of contents | Print every brochure in the catalogue, then print the catalogue itself; one full run of the brochure printer |
| `generate_page(topic)` | Called per-topic by `generate_all()`; can also be called directly if you want to refresh a single article | Pulls chunks from the vector store, neighbours from the graph, asks the LLM for the article + 🚚 analogy, writes the file | Print one tourist brochure for one specific town using everything the post office has filed about it |

`generate_all` deliberately wraps each `generate_page` in `try/except` and
logs the failure but **does not abort the run** — one bad topic should not
poison the rest of the rebuild.

---

## Where pages go on disk

```python
self.output_path = Path(settings.wiki_output_path) / "topics"
self.output_path.mkdir(parents=True, exist_ok=True)
```

| Path | Contents | 🚚 Courier |
|------|----------|-----------|
| `wiki-output/topics/{topic_id}.md` | One article per topic, written by the LLM, decorated with a `## 🔗 Connected Topics` footer linking to neighbours | One brochure per town, with the back cover listing the next towns over so readers can follow the road |
| `wiki-output/index.md` | Auto-generated index linking to every topic article, sorted by title | The brochure rack at the front of the post office — every printed brochure indexed for the next visitor |
| `wiki-output/feedback/verified-answers.md` | Written by the candidate store and the feedback processor (not the generator), but lives in the same tree so it is picked up by the next ingest | The supervisor's promoted-trip log — same filing cabinet, different drawer |
| `wiki-output/gaps/unanswered.md` | Written by the gap detector | The auditor's red-flag drawer in the same cabinet |
| `wiki-output/candidates/pending-review.md` | Written by the candidate store | The clipboard of off-road trips awaiting promotion |

`wiki_output_path` defaults to `./wiki-output` (see
[`src/config.py`](../../src/config.py), `WIKI_OUTPUT_PATH`).

---

## The per-page recipe

`generate_page()` does five things in order:

```python
wiki_top_k = max(settings.rag_top_k, 8)
chunks = await self.vector_store.search(topic.name, top_k=wiki_top_k)
context = "\n\n---\n\n".join([c.text for c in chunks])
sources = list({c.source_file for c in chunks})

connected = await self.graph_store.get_connected_topics(topic.id, max_hops=2)
connected_names = [t.name for t in connected]

result = await self.llm.generate_wiki_page(topic.name, context)
content = result["content"]
courier  = result["courier_analogy"]

if connected_names:
    footer = f"\n\n## 🔗 Connected Topics\n\n"
    footer += "\n".join(f"- [{t}]({t.lower().replace(' ', '-')}.md)" for t in connected_names)
    content += footer
```

| Step | Detail | 🚚 Courier |
|------|--------|-----------|
| 1. Wider net than chat | `wiki_top_k = max(settings.rag_top_k, 8)` — chat asks for 5 chunks, wiki asks for at least 8 | Brochure-writing needs more raw material than a single-trip delivery; the courier loads a heavier parcel just for printing day |
| 2. Use topic NAME as the query | `vector_store.search(topic.name, …)` — not the topic id, not a synthetic prompt | The courier asks the warehouse for "RAG Pipeline" the way a reader would search, not the slug `rag-pipeline` |
| 3. Pull 2-hop neighbours | `get_connected_topics(topic.id, max_hops=2)` — same hop budget as the chat engine | Walk two streets out from this town to find the neighbours worth linking to from the brochure back-cover |
| 4. Single LLM call | `llm.generate_wiki_page(topic_name, context)` returns `{"content": ..., "courier_analogy": ...}` | One commission to the writer per brochure — no chained prompts, no retries on partial output |
| 5. Append a navigation footer | `## 🔗 Connected Topics` with markdown links to `{name.lower().replace(' ', '-')}.md` | The back cover gets stamped with neighbour-town addresses so the next reader can follow the road |

The returned `WikiPage` model carries `topic_id`, `title`, `content`,
`courier_analogy`, `sources`, `connected_topics`, `generated_at`, `version`,
and `quality_score` — see [`src/models.py`](../../src/models.py) for the
full schema.

---

## Cost per generation

Wiki generation is the most LLM-heavy operation in the whole project — one
`generate_wiki_page` call per topic. Order-of-magnitude cost:

| Provider | Per-page input tokens (≈ 8 chunks × 800 chars ÷ 4 ≈ 1,600 in + topic name) | Per-page output (≈ 800 word article ≈ 1,000 tokens) | Per-page USD | 🚚 Courier |
|----------|---|---|---|-----------|
| Local (Ollama llama3.2) | ~1,800 in | ~1,000 out | $0.00 — runs on your machine | The local barn writer charges nothing but takes longer and writes a shorter brochure |
| AWS (Bedrock Claude Haiku 4.5) | ~1,800 in × $0.00025/1k ≈ $0.00045 | ~1,000 out × $0.00125/1k ≈ $0.00125 | ≈ $0.0017 per page | The AWS depot writer is fast and cheap per brochure; 100 topics ≈ $0.17 |
| Azure (GPT-4o-mini) | ~1,800 in × $0.00015/1k ≈ $0.00027 | ~1,000 out × $0.00060/1k ≈ $0.00060 | ≈ $0.0009 per page | The Azure hub writer is the cheapest per brochure today; 100 topics ≈ $0.09 |

(Token rates from `TOKEN_COSTS` in [`src/evaluation/evaluator.py`](../../src/evaluation/evaluator.py).)

A 100-topic graph rebuild therefore costs **at most a few cents** on either
cloud provider — cheap enough to schedule daily without thinking, but worth
gating behind an explicit `POST /wiki/rebuild` rather than running on every
ingest.

---

## When to trigger a rebuild

There is no automatic scheduler in `src/main.py`; rebuilds are explicit. The
intended triggers are:

| Trigger | Who fires it | Why |
|---------|--------------|-----|
| After a large ingest job | A human or CI script following `POST /ingest/run` | Many new topics likely landed in the graph; their brochures don't exist yet |
| After promoting a batch of candidates | The reviewer | Promoted answers are now in `verified-answers.md`; the next ingest will pull them in but their dedicated topic articles need refreshing |
| Periodically (cron / GH Actions) | Robot depot hand | Catches drift when source repos change without an explicit ingest |
| Never, in dev | You | If you are iterating on prompts, generating 100 articles per change is wasteful — call `generate_page()` for the one topic you care about |

The `WIKI_REBUILD_ON_CHANGE` setting exists in `src/config.py` (default
`True`) as a future hook for an event-driven rebuild — at the time of writing
nothing in the codebase reads it. Treat it as a planned switch, not a live
behaviour.

---

## 🚚 Courier explainer — the brochure printer

The wiki generator is the courier's brochure printer. Once a week (or whenever
you tell it to) the courier walks down the cartographer's list of every town on
the paper map and, for each one, pulls eight pages from the GPS warehouse that
mention that town, walks two streets out to find the neighbours, and hands the
whole bundle to the writer at the desk. The writer drafts a tourist brochure
for that town with a 🚚 analogy as the closing paragraph; the courier staples a
back cover listing the neighbour-town addresses and files the brochure in the
brochure rack at the front of the post office. The next time the post office
does its pre-sort, those brochures are sorted alongside the originals — so the
next reader who asks about the town finds the brochure, not just the raw
shipping manifests.

---

## Self-test questions

1. Why does `generate_page()` use `max(settings.rag_top_k, 8)` instead of just
   `settings.rag_top_k`?
2. The wiki generator calls `vector_store.search(topic.name, ...)`. Why the
   topic *name* rather than the topic *description*, and what would change if
   you used the description?
3. If `generate_page()` raises an exception inside `generate_all()`, what
   happens to the rest of the topics in that run?
4. Where do promoted-candidate Q&A pairs become available to the wiki
   generator — at the moment of promotion, or only after the next
   `POST /ingest/run`? Why?
5. Order-of-magnitude: how much does a 100-topic rebuild cost on AWS vs Azure
   vs local? Which provider would you schedule nightly, and which would you
   only trigger on demand?

---

## What to read next

- [Chat Engine Deep Dive](chat-engine-deep-dive.md) — the consumer of the
  wiki articles via the next ingest cycle.
- [LLM Interface](llm-interface-deep-dive.md) — the `generate_wiki_page`
  contract called per topic.
- [Feedback Loop Deep Dive](feedback-loop-deep-dive.md) — how
  `verified-answers.md` reaches the wiki tree.
- [Ingestion Pipeline Deep Dive](ingestion-pipeline-deep-dive.md) — how the
  generated `wiki-output/topics/*.md` is folded back into the corpus.
