"""Tests for document ingestion — scanner and chunker."""
import pytest
from pathlib import Path
from unittest.mock import patch
from src.ingestion.scanner import chunk_document


@pytest.fixture
def sample_md(tmp_path):
    """Create a temporary markdown file for testing."""
    content = """# RAG Overview

RAG stands for Retrieval Augmented Generation. It combines retrieval with generation.

## How It Works

The system first embeds the query, then searches for relevant chunks,
then passes those chunks to the LLM as context.

## Why RAG

RAG is preferred over fine-tuning because it is cheaper, faster to update,
and the knowledge base can be swapped without retraining the model.
"""
    f = tmp_path / "rag-overview.md"
    f.write_text(content)
    return f


def test_chunk_document_returns_chunks(sample_md):
    chunks = chunk_document(sample_md, chunk_size=50, overlap=10)
    assert len(chunks) > 0


def test_chunk_document_sets_metadata(sample_md):
    chunks = chunk_document(sample_md, chunk_size=50, overlap=10)
    for chunk in chunks:
        assert chunk.id  # has an ID
        assert chunk.text  # has content
        assert chunk.source_file == str(sample_md)
        assert chunk.chunk_index >= 0


def test_chunk_document_empty_file(tmp_path):
    f = tmp_path / "empty.md"
    f.write_text("")
    chunks = chunk_document(f)
    assert chunks == []


def test_chunk_document_overlap(sample_md):
    chunks = chunk_document(sample_md, chunk_size=30, overlap=10)
    if len(chunks) > 1:
        # Chunks should overlap — words from end of chunk N appear in chunk N+1
        words_0 = set(chunks[0].text.split())
        words_1 = set(chunks[1].text.split())
        assert len(words_0 & words_1) > 0, "Overlap should share words between adjacent chunks"


def test_chunk_ids_are_unique(sample_md):
    chunks = chunk_document(sample_md, chunk_size=50, overlap=10)
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids)), "All chunk IDs must be unique"
