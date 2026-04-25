# Deep Dive: LLM Providers — Ollama / Bedrock / Azure OpenAI

> **Study order:** #14 · **Difficulty:** ★★★☆☆ — three short files but each
> calls a different SDK with different auth, cost, and quirks.
>
> **Files:**
> [`src/llm/ollama.py`](../../src/llm/ollama.py) ·
> [`src/llm/bedrock.py`](../../src/llm/bedrock.py) ·
> [`src/llm/azure_openai.py`](../../src/llm/azure_openai.py) ·
> [`src/llm/factory.py`](../../src/llm/factory.py)
>
> **Implements:** [LLM Interface](llm-interface-deep-dive.md).

---

## Table of Contents

- [Why three providers](#why-three-providers)
- [Provider comparison at a glance](#provider-comparison-at-a-glance)
- [1. Ollama (local)](#1-ollama-local)
- [2. AWS Bedrock](#2-aws-bedrock)
- [3. Azure OpenAI](#3-azure-openai)
- [Auth & secrets — what each provider needs](#auth--secrets--what-each-provider-needs)
- [Cost — same questions, three very different bills](#cost--same-questions-three-very-different-bills)
- [When to use which](#when-to-use-which)
- [Common gotchas](#common-gotchas)
- [🫏 Donkey explainer — three writers at the same desk](#-donkey-explainer--three-writers-at-the-same-desk)
- [Self-test questions](#self-test-questions)
- [What to read next](#what-to-read-next)

---

## Why three providers

The knowledge engine is the same project across **local development, AWS, and
Azure** — only the provider implementations change. That means we keep three
concrete subclasses of `BaseLLM`, picked at startup by `create_llm()` based on
the `CLOUD_PROVIDER` env var. The interface guarantees the chat engine, wiki
generator, and graph extractor never know which one they are talking to.

| Provider | Class | When it runs | Default model | Cost shape | 🫏 Donkey |
|----------|-------|--------------|---------------|------------|-----------|
| Local | `OllamaLLM` | `CLOUD_PROVIDER=local` (default for dev/labs) | `llama3.2` over `http://localhost:11434/api/generate` | Free — your CPU/GPU | The home-stable donkey — slow but eats free hay; fine for practice runs |
| AWS | `BedrockLLM` | `CLOUD_PROVIDER=aws` | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` via Bedrock Converse API | $0.00025 / 1K input · $0.00125 / 1K output (per `TOKEN_COSTS["aws"]` in evaluator) | The AWS courier-donkey — paid per parcel, fast, knows the EU corridors |
| Azure | `AzureOpenAILLM` | `CLOUD_PROVIDER=azure` | `gpt-4o-mini` via Azure OpenAI deployment | $0.00015 / 1K input · $0.00060 / 1K output (per `TOKEN_COSTS["azure"]`) | The Azure courier-donkey — also paid per parcel, slightly cheaper, different paperwork at the gate |

---

## Provider comparison at a glance

| Aspect | Ollama (local) | AWS Bedrock | Azure OpenAI | 🫏 Donkey |
|--------|----------------|-------------|--------------|-----------|
| Transport | Raw HTTP via `httpx` to `localhost:11434` | `boto3` `bedrock-runtime` SDK, sync, wrapped in `run_in_executor` | `openai.AsyncAzureOpenAI` async client | Three different ways to hand a job to the writing donkey — slip it under the door, hand it to an AWS courier, post it via the Azure mail-room |
| API style | Single `POST /api/generate` with `{model, prompt, stream:false, options:{temperature}}` | `client.converse(modelId, system=[…], messages=[…], inferenceConfig={…})` | `chat.completions.create(model=deployment, messages=[…])` | The donkey can be briefed by hand-written note (Ollama), formal courier docket (Bedrock), or a structured email thread (Azure) |
| Async story | Truly async via `httpx.AsyncClient` | Sync SDK ⇒ wrapped with `asyncio.get_event_loop().run_in_executor` to avoid blocking | Native async SDK | Local donkey responds at the door; AWS donkey gets a courier; Azure donkey replies on the same async wire |
| Auth | None — assumes Ollama is running locally | `boto3` default credential chain (env vars, profile, IRSA) | `azure_openai_api_key` from settings | Local donkey trusts whoever knocks; AWS donkey checks an IAM badge; Azure donkey checks an API key card |
| Cost per query | $0 — you pay in laptop heat | Cheapest on-cloud Claude tier (Haiku 4.5) | Cheapest on-cloud GPT tier (4o-mini) | Free hay for the home donkey, AWS hay-bill, Azure hay-bill — the cheapest each cloud sells |
| Ideal use | Lab runs, CI tests, offline demos | Production EU traffic; pairs with DynamoDB stores | Production Azure-anchored stacks; pairs with Cosmos + AI Search | Practice trips at home, paid trips out of the AWS depot, paid trips out of the Azure hub |

---

## 1. Ollama (local)

```python
class OllamaLLM(BaseLLM):
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.ollama_base_url           # http://localhost:11434
        self.model    = settings.ollama_llm_model          # llama3.2

    async def complete(self, question, context,
                       system_prompt=DONKEY_SYSTEM_PROMPT, temperature=0.1):
        prompt = f"{system_prompt}\n\n---CONTEXT---\n{context}\n\n---QUESTION---\n{question}"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt,
                      "stream": False, "options": {"temperature": temperature}},
            )
            resp.raise_for_status()
            return resp.json()["response"]
```

**Notes that matter:**

- **Single concatenated prompt.** Ollama's `/api/generate` does not have a separate `system` field, so the system prompt is just prepended to the user content with `---CONTEXT---` / `---QUESTION---` markers.
- **120-second timeout.** Local llama3.2 on CPU can take 30–90 s for a long answer; the chat engine and ingest pipeline are happy to wait.
- **`stream=False`.** Knowledge engine does not stream tokens to clients — every endpoint returns the full string.
- **`extract_topics_and_relations()`** truncates input to `text[:3000]` chars before prompting and uses a JSON-only system prompt; it slices the result between the first `{` and last `}` and falls back to `{"topics":[], "relationships":[]}` on parse failure.
- **`generate_wiki_page()`** truncates context to 4000 chars and asks for the strict five-section structure (analogy / definition / how / why / connections); the donkey analogy is post-extracted by scanning for `🫏`.

---

## 2. AWS Bedrock

```python
class BedrockLLM(BaseLLM):
    def __init__(self):
        settings = get_settings()
        self.model_id = settings.aws_bedrock_llm_model       # claude-haiku-4-5 (EU)
        self.client   = boto3.client("bedrock-runtime",
                                     region_name=settings.aws_region)

    async def complete(self, question, context,
                       system_prompt=DONKEY_SYSTEM_PROMPT, temperature=0.1):
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_complete, question, context, system_prompt, temperature
        )

    def _sync_complete(self, question, context, system_prompt, temperature):
        user_content = f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"
        response = self.client.converse(
            modelId=self.model_id,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_content}]}],
            inferenceConfig={"temperature": temperature, "maxTokens": 2048},
        )
        return response["output"]["message"]["content"][0]["text"]
```

**Notes that matter:**

- **Bedrock Converse API** keeps the system prompt in its proper `system=[…]` slot, so the strict "ground in context only" instruction is honoured by Claude as a true system message.
- **`maxTokens: 2048`** is hard-coded here. Tier-2 Lab 9 (LLM_MAX_TOKENS sweep) reads `settings.llm_max_tokens` for other surfaces; this provider does not yet wire it through.
- **Sync SDK wrapped in executor.** `boto3` is synchronous; the wrapper keeps the FastAPI event loop free.
- **EU model id.** `eu.anthropic.claude-haiku-4-5-20251001-v1:0` is the EU cross-region inference profile — required because the project's AWS region is `eu-central-1`.
- **Same JSON-only patterns** for `extract_topics_and_relations()` and `generate_wiki_page()` as Ollama, with shorter prompts.

---

## 3. Azure OpenAI

```python
class AzureOpenAILLM(BaseLLM):
    def __init__(self):
        settings = get_settings()
        self.client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,   # 2024-02-01
        )
        self.deployment = settings.azure_openai_llm_deployment   # gpt-4o (default in code)

    async def complete(self, question, context,
                       system_prompt=DONKEY_SYSTEM_PROMPT, temperature=0.1):
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"},
            ],
            temperature=temperature,
            max_tokens=2048,
        )
        return response.choices[0].message.content
```

**Notes that matter:**

- **Native async client.** No executor needed — `await` directly on `chat.completions.create`.
- **`model=` is the deployment name**, not the OpenAI model id. Azure routes by deployment.
- **Default deployment is `gpt-4o`** in `config.py`, but the documented production cost line uses `gpt-4o-mini` (per the cost table in evaluator). Override with `AZURE_OPENAI_LLM_DEPLOYMENT=gpt-4o-mini` for the cheapest tier.
- **System prompt sits in its own message** — the strict "ground in context only" rule applies cleanly.

---

## Auth & secrets — what each provider needs

| Provider | Required env vars | Where they live | What breaks if missing | 🫏 Donkey |
|----------|-------------------|-----------------|------------------------|-----------|
| Ollama | `OLLAMA_BASE_URL`, `OLLAMA_LLM_MODEL` (defaults work locally) | `.env` / `Settings` | `httpx.ConnectError` on first `complete()` if the Ollama daemon isn't running | The home donkey only works if the stable door is open and the lamp is on |
| AWS Bedrock | Standard AWS creds (env / profile / role) plus `AWS_REGION`, `AWS_BEDROCK_LLM_MODEL` | `.env` + AWS credential chain | `botocore.exceptions.NoCredentialsError` or `AccessDeniedException` from Bedrock | The AWS courier needs an IAM badge before it will pick up parcels at the depot |
| Azure OpenAI | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_LLM_DEPLOYMENT` | `.env` | `openai.AuthenticationError` or `openai.NotFoundError` (wrong deployment name) at construction time | The Azure courier needs a key card and the right room number or it cannot enter the building |

---

## Cost — same questions, three very different bills

The evaluator's `TOKEN_COSTS` table is the single source of truth for per-query
cost in this repo:

```python
TOKEN_COSTS = {
    "local":  {"input": 0.0,      "output": 0.0},
    "aws":    {"input": 0.00025,  "output": 0.00125},   # Bedrock Haiku 4.5
    "azure":  {"input": 0.00015,  "output": 0.00060},   # GPT-4o-mini
}
```

| Provider | Input $/1K tok | Output $/1K tok | Implied cost of a 600-in / 400-out chat | 🫏 Donkey |
|----------|----------------|-----------------|------------------------------------------|-----------|
| Local | 0 | 0 | $0.0000 — only laptop electricity | The home donkey runs on free hay — only the electric bill notices |
| AWS Bedrock Haiku 4.5 | 0.00025 | 0.00125 | ≈ $0.00065 per query | The AWS courier charges per backpack carried plus a heavier fee for what it writes back |
| Azure OpenAI GPT-4o-mini | 0.00015 | 0.00060 | ≈ $0.00033 per query | The Azure courier is a touch cheaper per parcel and a touch cheaper per reply |

These figures are what the evaluator's [`CostScore`](evaluation-framework-deep-dive.md#what-the-evaluator-actually-measures)
multiplies the per-query token count against, so every report card carries a real
hay-bill column.

---

## When to use which

| Scenario | Pick | Why | 🫏 Donkey |
|----------|------|-----|-----------|
| First-time setup, lab sweeps, CI | Ollama | Free, deterministic enough at temperature 0.1, no network egress | Practice runs use the home donkey — no bill, no AWS bill, no Azure bill |
| Production EU traffic with DynamoDB stores | Bedrock | Same provider boundary as DynamoDB vector + graph stores; one IAM surface | Same depot for letters and the donkey — fewer key-cards to manage |
| Existing Azure tenant / Cosmos DB shop | Azure OpenAI | Pairs naturally with Cosmos DB + Azure AI Search; cheapest tier (gpt-4o-mini) | The Azure hub already runs the warehouse and map-room — keep the writer there too |
| Eval lab #19 LLM-as-judge | Bedrock or Azure | Local llama3.2 is too unreliable as a judge of faithfulness; cloud models score more consistently | The judge in the report-card factory needs better handwriting than the home donkey can manage |

---

## Common gotchas

| Gotcha | Where it bites | Fix | 🫏 Donkey |
|--------|----------------|-----|-----------|
| Ollama model not pulled (`ollama pull llama3.2`) | First `/chat` call hangs then 404s | Run `ollama pull llama3.2` once after install | The home donkey can't write a note about a town it has never read about |
| `boto3` not installed in `local` runs | Import error if anything pulls `bedrock.py` eagerly | Imports are deferred inside the factory branches; do not move them to the top of `factory.py` | The AWS courier never wakes up if the AWS uniform isn't even unpacked |
| Bedrock 200 K context limit, but EU Haiku has stricter throughput quotas | Long ingest runs trigger `ThrottlingException` | Reduce `RAG_CHUNK_SIZE` or add jitter; ingest already serialises one file at a time | The AWS courier can only carry so many parcels per hour — overload it and it drops the load |
| Azure deployment name vs model name confusion | `openai.NotFoundError: deployment not found` | `AZURE_OPENAI_LLM_DEPLOYMENT` must match the **Azure deployment** name, not the OpenAI model | Calling for the wrong room number at the Azure hub means the donkey is sent to an empty desk |
| Default Azure deployment in `config.py` is `gpt-4o`, but cost table assumes `gpt-4o-mini` | Real Azure bills come back ~10× higher than the report card suggests | Set `AZURE_OPENAI_LLM_DEPLOYMENT=gpt-4o-mini` to match the documented cost line | The hay-bill on the report card is for the small donkey — if you sent the big one, expect a bigger invoice |

---

## 🫏 Donkey explainer — three writers at the same desk

🫏 The writing-desk in the stable has one set of rules — taped up by `BaseLLM` —
and three different donkeys take turns at it. The **home donkey** (Ollama
llama3.2) is slow and unpaid; it works overnight on lab runs and never sends a
bill. The **AWS courier-donkey** (Bedrock Claude Haiku 4.5) shows its IAM badge
at the depot, picks up the job, writes a tidier note, and charges per hay-bale
of input and per hay-bale of output — output costs five times more, same as the
DE world's WCU > RCU. The **Azure courier-donkey** (GPT-4o-mini) does the same
job through a different mail-room — checks an API key card, follows a deployment
name into the right room, charges fractionally less, and carries the same 🫏
analogy back stamped on the delivery note. Same desk. Same three jobs. Three
different donkeys. The factory just decides which one gets the seat today.

---

## Self-test questions

1. Which two providers send the system prompt as a separate field, and which one concatenates it into the user prompt?
2. Why does `BedrockLLM.complete()` use `run_in_executor`, and what would break if it called `self.client.converse(...)` directly inside an `async def`?
3. Where in the codebase are the per-token prices for each provider defined, and which component reads them?
4. If `AZURE_OPENAI_LLM_DEPLOYMENT` is left at the default `gpt-4o`, what surprise will the next eval run produce?
5. Why are provider imports placed inside the `if/elif/else` branches of `create_llm()`?

---

## What to read next

- [LLM Interface Deep Dive](llm-interface-deep-dive.md) — the contract every provider here implements.
- [Chat Engine Deep Dive](chat-engine-deep-dive.md) — the consumer that actually picks `system_prompt` and `temperature` per call.
- [Evaluation Framework Deep Dive](evaluation-framework-deep-dive.md) — where `TOKEN_COSTS` is read and `CostScore` is computed.
- [Vector Store Providers](vectorstore-providers-deep-dive.md) and [Graph Store Providers](graphstore-providers-deep-dive.md) — the matching cloud-side stores you usually pair with each LLM provider.
