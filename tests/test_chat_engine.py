"""Tests for chat engine and feedback processor."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.chat.engine import ChatEngine
from src.models import ChatRequest, DocumentChunk, Topic


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.complete.return_value = (
        "🚚 The LLM is the courier carrying your question.\n\n"
        "GraphRAG combines vector search with graph traversal for richer answers."
    )
    return llm


@pytest.fixture
def mock_vector_store():
    vs = AsyncMock()
    vs.search.return_value = [
        DocumentChunk(
            id="chunk-001",
            text="RAG combines retrieval with generation for grounded answers.",
            source_file="docs/rag.md",
            source_repo="rag-chatbot",
            heading="RAG Overview",
            chunk_index=0,
            topic_ids=["rag", "retrieval"],
            score=0.92,
        )
    ]
    return vs


@pytest.fixture
def mock_graph_store():
    gs = AsyncMock()
    gs.get_connected_topics.return_value = [
        Topic(id="embeddings", name="Embeddings", description="Vector representations"),
        Topic(id="vector-search", name="Vector Search", description="Semantic search"),
    ]
    return gs


@pytest.fixture
def chat_engine(mock_llm, mock_vector_store, mock_graph_store):
    return ChatEngine(mock_llm, mock_vector_store, mock_graph_store)


def test_chat_engine_returns_response(chat_engine):
    request = ChatRequest(question="What is GraphRAG?")
    response = asyncio.run(chat_engine.answer(request))
    assert response.answer
    assert response.latency_ms >= 0
    assert isinstance(response.sources, list)


def test_chat_engine_extracts_courier_analogy(chat_engine):
    request = ChatRequest(question="Explain embeddings")
    response = asyncio.run(chat_engine.answer(request))
    assert "🚚" in response.courier_analogy


def test_chat_engine_calls_vector_store(chat_engine, mock_vector_store):
    request = ChatRequest(question="How does RAG work?")
    asyncio.run(chat_engine.answer(request))
    mock_vector_store.search.assert_called_once_with("How does RAG work?", top_k=5)


def test_chat_engine_includes_sources(chat_engine):
    request = ChatRequest(question="What is RAG?")
    response = asyncio.run(chat_engine.answer(request))
    assert "docs/rag.md" in response.sources


def test_chat_engine_expands_graph(chat_engine, mock_graph_store):
    request = ChatRequest(question="What is RAG?")
    asyncio.run(chat_engine.answer(request))
    # Graph store should be called for topic expansion
    mock_graph_store.get_connected_topics.assert_called()
