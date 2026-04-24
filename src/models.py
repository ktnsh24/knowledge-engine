from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    LOCAL = "local"
    AWS = "aws"
    AZURE = "azure"


class ConfidenceLevel(str, Enum):
    HIGH = "high"        # retrieval_score >= 0.70, answer grounded in docs
    PARTIAL = "partial"  # retrieval_score 0.40–0.69, thin coverage
    GAP = "gap"          # retrieval_score < 0.40, likely hallucination risk


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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    quality_score: float = 0.0      # from evaluation


# ---------------------------------------------------------------------------
# Chat Models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str                        # "user" | "assistant"
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    provider: ProviderType = ProviderType.LOCAL


class AnswerSource(str, Enum):
    DOCS = "docs"              # grounded in ingested docs (HIGH confidence)
    DOCS_PARTIAL = "docs_partial"  # docs + LLM fills gaps (PARTIAL confidence)
    LLM_KNOWLEDGE = "llm_knowledge"  # no docs found — LLM answers from training data (GAP)


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
    # Gap detection fields
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    is_gap: bool = False
    gap_id: str | None = None
    gap_reason: str = ""
    gap_suggestion: str = ""
    # Answer source — tells the UI WHERE the answer came from
    answer_source: AnswerSource = AnswerSource.DOCS
    candidate_id: str | None = None  # set when answer saved as candidate for review


# ---------------------------------------------------------------------------
# Knowledge Gap Models
# ---------------------------------------------------------------------------

class KnowledgeGap(BaseModel):
    """A question that the knowledge base couldn't answer well."""
    id: str
    question: str
    confidence: ConfidenceLevel
    retrieval_score: float
    chunk_count: int
    topic_count: int
    reason: str                      # human-readable explanation
    suggestion: str                  # what to do to fix it
    status: str = "open"             # "open" | "resolved"
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None


class WikiCandidate(BaseModel):
    """
    An LLM-generated answer to a GAP question — awaiting human review.

    When confidence=GAP, the LLM answers from training knowledge (not docs).
    That answer is saved here as a candidate. The user reviews it:
      👍 promote  → writes to wiki/feedback/verified-answers.md
                  → next ingest picks it up → future answers are doc-grounded
      👎 discard  → discarded, question stays in gaps as unresolved
    """
    id: str
    question: str
    answer: str
    donkey_analogy: str
    gap_id: str                      # links back to the KnowledgeGap
    status: str = "pending"          # "pending" | "promoted" | "discarded"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    promoted_at: datetime | None = None


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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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
