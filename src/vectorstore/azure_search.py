"""
Azure AI Search vector store — Azure provider.

Uses Azure AI Search (formerly Cognitive Search) with vector search index.
Embeddings generated via Azure OpenAI text-embedding-3-small.

🫏 Azure AI Search is the donkey's GPS with traffic data — it knows the fastest
route to relevant content and can re-rank mid-journey as new docs are added.
"""
import json
import asyncio
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchField,
    SearchFieldDataType, VectorSearch, HnswAlgorithmConfiguration,
    VectorSearchProfile,
)
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI
from src.vectorstore.base import BaseVectorStore
from src.models import DocumentChunk
from src.config import get_settings
import structlog

logger = structlog.get_logger()

INDEX_NAME = "knowledge-engine-vectors"


class AzureSearchVectorStore(BaseVectorStore):

    def __init__(self):
        settings = get_settings()
        self._settings = settings
        credential = AzureKeyCredential(settings.azure_search_api_key)
        self.search_client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=INDEX_NAME,
            credential=credential,
        )
        self.index_client = SearchIndexClient(
            endpoint=settings.azure_search_endpoint,
            credential=credential,
        )
        self.openai_client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )

    async def _ensure_index(self):
        """Create the search index if it doesn't exist."""
        try:
            await self.index_client.get_index(INDEX_NAME)
        except Exception:
            index = SearchIndex(
                name=INDEX_NAME,
                fields=[
                    SimpleField(name="chunk_id", type=SearchFieldDataType.String, key=True),
                    SearchableField(name="text", type=SearchFieldDataType.String),
                    SimpleField(name="source_file", type=SearchFieldDataType.String, filterable=True),
                    SimpleField(name="source_repo", type=SearchFieldDataType.String, filterable=True),
                    SimpleField(name="heading", type=SearchFieldDataType.String),
                    SimpleField(name="chunk_index", type=SearchFieldDataType.Int32),
                    SearchField(
                        name="embedding",
                        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        searchable=True,
                        vector_search_dimensions=1536,
                        vector_search_profile_name="default",
                    ),
                ],
                vector_search=VectorSearch(
                    profiles=[VectorSearchProfile(name="default", algorithm_configuration_name="hnsw")],
                    algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
                ),
            )
            await self.index_client.create_index(index)
            logger.info("azure_search_index_created", index=INDEX_NAME)

    async def _embed(self, text: str) -> list[float]:
        response = await self.openai_client.embeddings.create(
            model=self._settings.azure_openai_embed_deployment,
            input=text[:8000],
        )
        return response.data[0].embedding

    async def upsert(self, chunks: list[DocumentChunk]) -> int:
        await self._ensure_index()
        documents = []
        for chunk in chunks:
            embedding = await self._embed(chunk.text)
            documents.append({
                "chunk_id": chunk.id,
                "text": chunk.text,
                "embedding": embedding,
                "source_file": chunk.source_file,
                "source_repo": chunk.source_repo,
                "heading": chunk.heading,
                "chunk_index": chunk.chunk_index,
            })
        await self.search_client.upload_documents(documents)
        return len(documents)

    async def search(self, query: str, top_k: int = 5) -> list[DocumentChunk]:
        await self._ensure_index()
        query_embedding = await self._embed(query)
        from azure.search.documents.models import VectorizedQuery
        vector_query = VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=top_k,
            fields="embedding",
        )
        results = await self.search_client.search(
            search_text=None,
            vector_queries=[vector_query],
            top=top_k,
        )
        chunks = []
        async for result in results:
            chunks.append(DocumentChunk(
                id=result["chunk_id"],
                text=result["text"],
                source_file=result.get("source_file", ""),
                source_repo=result.get("source_repo", ""),
                heading=result.get("heading", ""),
                chunk_index=result.get("chunk_index", 0),
                score=result.get("@search.score", 0.0),
            ))
        return chunks

    async def chunk_count(self) -> int:
        try:
            result = await self.search_client.get_document_count()
            return result
        except Exception:
            return 0

    async def delete_by_source(self, source_file: str) -> int:
        results = await self.search_client.search(
            search_text="*",
            filter=f"source_file eq '{source_file}'",
            select=["chunk_id"],
        )
        ids = [r["chunk_id"] async for r in results]
        if ids:
            await self.search_client.delete_documents([{"chunk_id": i} for i in ids])
        return len(ids)
