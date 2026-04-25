"""API routes — ingestion."""
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from src.ingestion.scanner import scan_repos, chunk_document
from src.ingestion.graph_extractor import extract_and_store
from src.config import get_settings
import structlog

router = APIRouter()
logger = structlog.get_logger()


@router.post("/run")
async def run_ingestion(request: Request, background_tasks: BackgroundTasks):
    """Scan all repos, chunk docs, embed, extract graph."""
    background_tasks.add_task(
        _ingest_all,
        request.app.state.vector_store,
        request.app.state.graph_store,
        request.app.state.llm,
    )
    return {"status": "started", "message": "Ingestion running in background"}


async def _ingest_all(vector_store, graph_store, llm):
    settings = get_settings()
    files = scan_repos()
    logger.info("ingestion_started", files=len(files),
                chunk_size=settings.rag_chunk_size,
                chunk_overlap=settings.rag_chunk_overlap,
                chunk_strategy=settings.chunk_strategy)
    total_chunks = 0
    for path in files:
        chunks = chunk_document(
            path,
            chunk_size=settings.rag_chunk_size,
            overlap=settings.rag_chunk_overlap,
        )
        if chunks:
            n = await vector_store.upsert(chunks)
            total_chunks += n
            await extract_and_store(path.read_text(), graph_store, llm)
    logger.info("ingestion_complete", files=len(files), chunks=total_chunks)


@router.get("/status")
async def ingestion_status(request: Request):
    chunks = await request.app.state.vector_store.chunk_count()
    topics = await request.app.state.graph_store.topic_count()
    return {"chunks": chunks, "topics": topics}
