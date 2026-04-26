"""
DynamoDB vector store — AWS provider.

Stores embeddings as serialized floats in DynamoDB items.
Uses cosine similarity computed in Python (no OpenSearch needed = €0 cost).

🚚 DynamoDB is a parcel — not as fast as a dedicated vector DB,
but the courier can carry it without renting a truck.
For our scale (<100K chunks), Python cosine search is fast enough.
"""
import json
import math
import boto3
import asyncio
from src.vectorstore.base import BaseVectorStore
from src.models import DocumentChunk
from src.config import get_settings
import structlog

logger = structlog.get_logger()


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _normalize_scores(scores: list[float]) -> list[float]:
    """Min-max normalize so best match = 1.0 (fixes Titan low-score issue)."""
    if not scores:
        return scores
    mn, mx = min(scores), max(scores)
    if mx == mn:
        return [1.0] * len(scores)
    return [(s - mn) / (mx - mn) for s in scores]


class DynamoDBVectorStore(BaseVectorStore):

    def __init__(self):
        settings = get_settings()
        self.dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
        self.table = self.dynamodb.Table(settings.dynamodb_vector_table)
        self._embed_client = None
        self._settings = settings

    def _get_embedder(self):
        """Lazy-init Bedrock embeddings client."""
        if self._embed_client is None:
            import boto3 as b3
            self._embed_client = b3.client(
                "bedrock-runtime", region_name=self._settings.aws_region
            )
        return self._embed_client

    def _embed_text(self, text: str) -> list[float]:
        client = self._get_embedder()
        body = json.dumps({"inputText": text[:8000]})
        response = client.invoke_model(
            modelId=self._settings.aws_bedrock_embed_model,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        return result["embedding"]

    async def upsert(self, chunks: list[DocumentChunk]) -> int:
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_upsert, chunks
        )

    def _sync_upsert(self, chunks: list[DocumentChunk]) -> int:
        with self.table.batch_writer() as batch:
            for chunk in chunks:
                embedding = self._embed_text(chunk.text)
                batch.put_item(Item={
                    "chunk_id": chunk.id,
                    "text": chunk.text,
                    "embedding": json.dumps(embedding),
                    "source_file": chunk.source_file,
                    "source_repo": chunk.source_repo,
                    "heading": chunk.heading,
                    "chunk_index": chunk.chunk_index,
                })
        return len(chunks)

    async def search(self, query: str, top_k: int = 5) -> list[DocumentChunk]:
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_search, query, top_k
        )

    def _sync_search(self, query: str, top_k: int) -> list[DocumentChunk]:
        query_embedding = self._embed_text(query)

        # Full table scan + in-memory cosine (suitable for <100K chunks)
        response = self.table.scan()
        items = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = self.table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))

        if not items:
            return []

        # Compute raw cosine scores
        raw_scores = [_cosine(query_embedding, json.loads(item["embedding"])) for item in items]

        # Normalize (fixes Titan low-score problem from rag-chatbot lessons)
        normalized = _normalize_scores(raw_scores)

        # Sort and take top_k
        ranked = sorted(zip(normalized, items), key=lambda x: x[0], reverse=True)
        safe_k = min(top_k, len(ranked))

        chunks = []
        for score, item in ranked[:safe_k]:
            chunk = DocumentChunk(
                id=item["chunk_id"],
                text=item["text"],
                source_file=item.get("source_file", ""),
                source_repo=item.get("source_repo", ""),
                heading=item.get("heading", ""),
                chunk_index=int(item.get("chunk_index", 0)),
                score=score,
            )
            chunks.append(chunk)
        return chunks

    async def chunk_count(self) -> int:
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.table.scan(Select="COUNT")
        )
        return response.get("Count", 0)

    async def delete_by_source(self, source_file: str) -> int:
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.table.scan()
        )
        items = [i for i in response.get("Items", []) if i.get("source_file") == source_file]
        with self.table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"chunk_id": item["chunk_id"]})
        return len(items)
