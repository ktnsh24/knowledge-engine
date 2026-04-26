# Hands-On Labs — Phase 3: Production — Feedback Loops, CI/CD, Multi-Cloud

> **Prerequisites:** Phase 1 + Phase 2 complete. Baseline eval scores recorded.
> This phase covers the AI engineer skills rag-chatbot was weakest on (10-40%).

---

## Table of Contents

- [🚚 Phase 3 Metric Overview](#phase-3-metrics)
- [Lab 9: Feedback Loops — "How does the system get smarter?"](#lab-9-feedback-loops)
- [Lab 10: Graph Traversal Quality — "Did the knowledge graph actually help?"](#lab-10-graph-traversal-quality)
- [Lab 11: Multi-Provider Comparison — "Local vs AWS vs Azure"](#lab-11-multi-provider)
- [Lab 12: CI/CD Eval Gate — "Block bad deploys automatically"](#lab-12-cicd-eval-gate)
- [Phase 3 Skills Checklist](#skills-checklist)

---

## 🚚 Phase 3 Metric Overview {#phase-3-metrics}

| Metric | Courier Version | What It Measures |
|--------|---------------|-----------------|
| **Feedback conversion rate** | % of deliveries where the customer said "perfect!" (👍). The higher it is, the better the courier's route planning is. | thumbs_up / total_feedback |
| **Eval set growth rate** | Every 👎 adds a new test case. How fast is the courier's training set growing? | new golden questions / week |
| **Graph traversal quality** | Did the road map (graph) actually help the courier find a shorter route? Or did it just add noise? | topics_cited_in_answer / topics_added_by_graph |
| **Cross-provider pass rate delta** | Does the courier perform equally on Dutch roads (local) vs German autobahn (AWS) vs French toll roads (Azure)? | pass_rate_aws - pass_rate_local |
| **CI/CD eval gate pass rate** | The road inspector automatically blocks new couriers from starting if the road quality drops below 70%. | % of CI runs that passed the eval gate |

---

## Lab 9: Feedback Loops {#lab-9-feedback-loops}

**Skill:** Understand how feedback improves the system over time
**Time:** 25 minutes
**Metric focus:** `feedback_conversion_rate`, `eval_set_growth`

### How the feedback loop works

```
User asks question → gets answer
                           ↓
         👍 THUMBS UP              👎 THUMBS DOWN
              ↓                           ↓
  Saved to wiki/feedback/         Added to golden-questions.yaml
  verified-answers.md             (the eval set grows!)
              ↓                           ↓
  Next chat uses this              Next eval run includes
  as context                       this question
              ↓                           ↓
  Better answers for               CI/CD gate catches
  similar questions                regressions automatically
```

### Experiment 9a — Submit positive feedback (👍)

Ask a question, then submit feedback via API:

```bash
# Step 1: Ask question
RESPONSE=$(curl -s -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the courier analogy in this project?"}')

echo $RESPONSE | python3 -m json.tool

# Step 2: Submit thumbs up
curl -X POST http://localhost:8200/feedback/ \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the courier analogy in this project?",
    "answer": "The LLM is the courier...",
    "thumbs_up": true,
    "session_id": "lab-session-1"
  }'
```

📝 **Check the wiki feedback file was updated:**

```bash
cat wiki-output/feedback/verified-answers.md
```

| Check | Expected | Actual |
|-------|----------|--------|
| File exists? | Yes | ___ |
| Contains your Q&A? | Yes | ___ |
| Timestamp correct? | Yes | ___ |

### Experiment 9b — Submit negative feedback (👎)

```bash
curl -X POST http://localhost:8200/feedback/ \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What AWS services does the knowledge engine use?",
    "answer": "It uses EC2 and RDS.",
    "thumbs_up": false,
    "correction": "It uses DynamoDB for graph and vector store, and Bedrock for LLM.",
    "session_id": "lab-session-1"
  }'
```

📝 **Check the eval set was updated:**

```bash
tail -15 scripts/golden-questions.yaml
```

| Check | Expected | Actual |
|-------|----------|--------|
| New question at bottom of YAML? | Yes | ___ |
| `added_from_feedback: true` flag? | Yes | ___ |
| Correction saved? | Yes | ___ |

### Experiment 9c — Re-run eval to pick up the new question

```bash
# Run eval — it now includes your feedback question
curl -X POST http://localhost:8200/eval/run -d '{"n_questions": null}'
# null = run ALL questions including new feedback ones
```

📝 **Record:**

| Metric | Before feedback | After feedback |
|--------|----------------|----------------|
| Total golden questions | 11 | ___ |
| `pass_rate` | ___ | ___ |

> 🚚 The feedback question will likely fail on first run (the system made a mistake on it).
> That's CORRECT — it should fail. This is how the eval set catches regressions:
> next time you fix the system, this question must pass before you can deploy.

### What you learned

- [ ] 👍 feedback → wiki verified-answers.md (more context for similar future questions)
- [ ] 👎 feedback → golden-questions.yaml (harder eval set, catches regressions)
- [ ] The more you use the system, the harder the eval set becomes
- [ ] A harder eval set = more confidence when CI/CD gate passes

---

## Lab 10: Graph Traversal Quality {#lab-10-graph-traversal-quality}

**Skill:** Measure whether graph expansion is actually useful
**Time:** 20 minutes
**Metric focus:** `graph_expansion_useful`, `topics_cited_in_answer`, `topics_added_by_graph`

### Concept

Graph traversal can add noise if:
- Topics are too generic (everything connects to "python")
- Max hops is too large (reaches unrelated topics)
- LLM ignores the topic list

Graph traversal is useful when:
- Topics are specific and connected (e.g., "titan-embeddings" → "normalization" → "cosine-similarity")
- LLM mentions the graph-expanded topics in its answer
- Context recall improves (Phase 1, Lab 2)

### Experiment 10a — Check graph traversal quality on eval run

```bash
curl -X POST http://localhost:8200/eval/run \
  -d '{"n_questions": 5}' | python3 -m json.tool | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
for r in data.get('results', []):
    g = r['scores']
    print(f\"Q: {r['question'][:50]}\")
    print(f\"  graph_topics_added: {g['graph_topics_added']}\")
    print(f\"  graph_expansion_useful: {g['graph_expansion_useful']}\")
    print()
"
```

📝 **Record:**

| Question | `graph_topics_added` | `graph_expansion_useful` | Topics cited |
|----------|---------------------|-------------------------|-------------|
| Q1 | ___ | ___ | ___ |
| Q2 | ___ | ___ | ___ |
| Q3 | ___ | ___ | ___ |

### Experiment 10b — Tune max_hops

In `.env`, change `GRAPH_MAX_HOPS=2` to `GRAPH_MAX_HOPS=1`, restart, re-run:

```bash
# With max_hops=1 (direct neighbours only)
GRAPH_MAX_HOPS=1 poetry run start &
curl -X POST http://localhost:8200/eval/run -d '{"n_questions": 5}'
```

📝 **Compare:**

| Setting | `avg_context_recall` | `graph_expansion_useful %` | `avg_latency_ms` |
|---------|---------------------|---------------------------|-----------------|
| max_hops=1 | ___ | ___ | ___ |
| max_hops=2 | ___ | ___ | ___ |

> The sweet spot: enough hops to improve recall without adding noise or latency.

### What you learned

- [ ] `graph_expansion_useful=false` = topics found but LLM didn't use them
- [ ] More hops = better recall but more latency and potential noise
- [ ] If > 50% of eval questions show `graph_expansion_useful=false`, reduce max_hops

---

## Lab 11: Multi-Provider Comparison {#lab-11-multi-provider}

**Skill:** Run the same eval across Local, AWS, Azure — compare all metrics
**Time:** 30 minutes (assumes you've run Terraform for at least one cloud provider)
**Metric focus:** all metrics, cross-provider delta

> 🚚 This is the 3-way courier race. Same road (your docs), same packages (golden questions),
> three different couriers (Ollama, Bedrock, GPT-4o-mini). Who delivers best?
> rag-chatbot did this — knowledge-engine goes further with 7 more metrics.

### Experiment 11a — Local baseline (already have this)

Check your Phase 2 results file:

```bash
ls scripts/eval-results/eval-local-*.json | tail -1 | xargs python3 -m json.tool | grep -A20 '"metrics"'
```

📝 **Record local baseline (all 9 metrics):**

| Metric | Local |
|--------|-------|
| `avg_retrieval` | ___ |
| `avg_context_precision` | ___ |
| `avg_context_recall` | ___ |
| `avg_faithfulness` | ___ |
| `avg_answer_relevance` | ___ |
| `avg_answer_correctness` | ___ |
| `avg_completeness` | ___ |
| `hallucination_rate_pct` | ___ |
| `avg_cost_per_query_usd` | $0.00 |
| `pass_rate` | ___ |

### Experiment 11b — AWS run (optional, ~€0.02)

```bash
# Set AWS provider
CLOUD_PROVIDER=aws poetry run start &

curl -X POST http://localhost:8200/eval/run -d '{"n_questions": 11}'
```

📝 **Record AWS results:**

| Metric | Local | AWS | Delta (AWS-Local) |
|--------|-------|-----|------------------|
| `avg_retrieval` | ___ | ___ | ___ |
| `avg_context_recall` | ___ | ___ | ___ |
| `avg_faithfulness` | ___ | ___ | ___ |
| `hallucination_rate_pct` | ___ | ___ | ___ |
| `avg_cost_per_query_usd` | $0.00 | ___ | ___ |
| `pass_rate` | ___ | ___ | ___ |

### Experiment 11c — Build the 3-way comparison table

After running all 3 providers, fill in this full comparison:

| Metric | Local (Ollama) | AWS (Bedrock Haiku) | Azure (GPT-4o-mini) | Best |
|--------|---------------|---------------------|---------------------|------|
| `avg_retrieval` | ___ | ___ | ___ | ___ |
| `avg_context_precision` | ___ | ___ | ___ | ___ |
| `avg_context_recall` | ___ | ___ | ___ | ___ |
| `avg_faithfulness` | ___ | ___ | ___ | ___ |
| `avg_answer_correctness` | ___ | ___ | ___ | ___ |
| `avg_completeness` | ___ | ___ | ___ | ___ |
| `hallucination_rate_pct` | ___ | ___ | ___ | ___ |
| `avg_latency_ms` | ___ | ___ | ___ | ___ |
| `avg_cost_per_query_usd` | $0 | ___ | ___ | Local |
| **`pass_rate`** | ___ | ___ | ___ | ___ |

> This is the knowledge-engine equivalent of the rag-chatbot 3-way comparison doc.
> But with 9 metrics instead of 3 — including all 5 that were missing from rag-chatbot.

---

## Lab 12: CI/CD Eval Gate {#lab-12-cicd-eval-gate}

**Skill:** Understand how eval gates block bad deployments
**Time:** 20 minutes

### Concept

```
Developer changes chunk_size from 800 → 400 words
         ↓
Push to GitHub → CI runs automatically
         ↓
GitHub Actions: poetry run pytest tests/
         ↓
Tests pass → proceed to eval gate
         ↓
curl -X POST http://localhost:8200/eval/run
         ↓
pass_rate = 0.45   →  < 0.70 threshold
         ↓
❌ CI FAILS — deploy blocked
Message: "Eval gate failed: pass_rate=0.45 < required 0.70"
Developer must fix chunking before merge
```

### Experiment 12a — Simulate an eval gate failure

Change the chunking to a bad value, run eval, see if pass rate drops:

```bash
# Temporarily change CHUNK_SIZE in .env to 50 (very small = bad chunks)
echo "CHUNK_SIZE=50" >> .env

# Re-ingest with bad chunks
curl -X POST http://localhost:8200/ingest/run
sleep 30

# Run eval — expect lower scores
curl -X POST http://localhost:8200/eval/run -d '{"n_questions": 5}'
```

📝 **Record:**

| Setting | `pass_rate` | `avg_retrieval` | Would CI gate block? |
|---------|------------|----------------|---------------------|
| CHUNK_SIZE=800 (normal) | ___ | ___ | ___ |
| CHUNK_SIZE=50 (broken) | ___ | ___ | ___ |

> If pass_rate drops below 0.70 → CI gate blocks deploy. This is exactly what rag-chatbot was missing (had CI but no eval gate — score: 10%).

### Experiment 12b — Look at the CI workflow

```bash
cat .github/workflows/ci.yml
```

Identify:
- Where does the eval gate check happen?
- What threshold does it use?
- What happens if eval fails?

📝 **Answers:**

| Question | Answer |
|----------|--------|
| Eval gate threshold | ___ |
| What runs before eval? | ___ |
| How is gate failure reported? | ___ |

### Experiment 12c — Understand the wiki-rebuild workflow

```bash
cat .github/workflows/wiki-rebuild.yml
```

📝 **Understand:**
- What triggers this workflow? ___
- What does it do? ___
- Why is it important for the "self-improving" loop? ___

### What you learned

- [ ] CI/CD eval gates automate quality control — humans don't have to manually check
- [ ] The 70% threshold is a starting point — production systems often require 85%+
- [ ] wiki-rebuild.yml closes the loop: docs change → wiki auto-updates → users see fresh knowledge
- [ ] rag-chatbot had CI but no eval gate (score: 10%) — knowledge-engine has both (score: 80%+)

---

## Phase 3 Skills Checklist {#skills-checklist}

- [ ] Can explain the full feedback → eval set → CI gate loop
- [ ] Have submitted both 👍 and 👎 feedback and verified the files were updated
- [ ] Have measured `graph_expansion_useful` and tuned max_hops
- [ ] Have run at least 2 providers and built a comparison table
- [ ] Can explain what a CI/CD eval gate is and why rag-chatbot lacked it
- [ ] Know the difference between `has_hallucination` (per query) and `hallucination_rate` (system-level %)

---

## Full Metrics Summary — All 9 Metrics Explained

| Metric | In rag-chatbot? | Method | Pass threshold |
|--------|----------------|--------|----------------|
| `avg_retrieval` | ✅ Yes | Cosine similarity avg | > 0.5 |
| `avg_context_precision` | ✅ Yes (basic) | Relevant chunks / total chunks | > 0.6 |
| `avg_faithfulness` | ✅ Yes (keyword) | **UPGRADED to LLM-as-Judge** | > 0.7 |
| `avg_answer_relevance` | ✅ Yes (keyword) | Keyword overlap Q↔A | > 0.5 |
| `avg_context_recall` | ❌ **MISSING** | Expected topics found / total | > 0.6 |
| `avg_answer_correctness` | ❌ **MISSING** | Semantic cosine vs expected | > 0.6 |
| `avg_completeness` | ❌ **MISSING** | LLM-as-Judge: aspects covered | > 0.6 |
| `hallucination_rate_pct` | ❌ **MISSING** | % queries with hallucination | < 10% |
| `avg_cost_per_query_usd` | ❌ **MISSING** | Tokens × provider rate | < $0.002 |
| `graph_expansion_useful%` | ❌ **N/A** (new concept) | Topics cited / topics added | > 50% |
