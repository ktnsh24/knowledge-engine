# Deep Dive: The LLM Interface — `src/llm/base.py`

> **Study order:** #13 · **Difficulty:** ★★☆☆☆ — abstract class is small, but it
> hides three different jobs the courier is asked to do (answer, extract, write a wiki page).
>
> **File:** [`src/llm/base.py`](../../src/llm/base.py) · **Implementations:**
> [Ollama](llm-providers-deep-dive.md#1-ollama-local), [Bedrock](llm-providers-deep-dive.md#2-aws-bedrock),
> [Azure OpenAI](llm-providers-deep-dive.md#3-azure-openai) · **Used by:**
> [Chat Engine](chat-engine-deep-dive.md), [Wiki Generator](wiki-generator-deep-dive.md),
> [Graph Extractor](graph-extractor-deep-dive.md), [Evaluator](evaluation-framework-deep-dive.md).

---

## Table of Contents

- [Why this file matters](#why-this-file-matters)
- [The contract — three abstract methods](#the-contract--three-abstract-methods)
- [The two system prompts (and one toggle)](#the-two-system-prompts-and-one-toggle)
- [The factory — env-driven provider selection](#the-factory--env-driven-provider-selection)
- [DE parallel — strategy pattern you already know](#de-parallel--strategy-pattern-you-already-know)
- [Why three methods, not one](#why-three-methods-not-one)
- [What every implementer must promise](#what-every-implementer-must-promise)
- [🚚 Courier explainer — the writing-desk rules](#-courier-explainer--the-writing-desk-rules)
- [Self-test questions](#self-test-questions)
- [What to read next](#what-to-read-next)

---

## Why this file matters

`src/llm/base.py` is the **contract** every LLM provider must satisfy before the
chat engine, the wiki generator, or the graph extractor will accept it. It is what
lets `CLOUD_PROVIDER=local|aws|azure` swap one model for another with **zero code
changes** in the rest of the project. Think of it as a job description posted on
the depot wall: any courier that wants to sit at the writing desk must be able to
do these three things, in this order, returning these shapes.

It is **also** where the courier analogy becomes a hard contract — the
`COURIER_SYSTEM_PROMPT` constant lives in this file and is wired into every chat
call by default, so every answer the system ships is required to include a 🚚
analogy. That is not decoration; it is the project's signature.

---

## The contract — three abstract methods

```python
class BaseLLM(ABC):
    @abstractmethod
    async def complete(self, question: str, context: str,
                       system_prompt: str = COURIER_SYSTEM_PROMPT,
                       temperature: float = 0.1) -> str: ...

    @abstractmethod
    async def extract_topics_and_relations(self, text: str) -> dict: ...

    @abstractmethod
    async def generate_wiki_page(self, topic_name: str, context: str) -> dict: ...
```

| # | Method | Inputs | Returns | Used by | 🚚 Courier |
|---|--------|--------|---------|---------|-----------|
| 1 | `complete` | question + retrieved context + system prompt + temperature | plain answer string (with the 🚚 analogy embedded) | [Chat engine](chat-engine-deep-dive.md) — answer the user's question grounded in the GraphRAG context | The courier at the writing desk taking a question plus the parcel contents and writing a shipping manifest that always begins with the courier-on-route analogy |
| 2 | `extract_topics_and_relations` | a chunk of markdown text | `{"topics": [...], "relationships": [...]}` JSON | [Graph extractor](graph-extractor-deep-dive.md) — turn each ingested chunk into nodes + edges for the paper map | The courier reading the day's letters and pencilling in fresh towns and the roads between them onto the cartographer's draft map |
| 3 | `generate_wiki_page` | a topic name + supporting chunks | `{"content": markdown, "courier_analogy": "🚚 …"}` | [Wiki generator](wiki-generator-deep-dive.md) — write a per-topic article that is then re-ingested next run | The courier writing a tourist brochure for a specific town using everything the post office has filed about it, then leaving it at the printer |

All three methods are `async` because every concrete provider (Ollama HTTP, AWS Bedrock SDK, Azure OpenAI SDK) is I/O-bound — the chat engine is happy to await them in parallel with vector and graph lookups.

---

## The two system prompts (and one toggle)

The file exports three constants that are arguably more important than the abstract methods, because they are what the courier actually reads before every job:

| Constant | When it is used | What it forbids / allows | 🚚 Courier |
|----------|-----------------|--------------------------|-----------|
| `COURIER_SYSTEM_PROMPT` | Default for `complete()`. Used when the gap detector says HIGH or PARTIAL confidence. | Forces a 🚚 analogy on every answer; tells the courier to ground claims in the provided context only. | The strict desk rule — the courier may only write things it found in the parcel and must always sign off with the road analogy |
| `COURIER_SYSTEM_PROMPT_LAX` | Used when `SYSTEM_PROMPT_MODE=lax` (Tier-1 Lab 5). | Same 🚚 rule, but allows the courier to add training-data knowledge if context is thin. | The relaxed desk rule used to demonstrate hallucination explosion when the courier is allowed to invent |
| `FALLBACK_SYSTEM_PROMPT` | Used when the gap detector returns `GAP` (no usable context). | Forces a `⚠️ This answer is from LLM training knowledge` banner before any other text, plus the 🚚 analogy. | The honest off-road rule — the courier is allowed to deliver from memory but must stamp the parcel with a warning so the supervisor knows to verify it |

The helper `get_system_prompt(mode)` picks between strict and lax based on the
`system_prompt_mode` setting. The chat engine selects the fallback variant only
when confidence has already been computed as `GAP`.

---

## The factory — env-driven provider selection

```python
# src/llm/factory.py
def create_llm() -> BaseLLM:
    settings = get_settings()
    if settings.cloud_provider == CloudProvider.AWS:
        from src.llm.bedrock import BedrockLLM
        return BedrockLLM()
    elif settings.cloud_provider == CloudProvider.AZURE:
        from src.llm.azure_openai import AzureOpenAILLM
        return AzureOpenAILLM()
    else:
        from src.llm.ollama import OllamaLLM
        return OllamaLLM()
```

`create_llm()` is called exactly once during FastAPI startup
(`src/main.py::lifespan`) and the resulting instance is stashed on
`app.state.llm`. Routes get it via `request.app.state.llm` — no global, no DI
framework. The provider imports are **deferred inside the branches** so a missing
`boto3` or `openai` package never breaks the local-only flow.

---

## DE parallel — strategy pattern you already know

```
Data engineering (you know this)        Knowledge engine (this file)
──────────────────────────────────      ────────────────────────────────────
class BaseStorage(ABC):                  class BaseLLM(ABC):
    def query(sql) -> rows                   async complete(q, ctx) -> str
    def insert(rows)                         async extract(text) -> dict
                                             async generate_wiki(topic, ctx) -> dict

DynamoDB / Postgres / S3                 Ollama / Bedrock / Azure OpenAI
(swap by env var)                        (swap by CLOUD_PROVIDER env var)
```

If you have ever written a `BaseRepository` with three implementations behind a
factory, you have written this pattern. The only AI-specific piece is **what** the
methods do — the **shape** is identical.

---

## Why three methods, not one

A single `generate(prompt) -> str` would be enough to *implement* all three
behaviours, but the interface deliberately splits them so that:

1. **Each call site can pick the right system prompt and temperature** without
   sprinkling magic strings through the codebase. `complete()` defaults to the
   strict prompt at temperature 0.1; `extract_topics_and_relations()` overrides
   the system prompt to *"Return JSON only, no explanation."*
2. **Return shape is enforced.** `extract_topics_and_relations` always returns
   `{"topics": [...], "relationships": [...]}` — providers that fail to parse
   the model's JSON return empty lists rather than raising, so a single bad
   chunk cannot abort an ingest run.
3. **Tests can mock one method at a time.** `test_chat_engine.py` only needs to
   patch `complete`; `test_ingestion.py` only needs to patch
   `extract_topics_and_relations`.

---

## What every implementer must promise

Every concrete provider — see [LLM Providers Deep Dive](llm-providers-deep-dive.md) — has to satisfy:

| Promise | Why it matters | 🚚 Courier |
|---------|----------------|-----------|
| `complete()` returns a non-empty string that **includes** the `🚚` character when the prompt asked for it | Gap-detector's `_extract_courier()` searches for `🚚` to populate `ChatResponse.courier_analogy`; missing it falls back to a generic line | If the courier forgets to sign the shipping manifest with the road analogy, the dispatcher writes a default one in pencil — but the trip is logged as sloppy |
| `extract_topics_and_relations()` always returns the keys `topics` and `relationships`, even on parse failure | The graph extractor calls `.get("topics", [])` and `.get("relationships", [])`; missing keys would crash an ingest mid-run | If the cartographer hands back a blank sheet instead of a malformed one, the post office can keep sorting the rest of the day's mail |
| `generate_wiki_page()` returns both `content` and `courier_analogy` keys | The wiki page model requires the analogy field; the writer would otherwise have to re-extract it | The brochure printer expects two envelopes — full text and a one-line tagline — every time, no exceptions |
| All three methods are `async` and never block the event loop on long sync work | Bedrock's `boto3` is sync, so `BedrockLLM` wraps it with `run_in_executor` rather than calling it directly | Heavy Bedrock errands are handed to a courier so the dispatcher's desk stays free for the next request |

---

## 🚚 Courier explainer — the writing-desk rules

🚚 `BaseLLM` is the writing-desk in the corner of the depot. Three jobs land on
the desk every day: **answer the customer's question** (`complete`), **draw new
towns onto the map** (`extract_topics_and_relations`), and **write the tourist
brochure for one town** (`generate_wiki_page`). The desk has a strict rule taped
to it (the `COURIER_SYSTEM_PROMPT`): *every note must end with the courier-on-route
analogy*. Any courier that wants to sit at this desk — local llama, AWS Claude
Haiku, Azure GPT-4o-mini — must promise it can do all three jobs without breaking
the rule. The factory just decides which courier gets the seat today, based on
whether the depot is running on local fuel, AWS Bedrock fuel, or Azure OpenAI.

---

## Self-test questions

1. Which method is called by the chat engine on every user question, and which
   constant is its default `system_prompt` argument?
2. Why are the provider imports lazy (inside `if/elif/else` branches) in
   `factory.py` rather than at the top of the file?
3. What is the difference between `COURIER_SYSTEM_PROMPT` and
   `FALLBACK_SYSTEM_PROMPT`, and which one does the chat engine pick when the
   gap detector returns `GAP`?
4. Why does `extract_topics_and_relations()` swallow JSON parse failures and
   return empty lists instead of raising?
5. If you wanted to add a fourth provider (say `GeminiLLM`), what is the
   minimum set of files you would touch?

---

## What to read next

- [LLM Providers Deep Dive](llm-providers-deep-dive.md) — the three concrete classes that satisfy this contract.
- [Chat Engine Deep Dive](chat-engine-deep-dive.md) — where `complete()` is actually called, and how the system prompt is chosen per request.
- [Graph Extractor Deep Dive](graph-extractor-deep-dive.md) — where `extract_topics_and_relations()` is called, with prompt and parsing examples.
- [Wiki Generator Deep Dive](wiki-generator-deep-dive.md) — where `generate_wiki_page()` is called and how its output gets re-ingested.
