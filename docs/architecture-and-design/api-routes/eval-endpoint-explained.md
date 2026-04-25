# Endpoint Deep Dive: `POST /eval/run` — the inspector's bell

> **Study order:** #22 · **Source:** [`src/routes/eval.py`](../../../src/routes/eval.py)
> · **Component:** [Evaluation Framework](../../ai-engineering/evaluation-framework-deep-dive.md)
> · **Dataset:** `scripts/golden-questions.yaml` (grown by [👎 feedback](../../ai-engineering/feedback-loop-deep-dive.md)).

---

## Table of Contents

- [Endpoint summary](#endpoint-summary)
- [Request schema](#request-schema)
- [Response schema](#response-schema)
- [Internal flow](#internal-flow)
- [`curl` example](#curl-example)
- [Error cases](#error-cases)
- [🫏 Donkey explainer — the inspector's bell](#-donkey-explainer--the-inspectors-bell)

---

## Endpoint summary

| Method | Path | Auth | Purpose | 🫏 Donkey |
|--------|------|------|---------|-----------|
| POST | `/eval/run` | none | Run every question in the golden dataset through the live chat engine and grade the answers across the nine documented metrics; return the summary inline AND save a JSON file under `scripts/eval-results/` | Pull the inspector's bell — the road inspector drives every standard test delivery and fills in the nine clipboards, then files the report card in the cabinet |

Mounted at `/eval` with tag `evaluation` in `src/main.py`.

---

## Request schema

| Param | Where | Type | Required | Default | Effect |
|-------|-------|------|----------|---------|--------|
| `n_questions` | query string | int | no | `null` (means "all") | Caps how many golden questions are run; useful for fast smoke runs |

No request body. Runtime knobs come from `src/config.py`:

| Setting | Default | Effect on the eval |
|---------|---------|--------------------|
| `EVAL_MODE` | `rule_based` | `rule_based` = free keyword judge, `llm_judge` = LLM-as-Judge for faithfulness |
| `EVAL_FAITHFULNESS_THRESHOLD` | 0.5 | Threshold used by the rule-based path |
| `EVAL_KEYWORD_OVERLAP_PCT` | 0.5 | Threshold for "sentence is in context" in the keyword judge |
| `EVAL_GOLDEN_QUESTIONS_PATH` | `./scripts/golden-questions.yaml` | Where the question set is loaded from |
| `CLOUD_PROVIDER` | `local` | Reported in the response and used as the cost-table key |

---

## Response schema

```json
{
  "pass_rate": 0.7,
  "passed":    7,
  "total":     10,
  "provider":  "local",
  "metrics": {
    "avg_retrieval":           0.812,
    "avg_context_precision":   0.74,
    "avg_faithfulness":        0.85,
    "avg_answer_relevance":    0.62,
    "avg_context_recall":      0.71,
    "avg_answer_correctness":  0.66,
    "avg_completeness":        0.78,
    "hallucination_rate_pct": 12.0,
    "avg_cost_per_query_usd":  0.0,
    "total_cost_usd":          0.0
  },
  "avg_latency_ms": 1843.2,
  "comparison_with_rag_chatbot": {
    "rag_chatbot_had": { ... },
    "NEW_in_knowledge_engine": { ... }
  },
  "results": [ /* one EvaluationResult.to_dict() per question */ ]
}
```

| Field | Source | 🫏 Donkey |
|-------|--------|-----------|
| `pass_rate` | `EvalSummary.pass_rate` — `passed / total` | Fraction of test deliveries that scored 0.65 or above on the inspector's overall grade |
| `passed` / `total` | counts from the run | Tally of green-stamp deliveries vs total deliveries driven |
| `provider` | `settings.cloud_provider.value` | Which stable's donkey took the test deliveries today — local barn, AWS depot, or Azure hub |
| `metrics.*` | Averages of the per-metric scores; full meanings in the [Evaluation Framework deep dive](../../ai-engineering/evaluation-framework-deep-dive.md#the-nine-metrics-in-detail) | Daily totals of each clipboard column the inspector keeps |
| `avg_latency_ms` | Average of per-question latency timed by `run_evaluation` | Average trip duration on the tachograph across all test deliveries |
| `comparison_with_rag_chatbot` | `EvalSummary.compare_with_rag_chatbot()` | Side-by-side card showing which clipboard columns existed in the previous stable and which are new this stable |
| `results[]` | `EvaluationResult.to_dict()` per question | One graded receipt per test delivery, including answer preview, every score, and any flagged claims |

The same payload is also persisted as
`scripts/eval-results/eval-{provider}-{YYYYMMDD-HHMMSS}.json` via
`_save_results` — read that file from CI, not the HTTP response, to avoid
parsing very long inline arrays.

---

## Internal flow

```text
client
  │  POST /eval/run?n_questions=5
  ▼
FastAPI middleware (CORS)
  │
  ▼
src/routes/eval.py:run_eval(request, n_questions)
  │   - chat_engine = request.app.state.chat_engine
  │   - llm        = request.app.state.llm
  │   - evaluator  = KnowledgeEngineEvaluator(llm=llm)
  │
  ▼
src/evaluation/evaluator.py:run_evaluation(chat_engine, evaluator, n_questions)
  │
  ├── load_golden_questions()  ← reads scripts/golden-questions.yaml
  │
  └── for each question:
        ├── chat_engine.answer(ChatRequest(question=q["question"]))
        │     ↳ vector + graph + gap + LLM (full GraphRAG round trip)
        │
        ├── evaluator.evaluate(question, answer, retrieved_chunks=[],
        │                       expected_topics, graph_topics,
        │                       expected_answer, latency_ms, provider)
        │     ↳ nine _score_* methods → EvaluationResult
        │
        └── append to results

  build EvalSummary (averages, hallucination_rate, cost)
  _save_results(summary)  ← writes scripts/eval-results/eval-*.json

  return JSON to client
```

> **Heads up — `retrieved_chunks=[]`.** The driver currently passes an empty
> list because the chat engine's response does not yet expose its raw chunks.
> The retrieval / context-precision / context-recall scores therefore use the
> safe fallbacks documented in the
> [Evaluation Framework deep dive](../../ai-engineering/evaluation-framework-deep-dive.md#running-an-evaluation-end-to-end).
> Wiring chunks through `ChatResponse` is the documented next improvement.

---

## `curl` example

```bash
# Smoke run — first three golden questions, free
EVAL_MODE=rule_based curl -X POST 'http://localhost:8200/eval/run?n_questions=3' | jq '.metrics'

# Full run with LLM-as-Judge (costs a few cents on cloud providers)
EVAL_MODE=llm_judge  curl -X POST 'http://localhost:8200/eval/run' | jq '.pass_rate, .metrics'
```

---

## Error cases

| Trigger | Response | 🫏 Donkey |
|---------|----------|-----------|
| `golden-questions.yaml` is missing or empty | `200` with all zero counters (`EvalSummary()` default) | Inspector showed up but the test-delivery binder was empty; report card is blank |
| Chat engine throws on a single question | The exception bubbles up — the route does not catch per-question failures today | One bad test delivery halts the whole inspection; fix is to wrap the per-question loop in `try/except` and append a failure result |
| `EVAL_MODE=llm_judge` but the LLM is unreachable | `_score_faithfulness_llm` catches and falls back to `_score_faithfulness_keyword` (logs `llm_judge_failed_fallback_to_keyword`) | The inspector's preferred judge is out; falls back to the cheaper rule-based judge so the inspection still completes |
| `n_questions=0` | `total=0`, `pass_rate=0.0` (division-by-zero guarded by `if self.total > 0` in the property) | Inspector was told to grade zero deliveries; reports a perfect-zero day |
| Disk full when writing `scripts/eval-results/eval-*.json` | `_save_results` raises after the response is built — surfaces as a `500` from the route's perspective | Inspector finished grading but couldn't file the report card in the cabinet |

---

## 🫏 Donkey explainer — the inspector's bell

The eval bell is the only door in the stable that triggers a full exam. When
you ring it, the road inspector pulls the standard test-deliveries binder off
the shelf, then for each entry asks the live donkey to actually drive that
delivery — same dispatcher, same warehouse, same paper map as a normal
customer trip. The inspector grades each delivery across nine clipboards
(retrieval clarity, backpack relevance, missed towns, honesty about the
backpack, on-topic answer, match against the known-good reference, all
sub-questions covered, neighbour-town usefulness, and cargo-units burned)
and rolls them into one overall grade per delivery. At the end of the round
the inspector files a dated report card in the cabinet under
`scripts/eval-results/` and shouts the totals back through the door so the
caller can decide whether to ship the new donkey or send it back for retraining.
