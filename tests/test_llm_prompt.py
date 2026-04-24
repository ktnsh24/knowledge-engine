"""Tests for LLM system prompt — donkey analogy enforcement."""
import pytest
from src.llm.base import DONKEY_SYSTEM_PROMPT


def test_donkey_system_prompt_contains_emoji():
    assert "🫏" in DONKEY_SYSTEM_PROMPT


def test_donkey_system_prompt_explains_donkey_road_goods():
    prompt_lower = DONKEY_SYSTEM_PROMPT.lower()
    assert "donkey" in prompt_lower
    assert "road" in prompt_lower


def test_donkey_system_prompt_requires_analogy():
    """The prompt must instruct the LLM to always include the analogy."""
    assert "always" in DONKEY_SYSTEM_PROMPT.lower() or "every" in DONKEY_SYSTEM_PROMPT.lower()


def test_donkey_system_prompt_covers_multiple_topics():
    """Multi-topic conversations must each get their own analogy."""
    assert "multiple" in DONKEY_SYSTEM_PROMPT.lower() or "each" in DONKEY_SYSTEM_PROMPT.lower()
