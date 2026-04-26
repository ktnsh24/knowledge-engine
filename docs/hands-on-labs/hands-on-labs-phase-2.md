# Hands-On Labs — Phase 2: Missing Metrics (What rag-chatbot Couldn't Measure)

> **Prerequisites:** Phase 1 complete, docs ingested, eval suite baseline recorded.
> This phase focuses on the **5 metrics that were MISSING from rag-chatbot**.

---

## Table of Contents

- [🚚 Phase 2 Metric Overview](#phase-2-metrics)
- [Lab 4: LLM-as-Judge Faithfulness — "Is the AI making things up?"](#lab-4-llm-as-judge)
- [Lab 5: Answer Correctness — "Is the answer actually right?"](#lab-5-answer-correctness)
- [Lab 6: Completeness Score — "Did the answer cover everything?"](#lab-6-completeness)
- [Lab 7: Hallucination Rate — "How often does it hallucinate?"](#lab-7-hallucination-rate)
- [Lab 8: Cost Per Query — "How much did that answer cost?"](#lab-8-cost-per-query)
- [Phase 2 Skills Checklist](#skills-checklist)

---

## 🚚 Phase 2 Metric Overview {#phase-2-metrics}

These 5 metrics existed in the rag-chatbot design docs but were **never implemented**.

| Metric | Why Missing in rag-chatbot | How We Fixed It |
|--------|---------------------------|----------------|
| **LLM-as-Judge Faithfulness** | Code said *"upgrade to LLM-as-judge for production"* — never done | LLM scores its own answer: "does this claim exist in the context?" |
| **Answer Correctness (semantic)** | `answer_relevance` was keyword overlap, not semantic similarity | Embed answer + expected answer → cosine similarity |
| **Completeness Score** | Listed as exercise question in eval docs, never implemented | LLM-as-Judge: "how many aspects of the question were answered?" |
| **Hallucination Rate (%)** | `has_hallucination` was per-query boolean, not an aggregate | `hallucination_rate = hallucinators / total × 100` across eval run |
| **Cost Per Query** | Mentioned in `metrics-deep-dive.md` but never tracked in evaluator | Token counts × provider rates → € per query |

> 🚚 The courier always delivered. But until now, nobody was measuring:
> — did it deliver the RIGHT thing? (correctness)
> — did it invent extra packages that weren't ordered? (hallucination rate)
> — did it deliver ALL the ordered packages? (completeness)
> — how much did the trip cost? (cost per query)

---

## Lab 4: LLM-as-Judge Faithfulness {#lab-4-llm-as-judge}

**What rag-chatbot did:** Keyword overlap — count how many answer sentences contain words from the retrieved chunks.
**What this does:** Asks the LLM itself: *"Does this answer contain claims not supported by the context?"*

**Skill:** Understand LLM-as-Judge pattern, detect hallucination with AI
**Time:** 25 minutes
**Metric focus:** `faithfulness`, `faithfulness_method`, `has_hallucination`

### Concept

```
rag-chatbot (keyword method):
  "Refunds take 14 days" → extract keywords ["refunds", "take", "days"]
  → check if all appear in context → YES → score: 1.0
  Problem: "Refunds take 14 days at the Vatican" → keywords still match!

knowledge-engine (LLM-as-Judge):
  LLM reads context + answer together
  LLM asks: "Is '14 days at the Vatican' in the context?"
  LLM says: "No" → flags as hallucination → score: 0.3
```

### Experiment 4a — Ask a factual question (should score high faithfulness)

```bash
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What embedding model was used in the rag-chatbot project?"}'
```

📝 **Record:**

| Metric | Value | What it means |
|--------|-------|---------------|
| `faithfulness` score | ___ | 1.0 = fully grounded |
| `faithfulness_method` | `llm-as-judge` or `keyword-heuristic` | — |
| `has_hallucination` | true/false | false = good |
| `flagged_claims` (if any) | ___ | These sentences are suspicious |

### Experiment 4b — Trick the LLM (out-of-context question)

```bash
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What was the weather in Amsterdam when the rag-chatbot was built?"}'
```

This is NOT in any docs. The LLM should either refuse OR hallucinate.

📝 **Record:**

| Metric | Value | Correct behaviour? |
|--------|-------|-------------------|
| `faithfulness` | ___ | Should be < 0.5 if it hallucinated |
| `has_hallucination` | ___ | Should be `true` |
| Did LLM refuse? | Yes/No | `true` = better (said "I don't know") |
| Did LLM hallucinate? | Yes/No | `false` = better |

### Experiment 4c — Compare: LLM-as-Judge vs Keyword Method

Run the eval endpoint and look at the comparison field:

```bash
curl -X POST http://localhost:8200/eval/run \
  -H "Content-Type: application/json" \
  -d '{"n_questions": 3}'
```

In the response JSON, find `comparison_with_rag_chatbot`:

```json
{
  "rag_chatbot_had": {
    "faithfulness_keyword_based": 0.82
  },
  "NEW_in_knowledge_engine": {
    "avg_faithfulness (llm-as-judge)": 0.91,
    "faithfulness_upgraded_to_llm_as_judge": true
  }
}
```

📝 **Record the gap:**

| Method | Score | Difference |
|--------|-------|-----------|
| rag-chatbot keyword method | ___ | — |
| knowledge-engine LLM-as-Judge | ___ | ___ |

> The gap tells you how much the keyword method was over- or under-counting faithfulness.

### What you learned

- [ ] LLM-as-Judge catches subtle semantic hallucinations that keyword matching misses
- [ ] `faithfulness_method: "keyword-heuristic"` = LLM unavailable, fell back
- [ ] Low faithfulness + refused answer = CORRECT behaviour (no hallucination)
- [ ] Low faithfulness + long answer = HALLUCINATION (LLM made things up)

---

## Lab 5: Answer Correctness — "Is the answer actually right?" {#lab-5-answer-correctness}

**What rag-chatbot did:** `answer_relevance` = keyword overlap between question and answer.
That measures "is the answer on-topic?" — NOT "is the answer correct?"

**What this does:** Semantic cosine similarity between answer embedding and expected/ground-truth answer.

**Skill:** Understand semantic similarity vs keyword matching
**Time:** 20 minutes
**Metric focus:** `answer_correctness`, `answer_correctness_method`

### Concept

```
rag-chatbot (keyword method):
  Question: "What is RAG?"
  Answer: "RAG is a system that retrieves documents and generates answers using context."
  Expected: "Retrieval Augmented Generation combines retrieval with LLM generation."
  
  Keyword score: "RAG", "retrieves", "generates" overlap = 0.6 ✅ seems good
  Problem: "RAG is a type of carpet cleaning" also scores 0.5!

knowledge-engine (semantic embedding):
  Embed(answer) vs Embed(expected):
  If meaning is the same → cosine similarity > 0.8 ✅
  "RAG is carpet cleaning" → cosine similarity < 0.2 ❌ (caught!)
```

### Experiment 5a — Question with known expected answer

Edit `scripts/golden-questions.yaml` to add an `expected_answer` to one question:

```yaml
questions:
  - question: "What is RAG and why is it used instead of fine-tuning?"
    expected_topics: ["rag", "retrieval", "embeddings"]
    expected_answer: "RAG combines retrieval with LLM generation to answer questions using document context. It is preferred over fine-tuning because it is cheaper, faster to update, and doesn't require retraining."
```

Then run eval:

```bash
curl -X POST http://localhost:8200/eval/run -d '{"n_questions": 1}'
```

📝 **Record:**

| Metric | Value | What it means |
|--------|-------|---------------|
| `answer_correctness` | ___ | > 0.7 = semantically similar to expected |
| `answer_correctness_method` | `semantic-embedding` or `keyword-fallback` | — |
| `answer_relevance` (old metric) | ___ | Compare: keyword method vs semantic |

### Experiment 5b — See the gap between keyword and semantic scoring

Ask a question where a wrong answer could still match keywords:

```bash
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What does the vector database store?"}'
```

A wrong answer: *"The vector database stores customer data and shopping carts."*
This contains keywords like "vector", "database", "stores" — keyword score = high.
But semantic similarity to the correct answer = low.

📝 **Reflect:** Could the rag-chatbot evaluator have caught this wrong answer? ___

### What you learned

- [ ] `answer_correctness` requires `expected_answer` in golden-questions.yaml
- [ ] Semantic method embeds both answer and expected — cosine similarity
- [ ] Keyword method can be fooled by wrong answers that use the same vocabulary
- [ ] `method: "not-available"` = no expected_answer set for that question

---

## Lab 6: Completeness Score {#lab-6-completeness}

**What rag-chatbot did:** Nothing. Evaluation docs listed it as exercise #4 *"How would you add completeness?"* — never implemented.

**What this does:** LLM-as-Judge counts how many aspects of a multi-part question were answered.

**Skill:** Understand completeness evaluation, multi-part questions
**Time:** 20 minutes
**Metric focus:** `completeness`, `aspects_in_question`, `aspects_answered`

### Concept

```
Question: "What is GraphRAG, how does it work, and why is it better than plain RAG?"
         ↓ has 3 aspects: WHAT, HOW, WHY

Full answer covers all 3 → completeness = 1.0
Answer only explains WHAT → completeness = 0.33
Answer explains WHAT + HOW but not WHY → completeness = 0.67
```

### Experiment 6a — Multi-aspect question

```bash
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What is GraphRAG, how does it combine vector and graph stores, and why does it improve answer quality?"}'
```

📝 **Record:**

| Metric | Value | What it means |
|--------|-------|---------------|
| `completeness` score | ___ | 1.0 = all aspects covered |
| `aspects_in_question` | ___ | LLM-as-Judge counted N aspects |
| `aspects_answered` | ___ | How many the answer addressed |

### Experiment 6b — Single-aspect vs multi-aspect

Compare these two questions:

```bash
# Single aspect:
curl -X POST http://localhost:8200/chat/ \
  -d '{"question": "What is a vector database?"}'

# Multi-aspect:
curl -X POST http://localhost:8200/chat/ \
  -d '{"question": "What is a vector database, why do we need it, and how is it different from a graph database?"}'
```

📝 **Compare:**

| Question Type | `completeness` | `aspects_in_question` |
|--------------|----------------|----------------------|
| Single aspect | ___ | 1 |
| Multi-aspect | ___ | 3 |

> 🚚 Single-aspect = one package ordered. Multi-aspect = three packages. Completeness = did the courier deliver ALL of them?

### What you learned

- [ ] Completeness is separate from relevance — an answer can be relevant but incomplete
- [ ] Use multi-aspect questions in your golden dataset to test completeness
- [ ] `completeness < 0.5` = answer missed major parts of the question

---

## Lab 7: Hallucination Rate {#lab-7-hallucination-rate}

**What rag-chatbot did:** `has_hallucination = true/false` per single query — binary, not aggregated.
**What this does:** Tracks `hallucination_rate` = % of all eval questions where hallucination occurred.

**Skill:** Understand hallucination at system level (not just per-query)
**Time:** 15 minutes
**Metric focus:** `hallucination_rate_pct` in eval summary

### Concept

```
rag-chatbot: "This query has_hallucination = True"
             → useful for debugging 1 query
             → NOT useful for "is my system safe to deploy?"

knowledge-engine:
  11 golden questions evaluated
  3 had hallucination → hallucination_rate = 3/11 = 27%
  
  Threshold: < 10% = production-ready
             10-25% = needs tuning
             > 25% = do NOT deploy
```

### Experiment 7a — Run full eval, check hallucination rate

```bash
curl -X POST http://localhost:8200/eval/run \
  -d '{"n_questions": 11}' | python3 -m json.tool | grep -A5 "hallucination"
```

📝 **Record:**

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| `hallucination_rate_pct` | ___ | < 10% | Pass/Fail |
| Questions with hallucination | ___ | — | — |

### Experiment 7b — Force a hallucination

```bash
curl -X POST http://localhost:8200/chat/ \
  -d '{"question": "What was Ketan Sahu doing on March 15th 2020?"}'
```

This cannot be in any doc. Either: correct = "I don't have this information".
Incorrect = any specific answer about that date.

📝 **Record:**
- Did the LLM hallucinate? ___
- What was the `faithfulness` score? ___
- Did `has_hallucination = true`? ___

### What you learned

- [ ] Hallucination RATE (%) is more useful for production decisions than per-query boolean
- [ ] < 10% rate = generally safe for production
- [ ] The LLM-as-Judge faithfulness score drives the rate calculation

---

## Lab 8: Cost Per Query {#lab-8-cost-per-query}

**What rag-chatbot did:** Documented `cost_per_run` in `metrics-deep-dive.md` but never tracked in evaluator.
**What this does:** Tracks `input_tokens`, `output_tokens`, and `cost_usd` per query in the eval results.

**Skill:** Understand token economics, cost optimization
**Time:** 15 minutes
**Metric focus:** `total_tokens`, `cost_usd`, `avg_cost_per_query_usd`

### Token Cost Reference

| Provider | Model | Input cost / 1K tokens | Output cost / 1K tokens |
|----------|-------|------------------------|--------------------------|
| Local | Ollama llama3.2 | **€0** | **€0** |
| AWS | Bedrock Claude Haiku | $0.00025 | $0.00125 |
| Azure | GPT-4o-mini | $0.00015 | $0.00060 |

> Output tokens are always more expensive — they're generated, not just processed.

### Experiment 8a — Local cost (should be €0)

```bash
curl -X POST http://localhost:8200/eval/run \
  -d '{"n_questions": 3}' | python3 -m json.tool | grep -A5 "cost"
```

📝 **Record:**

| Metric | Value |
|--------|-------|
| `avg_cost_per_query_usd` | Should be $0.00 |
| `total_cost_usd` | Should be $0.00 |
| Provider | local |

### Experiment 8b — Estimate cost for AWS

Without switching to AWS, calculate manually:

One typical answer:
- Input: ~2000 tokens (context + question)
- Output: ~400 tokens (answer)

```python
input_cost = 2000 / 1000 * 0.00025   # = $0.0005
output_cost = 400 / 1000 * 0.00125   # = $0.0005
total = input_cost + output_cost       # = $0.001 per query
```

📝 **Estimate for 11 golden questions on AWS:**

| Calculation | Value |
|-------------|-------|
| Cost per query | ~$0.001 |
| × 11 questions | ~$0.011 |
| × 10 eval runs per project | ~$0.11 total |

> 🚚 The courier's wages: local = volunteer, AWS = €0.001/delivery, Azure = €0.0009/delivery.
> Cost per query × daily queries = monthly bill. Know this before deploying.

### Experiment 8c — Compare verbosity: short vs long answer

Long answers use more output tokens = more expensive.

```bash
# Short prompt (short answer expected)
curl -X POST http://localhost:8200/chat/ \
  -d '{"question": "Define RAG in one sentence."}'

# Long prompt (long answer expected)
curl -X POST http://localhost:8200/chat/ \
  -d '{"question": "Explain the entire rag-chatbot architecture in detail including all components, how they interact, the evaluation framework, the cloud deployment options, and the lessons learned from AWS runs."}'
```

📝 **Compare token usage:**

| Question | `total_tokens` | `cost_usd` |
|----------|---------------|-----------|
| Short | ___ | ___ |
| Long | ___ | ___ |

### What you learned

- [ ] Output tokens cost 4-5× more than input tokens
- [ ] Local = free always. Use local for iteration, cloud only to validate.
- [ ] `avg_cost_per_query_usd` in eval summary lets you project monthly costs
- [ ] Verbose answers = more cost — tune `max_tokens` in production

---

## Phase 2 Skills Checklist {#skills-checklist}

- [ ] Can explain LLM-as-Judge vs keyword faithfulness — and when each is appropriate
- [ ] Know what `answer_correctness` requires (expected_answer in golden questions)
- [ ] Understand completeness as distinct from relevance
- [ ] Know the hallucination rate threshold for production (< 10%)
- [ ] Can estimate monthly LLM cost given avg tokens per query and query volume
- [ ] Have run all 5 new metrics end-to-end on the golden question set
- [ ] Have recorded the `comparison_with_rag_chatbot` output showing the improvement
