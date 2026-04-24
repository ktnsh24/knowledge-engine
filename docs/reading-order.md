# 📚 Documentation Reading Order

> A guided path through the knowledge-engine docs. Start at Level 1 and work down.

---

## Level 1 — Start Here (The Big Picture)

| # | Document | What you'll learn |
|---|----------|-------------------|
| 1 | [README.md](../README.md) | Project overview, features, what makes this different from rag-chatbot |
| 2 | [Architecture](../architecture.md) | GraphRAG data flow, why both graph + vector, donkey analogy, cost per provider |

---

## Level 2 — Setup & Run It

| # | Document | What you'll learn |
|---|----------|-------------------|
| 3 | [Getting Started](setup-and-tooling/getting-started.md) | Full step-by-step: install, configure, start, ingest, ask first question |
| 4 | [How to Verify It's Working](../how-to-verify.md) | How to see the connected map, how to confirm the knowledge base is growing |

---

## Level 3 — Run the Experiments

| # | Document | What you'll learn |
|---|----------|-------------------|
| 5 | [Phase 1 — GraphRAG Foundation](hands-on-labs/hands-on-labs-phase-1.md) | Ingestion, graph traversal, baseline retrieval eval |
| 6 | [Phase 2 — Missing Metrics](hands-on-labs/hands-on-labs-phase-2.md) | The 5 gaps from rag-chatbot: faithfulness (LLM-as-Judge), context recall, answer correctness, completeness, hallucination rate |
| 7 | [Phase 3 — Production](hands-on-labs/hands-on-labs-phase-3.md) | Feedback loops, multi-cloud, CI/CD gate |

---

## Quick Reference

- **"I want to run it"** → Start at doc #3 (Getting Started)
- **"I want to understand the architecture"** → Start at doc #2 (Architecture)
- **"How do I know it's working?"** → Read doc #4 (How to Verify)
- **"I want to run the experiments"** → Follow docs #5 → #7 in order
- **"I want to deploy to AWS"** → Getting Started Steps 12–12e
- **"I want to deploy to Azure"** → Getting Started Steps 13–13f
