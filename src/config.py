from enum import Enum
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class CloudProvider(str, Enum):
    LOCAL = "local"
    AWS = "aws"
    AZURE = "azure"


class AppEnv(str, Enum):
    DEV = "dev"
    STG = "stg"
    PRD = "prd"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    cloud_provider: CloudProvider = CloudProvider.LOCAL
    app_env: AppEnv = AppEnv.DEV
    api_port: int = 8200
    api_keys_enabled: bool = False
    master_api_key: str = "dev-key"

    # Donkey analogy — always on
    donkey_analogy_enabled: bool = True

    # --- LLM ---
    # Local
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"

    # AWS
    aws_region: str = "eu-central-1"
    aws_bedrock_llm_model: str = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    aws_bedrock_embed_model: str = "amazon.titan-embed-text-v2:0"

    # Azure
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_llm_deployment: str = "gpt-4o"
    azure_openai_embed_deployment: str = "text-embedding-3-small"
    azure_openai_api_version: str = "2024-02-01"

    # --- Vector Store ---
    chroma_persist_path: str = "./data/chroma"
    dynamodb_vectors_table: str = "knowledge-engine-vectors"
    azure_search_endpoint: str = ""
    azure_search_api_key: str = ""
    azure_search_index: str = "knowledge-engine"

    # --- Graph Store ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "knowledge123"
    dynamodb_graph_table: str = "knowledge-engine-graph"
    cosmos_db_endpoint: str = ""
    cosmos_db_key: str = ""
    cosmos_db_database: str = "knowledge-engine"
    cosmos_db_graph_container: str = "graph"

    # --- Source Repos ---
    source_repos_path: str = "../"
    source_repos: str = "rag-chatbot,ai-gateway,ai-agent,ai-multi-agent,mcp-server,ai-engineering-field-guide"
    include_patterns: str = "**/*.md,**/*.txt"
    exclude_patterns: str = "**/node_modules/**,**/.venv/**,**/site/**,**/__pycache__/**"

    # --- Wiki ---
    wiki_output_path: str = "./wiki-output"
    wiki_rebuild_on_change: bool = True

    # --- Evaluation ---
    eval_enabled: bool = True
    eval_golden_questions_path: str = "./scripts/golden-questions.yaml"

    # --- Config-tuning labs (Tier 1–5) ---
    # Tier 1 — Essential
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 100
    rag_top_k: int = 5
    llm_temperature: float = 0.1
    system_prompt_mode: str = "strict"  # strict | lax
    embedding_dimensions: int = 1024

    # Tier 2 — Quality
    reranker_enabled: bool = False
    reranker_model: str = "bge-reranker-base"
    hybrid_search_enabled: bool = False
    hybrid_alpha: float = 0.5
    llm_max_tokens: int = 2048
    distance_metric: str = "cosine"

    # Tier 3 — HNSW vector-store tuning
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200
    hnsw_ef_search: int = 64

    # Tier 4 — Retrieval strategy
    query_rewriting_enabled: bool = False
    multi_query_count: int = 1
    metadata_filters: str = ""
    chunk_strategy: str = "fixed"

    # Tier 5 — Evaluation knobs
    eval_mode: str = "rule_based"  # rule_based | llm_judge
    eval_faithfulness_threshold: float = 0.5
    eval_keyword_overlap_pct: float = 0.5

    @property
    def source_repo_list(self) -> list[str]:
        return [r.strip() for r in self.source_repos.split(",")]

    @property
    def include_pattern_list(self) -> list[str]:
        return [p.strip() for p in self.include_patterns.split(",")]

    @property
    def exclude_pattern_list(self) -> list[str]:
        return [p.strip() for p in self.exclude_patterns.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
