# Getting Started

> **Full step-by-step guide:** [docs/setup-and-tooling/getting-started.md](setup-and-tooling/getting-started.md)
>
> **Reading order:** [docs/reading-order.md](reading-order.md)
>
> **How to verify it's working:** [docs/how-to-verify.md](how-to-verify.md)

🚚 **Courier lens:** this is the express loading dock — gear already installed, fill the GPS warehouse and paper map in seven commands, send the courier on its first delivery in under a minute.

---

## 30-Second Quick Start (Local — €0)

```bash
# 1. Pull Ollama models
ollama pull llama3.2
ollama pull nomic-embed-text

# 2. Clone and configure
cp .env.example .env
# Edit .env: set SOURCE_REPOS_PATH=/home/yourname/projects/ai-portfolio/repos

# 3. Start graph + vector stores
docker compose up -d neo4j chromadb

# 4. Install deps and start API
poetry install
poetry run start        # → http://localhost:8200

# 5. Ingest docs
curl -X POST http://localhost:8200/ingest/run

# 6. Ask a question
curl -X POST http://localhost:8200/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "What is GraphRAG?"}'

# 7. See the knowledge map
curl http://localhost:8200/wiki/graph
```

For full instructions with AWS, Azure, troubleshooting, and verification → see [setup-and-tooling/getting-started.md](setup-and-tooling/getting-started.md)
