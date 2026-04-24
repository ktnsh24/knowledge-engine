from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    LOCAL = "local"
    AWS = "aws"
    AZURE = "azure"


# ---------------------------------------------------------------------------
# Knowledge Graph Models
# ---------------------------------------------------------------------------

class Topic(BaseModel):
    """A single topic node in the knowledge graph."""
    id: str                          # e.g. "rag-pipeline"
    name: str                        # e.g. "RAG Pipeline"
    description: str = ""
    source_repos: list[str] = []     # which repos mention this topic
    source_files: list[str] = []     # which files mention this topic
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Relationship(BaseModel):
    """A directed edge between two topics in the knowledge graph."""
    source_id: str                   # e.g. "embeddings"
    target_id: str                   # e.g. "vector-store"
    relation_type: str               # e.g. "USED_BY", "STORED_IN", "REQUIRED_BY"
    weight: float = 1.0              # strength of relationship
    evidence: str = ""               # sentence that implied this relationship


class KnowledgeGraph(BaseModel):
    """Full graph: all topics + all relationships."""
    topics: list[Topic] = []
    relationships: list[Relationship] = []


# ---------------------------------------------------------------------------
# Document / Chunk Models
# ---------------------------------------------------------------------------

class DocumentChunk(BaseModel):
    """A chunk of a source markdown document with its embedding."""
    id: str
    text: str
    source_file: str
    source_repo: str
    heading: str = ""                # nearest heading above this chunk
    chunk_index: int = 0
    embedding: list[float] = []
    topic_ids: list[str] = []        # topics this chunk belongs to


# ---------------------------------------------------------------------------
# Wiki Models
# ---------------------------------------------------------------------------

class WikiPage(BaseModel):
    """A generated wiki page for a topic."""
    topic_id: str
    title: str
    content: str                     # full markdown content
    donkey_analogy: str              # the 🫏 analogy for this topic
    sources: list[str] = []         # source files used
    connected_topics: list[str] = [] # related topic IDs
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1
    quality_score: float = 0.0      # from evaluation


# ---------------------------------------------------------------------------
# Chat Models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str                        # "user" | "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    provider: ProviderType = ProviderType.LOCAL


class ChatResponse(BaseModel):
    answer: str
    donkey_analogy: str              # always included
    sources: list[str] = []         # source files used
    topics: list[str] = []          # topics retrieved from graph
    retrieval_score: float = 0.0
    faithfulness_score: float = 0.0
    latency_ms: int = 0
    provider: ProviderType = ProviderType.LOCAL
    session_id: str = "default"


# ---------------------------------------------------------------------------
# Feedback Models
# ---------------------------------------------------------------------------

class FeedbackSignal(BaseModel):
    """User feedback on a chat response — drives wiki improvement."""
    session_id: str
    question: str
    answer: str
    thumbs_up: bool                  # True = good, False = bad
    correction: str = ""             # optional user correction
    missing_info: str = ""           # what was missing from the answer
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Ingestion Models
# ---------------------------------------------------------------------------

class IngestionResult(BaseModel):
    repo: str
    files_found: int = 0
    chunks_created: int = 0
    topics_extracted: int = 0
    relationships_extracted: int = 0
    errors: list[str] = []
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# Health / Status
# ---------------------------------------------------------------------------

class HealthStatus(BaseModel):
    status: str = "ok"
    provider: ProviderType
    vector_store: str
    graph_store: str
    llm: str
    wiki_pages: int = 0
    total_chunks: int = 0
    total_topics: int = 0
