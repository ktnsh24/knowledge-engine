"""API routes — health."""
from fastapi import APIRouter, Request
from src.models import HealthStatus
from src.config import get_settings

router = APIRouter()


@router.get("/", response_model=HealthStatus)
async def health(request: Request):
    settings = get_settings()
    try:
        chunks = await request.app.state.vector_store.chunk_count()
        topics = await request.app.state.graph_store.topic_count()
        return HealthStatus(
            status="healthy",
            provider=settings.cloud_provider.value,
            vector_store_chunks=chunks,
            graph_topics=topics,
        )
    except Exception as e:
        return HealthStatus(status="degraded", error=str(e),
                            provider=settings.cloud_provider.value)
