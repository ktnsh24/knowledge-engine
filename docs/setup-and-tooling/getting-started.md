# Getting Started — Step by Step

> **What is this project?** A self-improving GraphRAG knowledge base that reads all your AI portfolio docs, builds a connected topic map, and gets smarter every time you ask a question.

## Table of Contents

- [What you need before starting](#what-you-need-before-starting)
- [Step 1 — Install Python 3.11+](#step-1--install-python-311)
- [Step 2 — Install Poetry](#step-2--install-poetry)
- [Step 3 — Clone the repository](#step-3--clone-the-repository)
- [Step 4 — Install dependencies](#step-4--install-dependencies)
- [Step 5 — Configure environment variables](#step-5--configure-environment-variables)
- [Step 6 — Set up Local (Ollama + Neo4j + ChromaDB) — €0](#step-6--set-up-local-ollama--neo4j--chromadb---0)
- [Step 7 — Ingest your docs](#step-7--ingest-your-docs)
- [Step 8 — Ask your first question](#step-8--ask-your-first-question)
- [Step 9 — Open the UI](#step-9--open-the-ui)
- [Step 10 — Run the evaluation suite](#step-10--run-the-evaluation-suite)
- [Step 11 — Run all labs automatically](#step-11--run-all-labs-automatically)
- [Step 12 — Set up AWS](#step-12--set-up-aws)
- [Step 13 — Set up Azure](#step-13--set-up-azure)
- [Step 14 — All API endpoints reference](#step-14--all-api-endpoints-reference)
- [Troubleshooting](#troubleshooting)

---

## What you need before starting

| Tool | Version | Why you need it |
|------|---------|-----------------|
| **Python** | 3.11+ | The app is written in Python |
| **Poetry** | 1.8+ | Package manager (manages dependencies + virtual environment) |
| **Docker + Compose** | 24+ | Runs Neo4j and ChromaDB locally |
| **Ollama** | latest | Local LLM + embeddings — free, no API key |
| **Git** | 2.40+ | Version control |
| **AWS CLI** | 2.x | Only needed for AWS provider |
| **Azure CLI** | 2.x | Only needed for Azure provider |
| **Terraform** | 1.5+ | Only needed to provision cloud infra |

### Check what is already installed

```bash
python3 --version      # Need 3.11+
poetry --version       # Need 1.8+
docker --version       # Need 24+
ollama --version       # Need latest
git --version
aws --version          # Only for AWS
az --version           # Only for Azure
terraform --version    # Only for cloud infra
```

---

## Step 1 — Install Python 3.11+

### On Ubuntu / WSL

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

python3.11 --version
# → Python 3.11.x
```

### On macOS

```bash
brew install python@3.11
python3.11 --version
```

---

## Step 2 — Install Poetry

Poetry is a **Python package manager**. It replaces `pip` + `requirements.txt` + `venv` with a single tool.

```bash
# Install
curl -sSL https://install.python-poetry.org | python3 -

# Add to PATH (add this to your ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"

# Verify
poetry --version
# → Poetry (version 1.8.x)

# Tell Poetry to create .venv/ inside the project folder (VS Code auto-detects it)
poetry config virtualenvs.in-project true
```

---

## Step 3 — Clone the repository

```bash
cd ~/projects/ai-portfolio/repos   # or wherever you keep your projects
git clone <your-repo-url> knowledge-engine
cd knowledge-engine
```

---

## Step 4 — Install dependencies

```bash
poetry install
```

What this does:
1. Reads `pyproject.toml` (your dependency list)
2. Resolves compatible versions
3. Creates `poetry.lock` (locks exact versions)
4. Installs everything into `.venv/`

### Activate the virtual environment

```bash
source .venv/bin/activate
# You'll see (knowledge-engine) at the start of your terminal prompt
```

---

## Step 5 — Configure environment variables

```bash
cp .env.example .env
code .env   # VS Code — or nano .env
```

### Minimum for Local (no cloud, no API keys, €0)

```bash
CLOUD_PROVIDER=local
APP_ENV=dev
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
CHROMA_HOST=localhost
CHROMA_PORT=8000

# IMPORTANT: path to your ai-portfolio/repos folder
# The ingestor scans this for .md and .py files
SOURCE_REPOS_PATH=/home/yourname/projects/ai-portfolio/repos
```

### Minimum for AWS

```bash
CLOUD_PROVIDER=aws
APP_ENV=dev
AWS_REGION=eu-central-1
AWS_PROFILE=personal                          # your personal AWS profile
DYNAMODB_VECTOR_TABLE=knowledge-engine-dev-vectors
DYNAMODB_GRAPH_TABLE=knowledge-engine-dev-graph
AWS_BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
SOURCE_REPOS_PATH=/home/yourname/projects/ai-portfolio/repos
```

### Minimum for Azure

```bash
CLOUD_PROVIDER=azure
APP_ENV=dev
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com
AZURE_COSMOS_KEY=your-key
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_API_KEY=your-key
SOURCE_REPOS_PATH=/home/yourname/projects/ai-portfolio/repos
```

---

## Step 6 — Set up Local (Ollama + Neo4j + ChromaDB) — €0

This is the recommended starting point. No cloud credentials, no API keys, zero cost.

### 6a. Install Ollama

```bash
# Linux / WSL
curl -fsSL https://ollama.com/install.sh | sh

ollama --version
```

### 6b. Pull the required models

```bash
# LLM (~2 GB)
ollama pull llama3.2

# Embedding model (~275 MB)
ollama pull nomic-embed-text

# Verify both are available
ollama list
```

### 6c. Start Neo4j and ChromaDB via Docker Compose

```bash
# Start only the local stores (not the full API yet)
docker compose up -d neo4j chromadb

# Wait ~20 seconds for Neo4j to initialise, then check
docker compose ps
# neo4j and chromadb should show "Up"
```

### 6d. Verify Neo4j is ready

```bash
curl http://localhost:7474
# Should return Neo4j browser HTML
```

### 6e. Start the API

```bash
poetry run start
# → Uvicorn running on http://localhost:8200
```

### 6f. Verify the API is healthy

```bash
curl http://localhost:8200/health
# → {"status":"ok","provider":"local","chunks":0,"topics":0}
```

**Chunks: 0, Topics: 0** is correct — you haven't ingested yet.

---

## Step 7 — Ingest your docs

The ingestor scans `SOURCE_REPOS_PATH`, chunks all `.md` and `.py` files, builds embeddings, and extracts topics + relationships into the graph.

```bash
# Trigger ingestion (runs in background)
curl -X POST http://localhost:8200/ingest/run
# → {"status":"started","message":"Ingestion running in background"}

# Watch progress
curl http://localhost:8200/ingest/status
# → {"chunks": 142, "topics": 38}
# Keep polling until chunks stop growing
```

### What the ingestor does internally

```
For each .md / .py file in SOURCE_REPOS_PATH:
  1. Split into ~500-token chunks
  2. Embed each chunk → store in ChromaDB / DynamoDB / Azure AI Search
  3. Ask LLM: "What topics and relationships exist in this text?"
  4. Store topics as nodes in Neo4j / DynamoDB / Cosmos DB
  5. Store relationships as edges (RELATED_TO, EXTENDS, USED_BY...)
```

After ingestion you should see topics growing. For the full ai-portfolio (6 repos) expect:
- **~150–300 chunks**
- **~40–80 topics**

---

## Step 8 — Ask your first question

```bash
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What is GraphRAG and why does it need both a graph and vector database?"}'
```

You should get a response like:

```json
{
  "answer": "GraphRAG combines vector search with graph traversal... 🫏 Think of it like a donkey...",
  "donkey_analogy": "The LLM is the donkey. The graph is the road...",
  "sources": ["rag-chatbot/docs/architecture.md", "knowledge-engine/docs/architecture.md"],
  "topics": ["GraphRAG", "Vector Search", "Graph Database"],
  "latency_ms": 843
}
```

> ⚠️ Every answer includes a `donkey_analogy`. This is by design — it's baked into the system prompt. If you don't see 🫏, something is wrong with the LLM call.

### Give feedback on the answer

```bash
# 👍 Good answer — saves Q&A to wiki/feedback/verified-answers.md
curl -X POST http://localhost:8200/feedback/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What is GraphRAG?", "answer": "...", "signal": "positive"}'

# 👎 Bad answer — appends question to scripts/golden-questions.yaml (eval set grows)
curl -X POST http://localhost:8200/feedback/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What is GraphRAG?", "answer": "...", "signal": "negative"}'
```

**This is how the knowledge base improves over time** — see [how-to-verify.md](../how-to-verify.md) for details.

---

## Step 9 — Open the UI

```bash
poetry run ui
# → Opens Streamlit at http://localhost:8501
```

The UI gives you:
- Chat interface with 👍/👎 buttons
- Topic sidebar (live list of all graph topics)
- Wiki Rebuild button (regenerates wiki pages from feedback)

---

## Step 10 — Run the evaluation suite

The evaluator tests all **9 metrics** against the golden question set in `scripts/golden-questions.yaml`.

```bash
# Run evaluation via API
curl -X POST http://localhost:8200/eval/run
```

Response includes all 9 metrics:

```json
{
  "avg_retrieval": 0.71,
  "avg_context_precision": 0.68,
  "avg_context_recall": 0.65,
  "avg_faithfulness": 0.82,
  "avg_answer_relevance": 0.74,
  "avg_answer_correctness": 0.60,
  "avg_completeness": 0.70,
  "hallucination_rate_pct": 9.1,
  "avg_cost_per_query_usd": 0.0,
  "overall_pass_rate": 0.72,
  "comparison_with_rag_chatbot": {
    "context_recall": "NEW — rag-chatbot only had Precision",
    "faithfulness": "UPGRADED to LLM-as-Judge (rag-chatbot used keyword match)",
    ...
  }
}
```

**Pass threshold:** `overall_pass_rate >= 0.65` → passes CI gate.

---

## Step 11 — Run all labs automatically

```bash
# Dry run — no API needed, tests all 27 experiments
python3 scripts/run_all_labs.py --dry-run

# Live run against local stack
python3 scripts/run_all_labs.py --env local

# Specific phases only
python3 scripts/run_all_labs.py --env local --phases 1,2

# Output: scripts/lab-results/local/lab-results-report.md
```

The runner covers all 3 phases (27 experiments):
- **Phase 1** — GraphRAG foundation (retrieval, graph traversal, baseline eval)
- **Phase 2** — 5 missing metrics from rag-chatbot (faithfulness, correctness, completeness, hallucination rate, cost)
- **Phase 3** — Production (feedback loops, multi-cloud provider check, CI/CD gate)

---

## Step 12 — Set up AWS

> ⚠️ **Always use personal AWS account (<YOUR_AWS_ACCOUNT_ID>)**. Never work account. Terraform has a safety guard: `allowed_account_ids = ["<YOUR_AWS_ACCOUNT_ID>"]`.

### 12a. Verify you're on the right account

```bash
aws sts get-caller-identity --profile personal
# "Account": "<YOUR_AWS_ACCOUNT_ID>"  ← must see this
```

### 12b. Provision infrastructure

```bash
cd infra/aws
terraform init
terraform apply
```

Creates:
- DynamoDB table `knowledge-engine-dev-vectors` (vector store)
- DynamoDB table `knowledge-engine-dev-graph` (graph adjacency list)
- S3 bucket for wiki output
- Budget alert at $10/month

**Estimated idle cost: €0** (DynamoDB PAY_PER_REQUEST — you pay per request, nothing when idle)

### 12c. Update .env

```bash
CLOUD_PROVIDER=aws
```

### 12d. Run labs on AWS

```bash
python3 scripts/run_all_labs.py --env aws
```

### 12e. Destroy when done

```bash
cd infra/aws
terraform destroy
```

---

## Step 13 — Set up Azure

### 13a. Login

```bash
az login
az account show   # verify correct subscription
```

### 13b. Provision infrastructure

```bash
cd infra/azure
terraform init
terraform apply
```

Creates (all free tier):
- Azure OpenAI (GPT-4o-mini + text-embedding-3-small)
- Cosmos DB NoSQL (400 RU/s free tier)
- Azure AI Search (free tier — 3 indexes, 50 MB)
- Storage account for wiki output

**Estimated idle cost: €0** (free tier)

### 13c. Get credentials from Terraform output

```bash
terraform output -json
# Copy endpoint URLs and keys into your .env
```

### 13d. Update .env

```bash
CLOUD_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=<from terraform output>
...
```

### 13e. Run labs on Azure

```bash
python3 scripts/run_all_labs.py --env azure
```

### 13f. Destroy when done

```bash
cd infra/azure
terraform destroy
```

---

## Step 14 — All API endpoints reference

| Method | Endpoint | What it does |
|--------|----------|--------------|
| `GET` | `/health` | Health check — shows provider, chunk count, topic count |
| `POST` | `/ingest/run` | Trigger doc ingestion (background task) |
| `GET` | `/ingest/status` | Ingestion progress — chunks and topics so far |
| `POST` | `/chat/` | Ask a question — returns answer + donkey analogy + sources + topics |
| `POST` | `/feedback/` | Submit 👍/👎 feedback on an answer |
| `GET` | `/wiki/topics` | List all topics in the knowledge graph |
| `GET` | `/wiki/graph` | Full knowledge graph (topics + relationships as JSON) |
| `POST` | `/wiki/rebuild` | Regenerate wiki pages from verified answers |
| `POST` | `/eval/run` | Run full evaluation suite — returns all 9 metrics |

### Interactive API docs

When the API is running, visit:
- **Swagger UI:** http://localhost:8200/docs
- **ReDoc:** http://localhost:8200/redoc

---

## Troubleshooting

### "Connection refused" on port 8200

```bash
# Check the API is running
poetry run start

# Check Neo4j and ChromaDB are up
docker compose ps
```

### "Neo4j not ready" on startup

```bash
# Wait ~30 seconds after docker compose up
docker compose logs neo4j | tail -20
# Look for: "Started" or "remote interface available"
```

### Chunks stay at 0 after ingest

```bash
# Check SOURCE_REPOS_PATH is set correctly
grep SOURCE_REPOS_PATH .env

# Check the path exists and has .md files
ls $SOURCE_REPOS_PATH
```

### Ollama "model not found"

```bash
ollama list
# If llama3.2 or nomic-embed-text missing:
ollama pull llama3.2
ollama pull nomic-embed-text
```

### AWS "access denied"

```bash
# Verify you're using personal account
aws sts get-caller-identity --profile personal
# Must show Account: <YOUR_AWS_ACCOUNT_ID>
```

### Answers missing 🫏 donkey analogy

The donkey analogy is in `src/llm/base.py` → `DONKEY_SYSTEM_PROMPT`. Every LLM call includes it. If missing:
```bash
# Check which LLM provider is active
curl http://localhost:8200/health
# Verify CLOUD_PROVIDER in .env matches what's running
```
