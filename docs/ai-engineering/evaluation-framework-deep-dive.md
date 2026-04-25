# Deep Dive: The Evaluation Framework — `src/evaluation/evaluator.py`

> **Study order:** #32 · **Difficulty:** ★★★★☆ — large file (≈800 lines) but
> the structure is regular: nine score dataclasses, one orchestrator, one
> golden-question loader. Once you see the pattern, the rest is bookkeeping.
>
> **File:** [`src/evaluation/evaluator.py`](../../src/evaluation/evaluator.py) ·
> **Triggered by:** [`POST /eval/run`](../architecture-and-design/api-routes/eval-endpoint-explained.md)
> · **Cross-repo reference:**
> [`ai-portfolio/personal/evaluation-metrics-cheatsheet.md`](../../../../personal/evaluation-metrics-cheatsheet.md).

---

## Table of Contents

- [Why this file matters](#why-this-file-matters)
- [What rag-chatbot had vs what knowledge-engine adds](#what-rag-chatbot-had-vs-what-knowledge-engine-adds)
- [The nine metrics in detail](#the-nine-metrics-in-detail)
- [The overall score and pass threshold](#the-overall-score-and-pass-threshold)
- [LLM-as-Judge vs rule-based — `EVAL_MODE`](#llm-as-judge-vs-rule-based--eval_mode)
- [Cost model — `TOKEN_COSTS`](#cost-model--token_costs)
- [Running an evaluation end-to-end](#running-an-evaluation-end-to-end)
- [Where results are saved](#where-results-are-saved)
- [Integration with `routes/eval.py`](#integration-with-routesevalpy)
- [🫏 Donkey explainer — the road inspector with nine clipboards](#-donkey-explainer--the-road-inspector-with-nine-clipboards)
- [Self-test questions](#self-test-questions)
- [What to read next](#what-to-read-next)

---

## Why this file matters

Without a single repeatable scoring mechanism you cannot tell whether the last
prompt edit, chunk-size sweep, or provider swap improved or regressed
behaviour — you can only feel that it did. `KnowledgeEngineEvaluator` is the
project's report-card factory: nine numeric scores per question, one
`overall_score`, one `passed` flag, one summary across all questions, and a
JSON file on disk with a timestamp so two runs can be diffed.

It also fills every documented gap from the rag-chatbot evaluator (the
docstring of the file lists them one by one). Read this doc once and you can
answer "how is this measured?" for any number you see in
`scripts/eval-results/*.json`.

> **Cross-repo cheatsheet:** for the metric *theory* — why faithfulness ≠
> answer correctness, why precision and recall are both needed — see
> [`ai-portfolio/personal/evaluation-metrics-cheatsheet.md`](../../../../personal/evaluation-metrics-cheatsheet.md).
> This doc is the *implementation* reference for those metrics inside this
> repo.

---

## What rag-chatbot had vs what knowledge-engine adds

The file's own docstring is explicit:

| # | Metric | rag-chatbot? | knowledge-engine? |
|---|--------|--------------|-------------------|
| 1 | Retrieval (`avg_score`, `top_score`, `quality`) | ✅ | ✅ same shape |
| 2 | Context Precision | ✅ basic | ✅ same |
| 3 | Context Recall | ❌ | ✅ NEW — compares `expected_topics` to retrieved + graph topics |
| 4 | Faithfulness | ✅ keyword heuristic only | ✅ UPGRADED — `EVAL_MODE` toggle: `rule_based` (keyword) or `llm_judge` (LLM-as-Judge) |
| 5 | Answer Relevance | ✅ keyword overlap | ✅ kept for backward comparison |
| 6 | Answer Correctness | ❌ | ✅ NEW — embedding cosine vs `expected_answer` (or keyword fallback) |
| 7 | Completeness | ❌ (was an exercise question) | ✅ NEW — LLM-as-Judge or keyword aspect count |
| 8 | Graph Traversal Quality | n/a — RAG only | ✅ NEW — did graph topics actually appear in the answer? |
| 9 | Cost per query | ❌ | ✅ NEW — token counts × `TOKEN_COSTS[provider]` |
| Bonus | Hallucination *rate* (across all runs) | ❌ (boolean per query only) | ✅ NEW — `EvalSummary.hallucination_rate` |

`EvalSummary.compare_with_rag_chatbot()` returns this exact split as JSON, so
the API response can show it side by side.

---

## The nine metrics in detail

Each metric has a dataclass score type and a `_score_*` method on the
evaluator. They follow the same shape: take the inputs the chat engine
produced, return a small dataclass with a normalised score in `[0.0, 1.0]`.

| Metric | Score class | Key fields | Method | Inputs needed |
|--------|-------------|------------|--------|---------------|
| Retrieval | `RetrievalScore` | `avg_score`, `top_score`, `chunks_retrieved`, `chunks_above_threshold`, derived `quality` (`excellent`/`good`/`fair`/`poor`) | `_score_retrieval(chunks)` | The list of `DocumentChunk` returned by the vector store; uses `getattr(c, "score", 0.5)` so it tolerates chunks without a score field |
| Context Precision | `ContextPrecisionScore` | `score`, `relevant_chunks`, `total_chunks` | `_score_context_precision(question, chunks)` | Question + chunks; counts chunks that share at least one keyword with the question |
| Context Recall | `ContextRecallScore` | `score`, `expected_topics`, `retrieved_topics`, `missed_topics`, derived `missed_count` | `_score_context_recall(expected_topics, chunks, graph_topics)` | `expected_topics` from the golden file; checks if topic words >3 chars appear in chunk text or graph topics |
| Faithfulness | `FaithfulnessScore` | `score`, `method` (`llm-as-judge` / `keyword-heuristic`), `flagged_claims`, derived `has_hallucination` (`< 0.8`) | `_score_faithfulness_llm(answer, chunks)` or `_score_faithfulness_keyword(answer, context)` | Answer + chunks; LLM judge prompts the model for a JSON verdict |
| Answer Relevance | `AnswerRelevanceScore` | `score`, `keyword_coverage` | `_score_answer_relevance(question, answer)` | Question + answer; keyword overlap, kept for parity with rag-chatbot |
| Answer Correctness | `AnswerCorrectnessScore` | `score`, `method` (`semantic-embedding` / `keyword-fallback` / `not-available` / `error`), `expected_answer_available` | `_score_answer_correctness(answer, expected_answer)` | Answer + expected answer; embeds both and computes cosine, falls back to keyword overlap if no embedder |
| Completeness | `CompletenessScore` | `score`, `aspects_in_question`, `aspects_answered`, `method` (`llm-as-judge` / `keyword-count` / `llm-fallback`) | `_score_completeness(question, answer)` | Question + answer; LLM-as-Judge counts aspects, keyword fallback estimates from word overlap |
| Graph Traversal | `GraphTraversalScore` | `topics_added_by_graph`, `graph_topics`, `graph_expansion_useful`, `topics_cited_in_answer` | `_score_graph_traversal(answer, graph_topics, chunks)` | Answer + the topic names the chat engine pulled from the graph; checks how many of them actually appear in the answer text |
| Cost | `CostScore` | `input_tokens`, `output_tokens`, `total_tokens`, `cost_usd`, `provider`, derived `cost_eur` (×0.92) | `_score_cost(input_tokens, output_tokens, provider)` | Token counts (caller-supplied) + provider name; multiplies by `TOKEN_COSTS[provider]` |

Two helpers underpin most of them:

- `_keywords(text)` — lowercased word list ≥3 chars, stripped of a small
  English stoplist; used by precision, recall, relevance, completeness
  fallbacks.
- `_cosine(a, b)` — pure-Python dot/norm; used by answer correctness when an
  embedder is provided.

---

## The overall score and pass threshold

`EvaluationResult.__post_init__` collapses seven of the nine metrics into a
single `overall_score`:

```python
self.overall_score = round(
    self.retrieval.avg_score       * 0.15 +
    self.context_precision.score   * 0.15 +
    self.context_recall.score      * 0.15 +
    self.faithfulness.score        * 0.20 +
    self.answer_relevance.score    * 0.10 +
    self.answer_correctness.score  * 0.15 +
    self.completeness.score        * 0.10,
    3,
)

@property
def passed(self) -> bool:
    return self.overall_score >= 0.65
```

Faithfulness carries the biggest weight (0.20) because hallucination is the
biggest failure mode; relevance and completeness carry the smallest (0.10
each). Graph traversal and cost are deliberately **not** in the formula — they
are diagnostic, not pass/fail signals.

`passed = overall_score >= 0.65` is intentionally lower than the rag-chatbot
threshold (0.7) because the knowledge-engine score is composed of seven
sub-scores instead of three, and partial coverage on a brand-new corpus is
expected.

---

## LLM-as-Judge vs rule-based — `EVAL_MODE`

The faithfulness metric is the one place where the evaluator itself spends
LLM tokens. It is gated by `EVAL_MODE` (see `src/config.py`):

| `EVAL_MODE` | What runs | Cost per question | When to use |
|-------------|-----------|-------------------|-------------|
| `rule_based` (default) | `_score_faithfulness_keyword` — sentences that share ≥40% of their keywords with the context are counted as "in context" | $0.00 | Local dev, fast iteration, smoke tests, anything in CI that runs on every push |
| `llm_judge` | `_score_faithfulness_llm` — sends a JSON-only judge prompt to the configured LLM, parses the response, falls back to keyword if parsing fails | A few hundred tokens per question (≈$0.0005 on Haiku, $0.0003 on GPT-4o-mini) | Pre-release runs, quality investigations, Lab 19 (judge vs rules divergence study) |

The judge prompt (kept in code so any provider can answer it) returns
`{"faithfulness_score": 0.0–1.0, "flagged_claims": [...], "reasoning": "..."}`.
Whichever method runs, `FaithfulnessScore.method` records the choice — so a
report-card row always shows whether the score came from rules or from a model.

The completeness metric also uses the LLM if one is wired (`self.llm`),
falling back to keyword aspect counting otherwise. Same pattern: the
`method` field on the score reveals which path ran.

---

## Cost model — `TOKEN_COSTS`

```python
TOKEN_COSTS = {
    "local":  {"input": 0.0,     "output": 0.0},
    "aws":    {"input": 0.00025, "output": 0.00125},  # Bedrock Haiku
    "azure":  {"input": 0.00015, "output": 0.00060},  # GPT-4o-mini
}
```

Per-1k-token rates, USD. The evaluator does NOT measure tokens itself — the
caller passes `input_tokens` and `output_tokens` to `evaluate()` (set to 0 in
the current `run_evaluation` driver, so cost is reported as $0 today). Plug a
real token counter in when you want this number to be live.

`CostScore.cost_eur` applies a flat 0.92 USD→EUR conversion. Good enough for
budget guardrails, not for finance.

---

## Running an evaluation end-to-end

```python
async def run_evaluation(chat_engine, evaluator, n_questions=None) -> EvalSummary:
    questions = load_golden_questions()                    # scripts/golden-questions.yaml
    if n_questions: questions = questions[:n_questions]

    for q in questions:
        request = ChatRequest(question=q["question"])
        response = await chat_engine.answer(request)        # ← real chat engine call
        result   = await evaluator.evaluate(
            question=q["question"], answer=response.answer,
            retrieved_chunks=[],                            # ← TODO: chat engine should expose
            expected_topics=q.get("expected_topics", []),
            graph_topics=response.topics or [],
            expected_answer=q.get("expected_answer"),
            latency_ms=latency, provider=settings.cloud_provider.value,
        )
        results.append(result)

    summary = EvalSummary(...)                              # averages + hallucination rate
    _save_results(summary)                                  # JSON to scripts/eval-results/
    return summary
```

| Step | Notes | 🫏 Donkey |
|------|-------|-----------|
| Load golden questions | Path: `scripts/golden-questions.yaml`; format documented in the [Feedback Loop deep dive](feedback-loop-deep-dive.md) — 👎 entries are appended here automatically | The auditor pulls today's standard test deliveries off the binder before opening the loading dock |
| Per-question chat call | Uses the live `ChatEngine.answer()` — same code path as production | The donkey actually drives each test delivery; the auditor times it and grades the receipt |
| Per-question evaluation | Currently `retrieved_chunks=[]` because the chat response does not yet expose its raw chunks; retrieval scores fall back to defaults | One clipboard column is blank today — TODO to wire chunks through the response so the auditor can score them |
| Build summary | Averages each metric across all questions; computes `pass_rate`, `hallucination_rate`, `total_cost_usd` | The auditor totals every clipboard at the end of the day for the daily summary |
| Save JSON | `scripts/eval-results/eval-{provider}-{timestamp}.json` | The signed report card filed in the cabinet, dated and stable so two runs can be compared |

---

## Where results are saved

`_save_results(summary)` writes a single JSON file per run:

```text
scripts/eval-results/eval-{provider}-{YYYYMMDD-HHMMSS}.json
```

The schema includes the headline numbers, the per-metric averages (split into
"rag-chatbot had" vs "NEW in knowledge-engine"), `avg_latency_ms`,
`comparison_with_rag_chatbot()` for the side-by-side table, and the full list
of per-question results from `EvaluationResult.to_dict()`.

That single file is what a CI eval-gate workflow reads to decide whether to
fail the build, and what a notebook reads to chart improvement over time.

---

## Integration with `routes/eval.py`

The route is a thin wrapper that hands the chat engine and the LLM to the
evaluator and returns the summary as JSON:

```python
@router.post("/run")
async def run_eval(request: Request, n_questions: int = None):
    chat_engine = request.app.state.chat_engine
    llm         = request.app.state.llm
    evaluator   = KnowledgeEngineEvaluator(llm=llm)
    summary     = await run_evaluation(chat_engine, evaluator, n_questions=n_questions)
    return {
        "pass_rate": ...,
        "metrics": { ... },
        "comparison_with_rag_chatbot": summary.compare_with_rag_chatbot(),
        "results": [r.to_dict() for r in summary.results],
    }
```

Notes:

- The route does **not** pass an `embedder` to `KnowledgeEngineEvaluator`,
  so answer-correctness today uses the keyword fallback. Wire in
  `vector_store.embedder` (or equivalent) when you want semantic correctness.
- `n_questions` is a useful smoke-test knob — `POST /eval/run?n_questions=3`
  keeps a CI run cheap and fast.

Full request/response shape lives in the
[Eval Endpoint](../architecture-and-design/api-routes/eval-endpoint-explained.md)
doc.

---

## 🫏 Donkey explainer — the road inspector with nine clipboards

The evaluator is the road inspector with nine clipboards. Every standard test
delivery from the auditor's binder gets driven by a real donkey, and each
clipboard records one thing: how relevant the GPS hits were, how much of the
backpack was actually useful, how many expected towns were missed, whether the
delivery note invented anything not in the backpack, whether the answer
addressed the customer's actual question, whether the answer matches the
known-good reference, whether every sub-question was covered, whether the
neighbour towns from the cartographer earned their place on the page, and how
many cargo-units the donkey burned through. Seven of the nine clipboards fold
into a single grade between zero and one; pass at 0.65 or above. The clipboards
themselves are kept on file with a timestamp so tomorrow's inspector can hold
yesterday's report up alongside today's and see whether the donkey is getting
faster or slower, more honest or less honest, cheaper or more expensive.

---

## Self-test questions

1. Which two of the nine metrics are NOT included in `overall_score`, and why
   would you choose to keep them diagnostic-only?
2. `EVAL_MODE=rule_based` and `EVAL_MODE=llm_judge` give different
   faithfulness numbers for the same answer. How would you design a Lab 19
   experiment to quantify the divergence?
3. The current `run_evaluation` driver passes `retrieved_chunks=[]` — what is
   the practical impact on the retrieval, context-precision, and
   context-recall scores in today's reports? What would you change to fix it?
4. Cost is computed from caller-supplied token counts that default to 0.
   Where would you add a token counter so `cost_usd` becomes accurate without
   changing the evaluator's interface?
5. Two runs of `POST /eval/run` against the same data produce slightly
   different `overall_score` values when `EVAL_MODE=llm_judge`. What is the
   structural reason, and which knob (in `src/config.py`) would you tighten
   to reduce the variance?

---

## What to read next

- [`evaluation-metrics-cheatsheet.md`](../../../../personal/evaluation-metrics-cheatsheet.md) —
  the cross-repo theory reference.
- [Eval Endpoint](../architecture-and-design/api-routes/eval-endpoint-explained.md) —
  the API surface in full.
- [Chat Engine Deep Dive](chat-engine-deep-dive.md) — the only thing being
  measured.
- [Testing](testing.md) — how the eval gate hooks into the wider pyramid.
- [Feedback Loop Deep Dive](feedback-loop-deep-dive.md) — how 👎 questions
  end up in the golden file the evaluator reads.
