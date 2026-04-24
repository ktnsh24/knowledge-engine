# Getting Started

## Prerequisites

- **Python 3.11+**
- **Docker + Docker Compose**
- **Poetry** (`pip install poetry`)
- **Ollama** (for local LLM)

---

## Quick Start (Local — €0 cost)

### Step 1: Install Ollama models

```bash
ollama pull llama3.2          # LLM
ollama pull nomic-embed-text  # Embeddings
```

### Step 2: Clone and configure

```bash
cd ~/your-repos/knowledge-engine
cp .env.example .env

# Edit .env — set this to your ai-portfolio/repos path:
# SOURCE_REPOS_PATH=/home/yourname/maestro/ai-portfolio/repos
```

### Step 3: Start services

```bash
docker compose up -d neo4j chromadb
# Wait ~20 seconds for Neo4j to be ready
```

### Step 4: Install Python deps

```bash
poetry install
```

### Step 5: Start the API

```bash
poetry run start
# API running at http://localhost:8200
```

### Step 6: Ingest your docs

```bash
curl -X POST http://localhost:8200/ingest/run
# Check progress:
curl http://localhost:8200/ingest/status
```

### Step 7: Open the UI

```bash
poetry run ui
# Opens at http://localhost:8501
```

### Step 8: Ask a question

```bash
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What is GraphRAG and why does it need both a graph and vector database?"}'
```

---

## Quick Start (AWS)

> ⚠️ Always use personal account (211132580210), never Odido account.

### Step 1: Provision infrastructure

```bash
cd infra/aws
terraform init
terraform apply
```

### Step 2: Configure .env

```bash
CLOUD_PROVIDER=aws
AWS_REGION=eu-central-1
AWS_PROFILE=personal
DYNAMODB_VECTOR_TABLE=knowledge-engine-dev-vectors
DYNAMODB_GRAPH_TABLE=knowledge-engine-dev-graph
```

### Step 3: Run

Same steps 4-8 as local. The API automatically uses AWS services.

---

## Quick Start (Azure)

### Step 1: Provision infrastructure

```bash
cd infra/azure
terraform init
terraform apply
```

### Step 2: Configure .env

```bash
CLOUD_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com
AZURE_OPENAI_API_KEY=your-key
AZURE_COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com
AZURE_COSMOS_KEY=your-key
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_API_KEY=your-key
```

### Step 3: Run

Same steps 4-8 as local.

---

## Destroy Cloud Resources

```bash
# AWS
cd infra/aws && terraform destroy

# Azure
cd infra/azure && terraform destroy
```

Always destroy after use to avoid ongoing charges.
