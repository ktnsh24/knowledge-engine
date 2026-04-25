# Testing the Knowledge Engine

> **Study order:** #34 · **Difficulty:** ★★☆☆☆ — once you understand the
> three layers of the pyramid, the only judgement call is "which layer does my
> change need?"
>
> **Test root:** [`tests/`](../../tests/) · **Eval driver:**
> [`src/evaluation/evaluator.py`](../../src/evaluation/evaluator.py) · **Eval
> dataset:** `scripts/golden-questions.yaml` (grown by [👎 feedback](feedback-loop-deep-dive.md)).

---

## Table of Contents

- [Why this doc exists](#why-this-doc-exists)
- [The three-layer test pyramid](#the-three-layer-test-pyramid)
- [Layer 1 — unit tests (pytest)](#layer-1--unit-tests-pytest)
- [Layer 2 — integration tests (pytest + live stores)](#layer-2--integration-tests-pytest--live-stores)
- [Layer 3 — eval tests (the report card)](#layer-3--eval-tests-the-report-card)
- [How to run each layer](#how-to-run-each-layer)
- [Coverage targets](#coverage-targets)
- [What CI gates look like](#what-ci-gates-look-like)
- [🫏 Donkey explainer — the quality gates before every shipment](#-donkey-explainer--the-quality-gates-before-every-shipment)
- [Self-test questions](#self-test-questions)
- [What to read next](#what-to-read-next)

---

## Why this doc exists

A RAG/GraphRAG project has *two* kinds of correctness — code correctness
(does the function return what it claims?) and answer correctness (does the
donkey answer the user's question well?). One pyramid alone covers neither —
unit tests will not catch hallucination, and an eval suite will not catch a
chunker off-by-one. This doc maps every kind of test in the project to the
layer that catches it.

---

## The three-layer test pyramid

```text
        ┌─────────────────────────────────────────┐
        │   Layer 3 — Eval (report card)          │  slow, expensive, semantic
        │   golden questions × 9 metrics          │  ←─ POST /eval/run
        ├─────────────────────────────────────────┤
        │   Layer 2 — Integration                 │  medium, needs Neo4j +
        │   chat → vector → graph → llm round-trip│  Chroma + Ollama running
        ├─────────────────────────────────────────┤
        │   Layer 1 — Unit                        │  fast, pure-python,
        │   one function or one class at a time   │  no network, runs in CI
        └─────────────────────────────────────────┘
```

The wider the band, the more tests at that layer. The narrower the band, the
slower and more semantic the assertion.

| Layer | What it catches | What it MISSES |
|-------|----------------|----------------|
| Unit | Off-by-one in chunker, wrong threshold in gap detector, broken JSON parsing in faithfulness judge fallback | "The donkey hallucinated about caching" — the answer-grade question |
| Integration | A vector store + graph store mismatch, a missing `app.state.*` wiring, a 500 from `POST /chat` because Ollama is down | "The retrieval is technically working but the score dropped from 0.75 to 0.55 since the last embedding-model swap" |
| Eval | Quality regressions across the 9 metrics, per-question pass/fail, hallucination-rate trend | "Why did this *specific* question's faithfulness drop?" — that needs a debug run, not the eval suite |

---

## Layer 1 — unit tests (pytest)

Targets: one class or one function at a time, no network, no docker, no
Ollama. Fastest tier — should run on every save in your editor.

| Module under test | What to assert | Example case |
|-------------------|----------------|--------------|
| [`src/chat/gap_detector.py`](../../src/chat/gap_detector.py) | Threshold logic returns the right `ConfidenceLevel`; `gap_summary()` aggregates correctly | `top_score=0.71, chunk_count=2` → `HIGH`; `top_score=0.71, chunk_count=1` → `PARTIAL` |
| [`src/chat/candidate_store.py`](../../src/chat/candidate_store.py) | `save_candidate` writes both files; `_update_status` flips status correctly; `summary()` counts pending/promoted/discarded | Promoting a non-existent id returns `None`; discarding a promoted candidate is a no-op |
| [`src/chat/feedback.py`](../../src/chat/feedback.py) | 👍 writes to `verified-answers.md`; 👎 writes to `golden-questions.yaml`; both write raw JSONL | Each branch produces the documented `result["action"]` value |
| [`src/evaluation/evaluator.py`](../../src/evaluation/evaluator.py) helpers | `_keywords` strips stopwords, `_cosine` returns 1.0 for identical vectors, `_score_retrieval` handles empty chunk list | Fixture chunks with `score=0.9` produce `quality="excellent"` |
| [`src/wiki/generator.py`](../../src/wiki/generator.py) | Per-page filename matches `{topic_id}.md`; index lists pages alphabetically by title; failure in one topic does not abort the run | Mock LLM returns content; verify file appears at the expected path |
| `src/models.py` | Pydantic validation rejects bad inputs (e.g. `ConfidenceLevel` from a typo string) | `ChatRequest(question="")` should still validate (no min length set today) — assert current behaviour |

**Rule of thumb:** every public method on the modules above gets at least one
unit test for the happy path and one for the obvious failure path.

---

## Layer 2 — integration tests (pytest + live stores)

Targets: full request → response with real services running locally.
Prerequisites: `docker compose up -d neo4j chromadb` and a running
`ollama serve` with `llama3.2` pulled.

| Scenario | What it proves |
|----------|----------------|
| `POST /ingest/run` against a tiny fixture corpus, then `GET /ingest/status` returns non-zero `chunks` and `topics` | Scanner + chunker + embedder + graph extractor + both stores wire together end to end |
| `POST /chat` with a question covered by the fixture corpus → `confidence=HIGH`, `sources` non-empty | Vector + graph + LLM compose correctly; gap detector does not over-flag |
| `POST /chat` with a question NOT covered by the fixture corpus → `confidence=GAP`, `candidate_id` returned, candidate file appears | Fallback path and candidate creation work end to end |
| `POST /wiki/candidates/{id}/promote` followed by `POST /ingest/run` followed by the same `POST /chat` → now `confidence=HIGH` | The self-improving loop closes |
| `POST /feedback/` with `thumbs_up=true`, then check `verified-answers.md` grew | Feedback writeback works |
| `GET /health/` returns `status=healthy` and matching counts | Lifespan wiring + the two `*.count()` calls work |

These tests are slow (LLM calls, embedding) and flaky against rate-limited
clouds, so run them locally against Ollama/Chroma/Neo4j only. The `app_env`
setting helps gate them so they only run when the right env is up.

---

## Layer 3 — eval tests (the report card)

Triggered with `POST /eval/run` (see the
[Eval Endpoint](../architecture-and-design/api-routes/eval-endpoint-explained.md)).

| Property | Value |
|----------|-------|
| Input | `scripts/golden-questions.yaml` (seeded by hand, grown by 👎 feedback) |
| Per-question metrics | The nine documented in the [Evaluation Framework deep dive](evaluation-framework-deep-dive.md) |
| Pass criterion per question | `overall_score >= 0.65` |
| Suite pass criterion | `pass_rate >= 0.7` (suggested CI gate; tune as the corpus matures) |
| Output | JSON file in `scripts/eval-results/eval-{provider}-{timestamp}.json` |
| Cost | Free with `EVAL_MODE=rule_based`; ≈$0.0005/question with `EVAL_MODE=llm_judge` |

**When to run which:**

| Trigger | Mode | Why |
|---------|------|-----|
| Pre-commit / CI on every push | `rule_based` + `n_questions=3` | Smoke — fast and free, catches obvious breakage |
| Nightly scheduled job | `rule_based` on the full set | Trend tracking on free signals |
| Pre-release / before merging a prompt change | `llm_judge` on the full set | Catches semantic hallucinations the rule-based judge misses |
| Lab 19 (judge vs rule divergence) | Both, side by side | Quantify the divergence so you trust the rule-based mode in CI |

---

## How to run each layer

| Layer | Command | Prereqs |
|-------|---------|---------|
| Unit | `poetry run pytest tests/unit/ -q` | Just `poetry install` |
| Integration | `poetry run pytest tests/integration/ -q` | `docker compose up -d neo4j chromadb` + `ollama pull llama3.2` + `ollama serve` |
| Eval (CLI) | `poetry run python -c "import asyncio; from src.evaluation.evaluator import run_evaluation, KnowledgeEngineEvaluator; asyncio.run(run_evaluation(chat_engine, KnowledgeEngineEvaluator()))"` | Whole stack running; chat engine wired via lifespan |
| Eval (HTTP) | `curl -X POST http://localhost:8200/eval/run?n_questions=5` | Server running (`poetry run uvicorn src.main:app --port 8200`) |

The exact `tests/` subfolder layout above is the recommended convention; the
test directory in this repo is currently a placeholder being filled out.

---

## Coverage targets

These are guidance numbers, not yet enforced thresholds in CI:

| Layer | Coverage target | What "covered" means |
|-------|-----------------|----------------------|
| Unit | ≥80% line coverage of `src/chat/`, `src/evaluation/`, `src/wiki/`, `src/ingestion/`, `src/models.py` | Every branch of the gap thresholds, every status flip in the candidate store, every metric scoring method |
| Integration | At least one test per route in `src/routes/` | Wiring sanity — guarantees the lifespan-injected `app.state.*` exists for every endpoint |
| Eval | Pass rate ≥0.7 on a corpus of ≥10 golden questions per provider | A real, comparable score across local/AWS/Azure runs |

`pytest --cov=src --cov-report=term-missing` is the recommended invocation
once the test directory is fleshed out.

---

## What CI gates look like

A working CI for this project enforces:

| Gate | Layer | Command |
|------|-------|---------|
| Lint | n/a | `poetry run ruff check src tests` (and `poetry run black --check src tests`) |
| Unit | 1 | `poetry run pytest tests/unit/ -q` |
| Smoke eval | 3 | `EVAL_MODE=rule_based poetry run pytest tests/eval/test_smoke_eval.py -q` (calls `POST /eval/run?n_questions=3` against an in-process `TestClient`) |
| Pre-release eval | 3 | `EVAL_MODE=llm_judge` on the full golden file; gated on `pass_rate >= 0.7` and `hallucination_rate <= 0.15` |
| Integration | 2 | Optional — local-only because it needs Docker + Ollama |

The pre-release gate is the most valuable one — it is what stops a "the
prompts feel better" change from silently regressing the report card.

---

## 🫏 Donkey explainer — the quality gates before every shipment

Testing is the three quality gates the donkey passes before any new behaviour
goes out the stable door. The first gate is the parts inspector: every screw,
threshold, and JSON parser is checked individually so nothing obviously broken
leaves the workshop. The second gate is the dry-run loading dock: the donkey
actually loads a small backpack from a real warehouse, walks through the gate,
and proves the whole route works end-to-end on the practice course. The third
gate is the road inspector with the nine clipboards: standard test deliveries
are driven for real and graded across nine columns, and any donkey whose
average grade dips below the line is sent back to the workshop. The first gate
runs in seconds on every save; the second gate runs locally when you change
the wiring; the third gate runs before any new donkey is allowed to start a
shift.

---

## Self-test questions

1. Which layer would catch a bug where `gap_detector.py` accidentally returned
   `HIGH` for `top_score = 0.69`? Why?
2. Which layer would catch a quality regression where the average faithfulness
   dropped from 0.85 to 0.62 after changing the system prompt? Why?
3. Why is `EVAL_MODE=rule_based` the right default for CI gates on every push,
   even though `llm_judge` is more accurate?
4. The integration tests need Neo4j, ChromaDB, and Ollama running. What does
   that imply about whether they should run in GitHub Actions, in a pre-merge
   gate, or only locally?
5. If the `pass_rate` gate is set to 0.7, what is the maximum number of failing
   questions allowed in a 10-question golden file? In a 25-question one?

---

## What to read next

- [Evaluation Framework Deep Dive](evaluation-framework-deep-dive.md) — what
  the nine clipboards measure and how `overall_score` is composed.
- [Chat Engine Deep Dive](chat-engine-deep-dive.md) — the request path that
  every layer eventually exercises.
- [Feedback Loop Deep Dive](feedback-loop-deep-dive.md) — how the 👎 path
  grows the golden dataset the eval layer reads.
- [Eval Endpoint](../architecture-and-design/api-routes/eval-endpoint-explained.md) —
  the HTTP entry point used by the smoke gate.
