"""FastAPI application factory with lifespan management."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from src.config import get_settings
from src.llm.factory import create_llm
from src.vectorstore.factory import create_vector_store
from src.graphstore.factory import create_graph_store
from src.chat.engine import ChatEngine
from src.chat.feedback import FeedbackProcessor
from src.wiki.generator import WikiGenerator
from src.routes import chat, wiki, ingest, health, feedback, eval as eval_route

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise all services on startup, clean up on shutdown."""
    settings = get_settings()
    logger.info("knowledge_engine_starting", provider=settings.cloud_provider.value)

    # Initialise stores and services
    llm = create_llm()
    vector_store = create_vector_store()
    graph_store = create_graph_store()
    chat_engine = ChatEngine(llm, vector_store, graph_store)
    wiki_gen = WikiGenerator(llm, vector_store, graph_store)
    feedback_proc = FeedbackProcessor()

    # Make available to routes via app state
    app.state.llm = llm
    app.state.vector_store = vector_store
    app.state.graph_store = graph_store
    app.state.chat_engine = chat_engine
    app.state.wiki_gen = wiki_gen
    app.state.feedback_proc = feedback_proc

    chunk_count = await vector_store.chunk_count()
    topic_count = await graph_store.topic_count()
    logger.info("knowledge_engine_ready", chunks=chunk_count, topics=topic_count,
                provider=settings.cloud_provider.value)

    yield

    # Cleanup
    if hasattr(graph_store, "close"):
        await graph_store.close()
    logger.info("knowledge_engine_stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Knowledge Engine",
        description="Self-improving GraphRAG knowledge base — Local | AWS | Azure",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(chat.router, prefix="/chat", tags=["chat"])
    app.include_router(ingest.router, prefix="/ingest", tags=["ingestion"])
    app.include_router(wiki.router, prefix="/wiki", tags=["wiki"])
    app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
    app.include_router(eval_route.router, prefix="/eval", tags=["evaluation"])

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("src.main:app", host="0.0.0.0", port=8200, reload=True)
