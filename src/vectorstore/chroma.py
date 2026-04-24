"""
ChromaDB vector store — local provider.
Zero cost, runs in Docker alongside Neo4j.
"""
import chromadb
from chromadb.utils import embedding_functions
from src.vectorstore.base import BaseVectorStore
from src.models import DocumentChunk
from src.config import get_settings


class ChromaVectorStore(BaseVectorStore):

    def __init__(self):
        settings = get_settings()
        self.client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
        ef = embedding_functions.OllamaEmbeddingFunction(
            url=f"{settings.ollama_base_url}/api/embeddings",
            model_name=settings.ollama_embed_model,
        )
        self.collection = self.client.get_or_create_collection(
            name="knowledge_engine",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

    async def upsert(self, chunks: list[DocumentChunk]) -> int:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_upsert, chunks
        )

    def _sync_upsert(self, chunks: list[DocumentChunk]) -> int:
        if not chunks:
            return 0
        self.collection.upsert(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[{
                "source_file": c.source_file,
                "source_repo": c.source_repo,
                "heading": c.heading,
                "chunk_index": c.chunk_index,
            } for c in chunks],
        )
        return len(chunks)

    async def search(self, query: str, top_k: int = 5) -> list[DocumentChunk]:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_search, query, top_k
        )

    def _sync_search(self, query: str, top_k: int) -> list[DocumentChunk]:
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        chunks = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            score = max(0.0, 1.0 - distance)  # cosine distance → similarity
            chunk = DocumentChunk(
                id=results["ids"][0][i],
                text=doc,
                source_file=meta.get("source_file", ""),
                source_repo=meta.get("source_repo", ""),
                heading=meta.get("heading", ""),
                chunk_index=meta.get("chunk_index", 0),
                score=score,
            )
            chunks.append(chunk)
        return chunks

    async def chunk_count(self) -> int:
        return self.collection.count()

    async def delete_by_source(self, source_file: str) -> int:
        results = self.collection.get(where={"source_file": source_file})
        ids = results["ids"]
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)
