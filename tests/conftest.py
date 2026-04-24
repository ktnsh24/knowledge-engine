"""pytest configuration — sets CLOUD_PROVIDER=local for all tests."""
import os
import pytest

# Always run tests against local provider — no cloud deps in unit tests
os.environ.setdefault("CLOUD_PROVIDER", "local")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("CHROMA_HOST", "localhost")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("SOURCE_REPOS_PATH", "/tmp/test-repos")
os.environ.setdefault("WIKI_OUTPUT_PATH", "/tmp/wiki-output")
