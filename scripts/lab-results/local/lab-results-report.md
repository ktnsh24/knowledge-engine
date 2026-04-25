# 🧪 Knowledge Engine Lab Results — LOCAL Environment

> **Generated:** 2026-04-24 08:45 UTC
>
> **Provider:** LOCAL
>
> **API:** http://localhost:8200

---

## 📊 Evaluation Summary — All 9 Metrics

### Metrics present in rag-chatbot (for comparison)

| Metric | rag-chatbot score | knowledge-engine (LOCAL) |
|--------|------------------|------------------------------|
| `avg_retrieval` | *not recorded* | **0.71** |
| `avg_context_precision` | *not recorded* | **0.68** |
| `avg_faithfulness` | — (keyword) | **0.82** (LLM-as-Judge ✅) |
| `avg_answer_relevance` | *basic* | **0.74** |

### NEW metrics — missing from rag-chatbot

| Metric | Was in rag-chatbot? | LOCAL Score | Pass threshold |
|--------|--------------------|--------------------|----------------|
| `avg_context_recall` | ❌ Missing | **0.65** | > 0.60 |
| `avg_answer_correctness` | ❌ Missing | **0.6** | > 0.60 |
| `avg_completeness` | ❌ Missing (exercise only) | **0.7** | > 0.60 |
| `hallucination_rate_pct` | ❌ per-query boolean only | **9.1%** | < 10% |
| `avg_cost_per_query_usd` | ❌ documented, never tracked | **$0.000000** | < $0.002 |

### Overall

| Metric | Value |
|--------|-------|
| **Pass rate** | **0.72** (8/11) |
| **Avg latency** | 1240.0ms |
| **Provider** | local |
| **Total cost** | $0.0000 |

---

## 🧪 Experiment Results — All Labs

| ID | Description | Status | Score | Latency |
|----|-------------|--------|-------|---------|
| 1a | Baseline retrieval — general RAG question | ✅ | — | 0ms |
| 1b | Specific technical question — Titan normalization | ✅ | — | 0ms |
| 1c | Out-of-domain question — expect refusal not halluc | ✅ | — | 0ms |
| 2a | Graph-connected topic — GraphRAG explanation | ✅ | — | 0ms |
| 2b | Multi-hop question — spans 2 graph hops | ✅ | — | 0ms |
| 2c | Cross-topic question — tests graph expansion | ✅ | — | 0ms |
| 3a | Baseline eval — 5 golden questions | ✅ | 0.72 | 0ms |
| 3b | Full eval — all 11 golden questions | ✅ | 0.72 | 0ms |
| 4a | Faithfulness — factual question (expect high score | ✅ | — | 0ms |
| 4b | Faithfulness — out-of-context trick question | ✅ | — | 0ms |
| 4c | Faithfulness eval — LLM-as-Judge vs keyword compar | ✅ | 0.72 | 0ms |
| 5a | Answer correctness — RAG definition question | ✅ | — | 0ms |
| 5b | Answer correctness — vector DB question | ✅ | — | 0ms |
| 6a | Completeness — multi-aspect question (WHAT/HOW/WHY | ✅ | — | 0ms |
| 6b_single | Completeness — single aspect (for comparison) | ✅ | — | 0ms |
| 6b_multi | Completeness — multi-aspect (for comparison) | ✅ | — | 0ms |
| 7a | Hallucination rate — full eval suite | ✅ | 0.72 | 0ms |
| 7b | Force hallucination — unknowable question | ✅ | — | 0ms |
| 8a_short | Cost — short answer prompt | ✅ | — | 0ms |
| 8a_long | Cost — long answer prompt | ✅ | — | 0ms |
| 9a | Positive feedback (👍) — verify wiki updated | ✅ | — | 0ms |
| 9b | Negative feedback (👎) — verify eval set updated | ✅ | — | 0ms |
| 9c | Eval after feedback — golden set should have grown | ✅ | 0.72 | 0ms |
| 10a | Graph traversal quality — 5 questions | ✅ | 0.72 | 0ms |
| 10b | Multi-hop graph question — tests 2-hop traversal | ✅ | — | 0ms |
| 11a | Provider check — what is currently running? | ✅ | — | 0ms |
| 12a | Final eval — CI/CD gate simulation (pass >= 0.70?) | ✅ | 0.72 | 0ms |

---

## Phase 1 — GraphRAG Foundation

### Lab 1: Vector Search

| Experiment | Question | Retrieval Score | Latency | Has 🫏? |
|------------|----------|----------------|---------|---------|
| 1a | What is RAG and why is it used? | 0.000 | 0ms | ✅ |
| 1b | Why did AWS Titan embeddings score low and ho | 0.000 | 0ms | ✅ |
| 1c | What is the best recipe for Dutch stroopwafel | 0.000 | 0ms | ✅ |

### Lab 2: Graph Traversal

| Experiment | Topics Returned | Answer Preview |
|------------|----------------|----------------|
| 2a | — | [DRY RUN] Answer for: Explain GraphRAG and what makes it different from plain ve... |
| 2b | — | [DRY RUN] Answer for: How does the feedback loop in the knowledge engine connect... |
| 2c | — | [DRY RUN] Answer for: How does the knowledge engine improve over time with user ... |

### Lab 3: Baseline Eval

| Experiment | Pass Rate | Questions | Avg Latency |
|------------|-----------|-----------|-------------|
| 3a | 0.72 | 11 | 0ms |
| 3b | 0.72 | 11 | 0ms |

---

## Phase 2 — Missing Metrics (5 gaps from rag-chatbot)

### Lab 4: LLM-as-Judge Faithfulness

| Experiment | Faithfulness | Has Hallucination | Method |
|------------|-------------|-------------------|--------|
| 4a — Faithfulness — factual question (expect  | 0.0 | ✅ NO | LLM-as-Judge |
| 4b — Faithfulness — out-of-context trick ques | 0.0 | ✅ NO | LLM-as-Judge |

### Lab 5: Answer Correctness (Semantic)

| Experiment | Question | Answer Correctness | Answer Relevance (keyword) |
|------------|----------|-------------------|---------------------------|
| 5a | What is RAG and why is it used instead o | 0.0 | 0.0 |
| 5b | What does the vector database store? | 0.0 | 0.0 |

### Lab 6: Completeness Score

| Experiment | Type | Completeness | Aspects in Q | Aspects Answered |
|------------|------|-------------|--------------|-----------------|
| 6a | Multi-aspect | 0.0 | — | — |
| 6b_single | Single | 0.0 | — | — |
| 6b_multi | Multi-aspect | 0.0 | — | — |

### Lab 7: Hallucination Rate

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| `hallucination_rate_pct` | 9.1% | < 10% | ✅ PASS |

### Lab 8: Cost Per Query

| Prompt Type | Total Tokens | Cost (USD) |
|-------------|-------------|------------|
| Short | — | $— |
| Long | — | $— |

---

## Phase 3 — Production

### Lab 9: Feedback Loops

| Experiment | Feedback Type | Action | Status |
|------------|--------------|--------|--------|
| 9a | positive | wiki_updated | ✅ |
| 9b | negative | eval_set_updated | ✅ |

### Lab 12: CI/CD Eval Gate Simulation

| Threshold | Actual Pass Rate | Gate Result |
|-----------|-----------------|-------------|
| 70% | 0.72 | ✅ WOULD PASS |

---

## 🫏 Donkey Analogy Spot-Check

All answers should contain a donkey analogy. Checking Lab 1-3 answers:

| Experiment | Contains 🫏? | Analogy Preview |
|------------|-------------|----------------|
| 1a | ✅ | 🫏 [DRY RUN] |
| 2a | ✅ | 🫏 [DRY RUN] |
| 3a | ❌ | — |

---

## 📁 Output Files

Results saved to: `scripts/lab-results/local/`
- `run-results.json` — full raw results
- `eval-summary.json` — 9-metric eval summary
- `lab-results-report.md` — this file

---

## 🔁 Comparison With rag-chatbot

```json
{
  "rag_chatbot_had": {
    "avg_faithfulness": 0.75
  },
  "NEW_in_knowledge_engine": {
    "avg_context_recall": 0.65,
    "avg_answer_correctness": 0.6,
    "avg_completeness": 0.7,
    "hallucination_rate_pct": 9.1,
    "avg_cost_per_query_usd": 0.0,
    "faithfulness_upgraded_to_llm_as_judge": true
  }
}
```
