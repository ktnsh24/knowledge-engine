# 📚 Documentation Reading Order

> A guided path through the knowledge-engine docs. Start at Level 1 and work your way down. Placeholders marked *(coming in batch C/D)* are docs that land in subsequent documentation batches — the filename is the contract; the content fills in later.

---

## Table of Contents

- [Level 1 — Big Picture](#level-1--big-picture)
- [Level 2 — Setup & Run](#level-2--setup--run)
- [Level 3 — Deep Dives (GraphRAG Pipeline)](#level-3--deep-dives-graphrag-pipeline)
- [Level 4 — API](#level-4--api)
- [Level 5 — Cloud](#level-5--cloud)
- [Level 6 — Evaluation & Reference](#level-6--evaluation--reference)
- [Level 7 — Hands-On Labs](#level-7--hands-on-labs)
- [Quick Reference](#quick-reference)

---

## Level 1 — Big Picture

Read these first to understand what this project is and how GraphRAG differs from plain RAG.

| # | Document | What you'll learn | 🫏 Donkey |
|---|----------|-------------------|-----------|
| 1 | [README.md](../README.md) | Project overview, providers, what makes this different from rag-chatbot | The stable notice board — what the donkey carries (LLM + GPS warehouse + paper map), what makes this stable special compared to the plain-RAG one next door |
| 2 | [GraphRAG Concepts](ai-engineering/graphrag-concepts.md) | What GraphRAG is, why a graph AND a vector store, the data model, when NOT to use it | The training manual for the upgraded donkey — why GPS coordinates alone aren't enough and the paper town map earns its keep |
| 3 | [Architecture Overview](architecture.md) | System diagram, data flow, provider matrix, cost architecture | The delivery route map — every road, junction, and stable from raw doc to final answer with tolls listed |

---

## Level 2 — Setup & Run

Now get the project running on your machine.

| # | Document | What you'll learn | 🫏 Donkey |
|---|----------|-------------------|-----------|
| 4 | [Getting Started — Full](setup-and-tooling/getting-started.md) | Step-by-step: install Python + Poetry, configure `.env`, start Neo4j + ChromaDB, ingest, ask the first question | Loading the donkey from scratch — install the gear, fill the GPS warehouse and paper map, send the first delivery |
| 5 | [Getting Started — Quick Start](getting-started.md) | The 30-second copy-paste version of doc #4 for people who already have Python + Docker + Ollama | Express loading dock — skip the orientation, go straight to the first delivery |
| 6 | [How to Verify](how-to-verify.md) | How to see the connected map (Neo4j Browser, `/wiki/graph`), confirm chunks + topics are growing, prove the self-improving loop works | The supervisor's clipboard — count the warehouse shelves, look at the map on the wall, confirm yesterday's 👍 answers are now part of the corpus |

---

## Level 3 — Deep Dives (GraphRAG Pipeline)

One file per stage of the pipeline, in data-flow order. These are the "how does it actually work" docs.

| # | Document | What you'll learn | 🫏 Donkey |
|---|----------|-------------------|-----------|
| 7 | [Ingestion Pipeline Deep Dive](ai-engineering/ingestion-pipeline-deep-dive.md) | Scanner → chunker → embedder → graph extractor → both stores in one pass | The post office pre-sort — every letter cut into pages, GPS-stamped, AND mapped on the town map before the donkey arrives |
| 8 | [Graph Extractor Deep Dive](ai-engineering/graph-extractor-deep-dive.md) | How the LLM is prompted to emit topics + typed relationships from each chunk, with `evidence` for audit | The town-cartographer at work — reading every delivery note and pencilling new towns and roads onto the official paper map |
| 9 | [Vector Store Interface](ai-engineering/vectorstore-interface-deep-dive.md) | The `BaseVectorStore` contract: `upsert / search / chunk_count / delete_by_source` | The warehouse door rules — any GPS warehouse that follows this contract can serve the donkey |
| 10 | [Vector Store Providers](ai-engineering/vectorstore-providers-deep-dive.md) | ChromaDB (local), DynamoDB (AWS) with Python cosine, Azure AI Search — how each implements the interface | Three GPS warehouses the donkey can use — local barn (Chroma), AWS depot (DynamoDB), Azure hub (AI Search) — same contract, different floor plans |
| 11 | [Graph Store Interface](ai-engineering/graphstore-interface-deep-dive.md) | The `BaseGraphStore` contract: `upsert_topic / upsert_relationship / get_connected_topics / get_full_graph` | The map-room rules — any paper-map workshop that follows this contract can hang on the donkey's wall |
| 12 | [Graph Store Providers](ai-engineering/graphstore-providers-deep-dive.md) | Neo4j Community (local), DynamoDB adjacency-list (AWS), Cosmos DB NoSQL (Azure) — same model, three storage tricks | Three paper maps — Neo4j drawn in proper graph ink, DynamoDB rolled up as adjacency-list rows, Cosmos NoSQL pinned as document pages |
| 13 | [LLM Interface](ai-engineering/llm-interface-deep-dive.md) | The `BaseLLM` contract: `complete / extract_topics_and_relations / generate_wiki_page` | The writing desk rules — any donkey that wants to sit at this desk must speak these three sentences |
| 14 | [LLM Providers](ai-engineering/llm-providers-deep-dive.md) | Ollama llama3.2 (local), Bedrock Claude Haiku (AWS), Azure OpenAI GPT-4o-mini — handwriting differences | Three writers at the desk — local llama, AWS Claude Haiku, Azure GPT-4o-mini — same three sentences, very different handwriting and speed |
| 15 | [Chat Engine Deep Dive](ai-engineering/chat-engine-deep-dive.md) | Vector search → graph expand → gap check → LLM answer; how the three stores cooperate per query | The dispatcher's office — where the donkey is briefed with GPS shortlist, paper-map neighbours, and a confidence stamp before leaving |
| 16 | [Wiki Generator Deep Dive](ai-engineering/wiki-generator-deep-dive.md) | How verified Q&A pairs become per-topic markdown pages that re-enter the corpus on the next ingest | The brochure-writer — turns approved trip reports into a tourist guide for each town, ready to be re-shelved |
| 17 | [Gap Detector Deep Dive](ai-engineering/gap-detector-deep-dive.md) | HIGH / PARTIAL / GAP confidence thresholds, how gaps land in `wiki/gaps/`, how candidates close them | The honest auditor — flags trips where the donkey couldn't find a real road and parks the invented route on the supervisor's clipboard |
| 18 | [Feedback Loop Deep Dive](ai-engineering/feedback-loop-deep-dive.md) | 👍 → `verified-answers.md` → re-ingested next run; 👎 → `golden-questions.yaml` → eval set grows | The trip-debrief desk — good trips get framed and re-filed in the warehouse; bad trips get added to next month's training run |

---

## Level 4 — API

How the FastAPI server exposes the GraphRAG pipeline.

| # | Document | What you'll learn | 🫏 Donkey |
|---|----------|-------------------|-----------|
| 19 | [API Routes Overview](architecture-and-design/api-routes-explained.md) | All endpoints at a glance with request/response shapes | The stable's front door signs — every entry point, what goes in, what comes out |
| 20 | [Ingest Endpoint](architecture-and-design/api-routes/ingest-endpoint-explained.md) | `POST /ingest/run` and `GET /ingest/status` — kick off and poll the pipeline | The intake desk — drop off a fresh stack of letters, then check whether the post office has finished pre-sorting |
| 21 | [Wiki Endpoint](architecture-and-design/api-routes/wiki-endpoint-explained.md) | `/wiki/topics`, `/wiki/graph`, `/wiki/rebuild`, candidates review | The map room window — peek at the paper map, the town list, and pending brochure drafts |
| 22 | [Eval Endpoint](architecture-and-design/api-routes/eval-endpoint-explained.md) | `POST /eval/run` — trigger a scoring run from the API | The quality inspector's window — trigger a report card without touching the code |
| 23 | [Feedback Endpoint](architecture-and-design/api-routes/feedback-endpoint-explained.md) | `POST /feedback/` with 👍/👎 — closes the self-improving loop | The trip-debrief window — supervisors hand in their good/bad verdicts here |
| 24 | [Health Endpoint](architecture-and-design/api-routes/health-endpoint-explained.md) | `/health` — chunks count, topics count, provider | The stable health check — is the donkey awake, is the warehouse stocked, is the map drawn? |
| 25 | [Pydantic Models](reference/pydantic-models.md) *(coming in batch C)* | Request/response schemas for every endpoint | The parcel size rules — every request and response must fit one of these moulds |
| 26 | [API Reference](reference/api-reference.md) *(coming in batch C)* | Full API spec, status codes, error shapes | The full catalogue of doors — every endpoint, every field, every error code |

---

## Level 5 — Cloud

How the project deploys to AWS and Azure.

| # | Document | What you'll learn | 🫏 Donkey |
|---|----------|-------------------|-----------|
| 27 | [AWS Services](architecture-and-design/aws-services.md) *(coming in batch D)* | DynamoDB (vectors AND adjacency-list graph), Bedrock, IAM — why no Neptune | The AWS depot — one DynamoDB warehouse holds both backpacks AND the rolled-up paper map; Bedrock writer in the corner |
| 28 | [Azure Services](architecture-and-design/azure-services.md) *(coming in batch D)* | Cosmos DB NoSQL (graph), Azure AI Search (vectors), Azure OpenAI — free-tier choices | The Azure hub — Cosmos NoSQL pages for the map, AI Search shelves for the backpacks, GPT-4o-mini writer at the desk |
| 29 | [Infrastructure (Terraform)](architecture-and-design/infra-explained.md) *(coming in batch D)* | Terraform modules for AWS and Azure with cost guardrails | The blueprints — run one command, the whole stable appears (and another command, it disappears) |
| 30 | [Terraform Guide](setup-and-tooling/terraform-guide.md) *(coming in batch D)* | How to run `terraform apply` / `destroy` safely, especially against a personal AWS account | How to use the blueprints — build it, inspect it, tear it down without leaving meters running |
| 31 | [CI/CD](architecture-and-design/cicd-explained.md) *(coming in batch D)* | GitHub Actions: lint, test, eval-gate, deploy | The robot stable hand — won't ship a slower or less faithful donkey because the eval gate fails |

---

## Level 6 — Evaluation & Reference

How quality is measured and where to look it up.

| # | Document | What you'll learn | 🫏 Donkey |
|---|----------|-------------------|-----------|
| 32 | [Evaluation Framework Deep Dive](ai-engineering/evaluation-framework-deep-dive.md) | The 9 metrics: retrieval, context_recall, faithfulness, completeness, hallucination_rate, etc. — and the LLM-as-Judge variants | The report card factory — same 9 columns every run so improvements and regressions can't hide |
| 33 | [Golden Dataset Deep Dive](ai-engineering/golden-dataset-deep-dive.md) *(TBD — knowledge-engine grows this set from 👎 feedback rather than starting with a fixed 25)* | How `scripts/golden-questions.yaml` is seeded and how 👎 feedback grows it over time | The benchmark deliveries that grow over time — every bad trip becomes a permanent test the next donkey must pass |
| 34 | [Testing](ai-engineering/testing.md) | Unit tests, integration tests, eval tests; how the eval gate hooks into pytest | Quality gates before every shipment — unit checks per part, full-run integration, scored eval pass |
| 35 | [Monitoring](reference/monitoring.md) *(coming in batch D)* | Logs, metrics, dashboards (when added) — what to watch in production | The CCTV — every delivery time, every gap, every 👎 captured for review |

---

## Level 7 — Hands-On Labs

**Read [How to Read the Labs](hands-on-labs/how-to-read-the-labs.md) FIRST.** It explains why every lab seems to report the same metrics — without that mental model the labs feel repetitive and confusing.

Then run the labs in this order: config-tuning → Phase 1 → Phase 2 → Phase 3.

| # | Document | What you'll learn | 🫏 Donkey |
|---|----------|-------------------|-----------|
| 36 | [How to Read the Labs](hands-on-labs/how-to-read-the-labs.md) | The yardstick (6 metrics) vs the knob (one per lab); the 5-question method; suggested study order | Read this BEFORE any lab — the missing intro that makes every report card make sense |
| 37 | [Config Tuning Labs (1–19)](hands-on-labs/hands-on-labs-config-tuning.md) | Single-knob sweeps: chunk_size, top_k, temperature, system prompt, embedding model, reranker, hybrid, HNSW — same yardstick, one knob at a time | The interview answer "how would you tune this?" expressed as 19 cheap, controlled experiments |
| 38 | [Phase 1 — GraphRAG Foundation](hands-on-labs/hands-on-labs-phase-1.md) | Vector-only baseline, graph traversal, GraphRAG combined — proves 1+1 > 2 (or doesn't) | First three solo trips — GPS only, paper map only, then both together; read the first three report cards side by side |
| 39 | [Phase 2 — Missing Metrics](hands-on-labs/hands-on-labs-phase-2.md) | LLM-as-Judge faithfulness, answer correctness, completeness, hallucination_rate, cost-per-query | Add the harder report-card columns — judge faithfulness, exact correctness, completeness, honesty about invention, hay-bill per trip |
| 40 | [Phase 3 — Production](hands-on-labs/hands-on-labs-phase-3.md) | Feedback loops, graph traversal quality, multi-provider sweep, CI/CD eval gate | The full production loop — yesterday's 👎 becomes today's test, three stables race the same questions, the robot hand blocks regressions |

---

## Quick Reference

- **"I want to run it"** → doc #5 (Quick Start) or doc #4 (Full Getting Started)
- **"I want to understand GraphRAG"** → doc #2 (GraphRAG Concepts), then doc #3 (Architecture)
- **"How do I see the knowledge map?"** → doc #6 (How to Verify)
- **"How does the chat engine work internally?"** → doc #15 (Chat Engine Deep Dive — coming in batch C)
- **"How do I deploy to AWS / Azure?"** → docs #27–#31 (coming in batch D)
- **"I want to run the experiments"** → doc #36 first, then #37 → #38 → #39 → #40
- **"What metric is this score?"** → doc #32 (Evaluation Framework — coming in batch D)
