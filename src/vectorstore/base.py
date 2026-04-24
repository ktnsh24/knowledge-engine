"""Vector store base interface."""
from abc import ABC, abstractmethod
from src.models import DocumentChunk


class BaseVectorStore(ABC):

    @abstractmethod
    async def upsert(self, chunks: list[DocumentChunk]) -> int:
        """Store chunks with embeddings. Returns count upserted."""
        ...

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[DocumentChunk]:
        """Semantic search — returns top_k chunks sorted by relevance."""
        ...

    @abstractmethod
    async def chunk_count(self) -> int:
        ...

    @abstractmethod
    async def delete_by_source(self, source_file: str) -> int:
        """Remove all chunks from a given source file (for re-ingestion)."""
        ...
