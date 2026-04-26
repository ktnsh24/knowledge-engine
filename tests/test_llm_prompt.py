"""Tests for LLM system prompt — courier analogy enforcement."""
import pytest
from src.llm.base import COURIER_SYSTEM_PROMPT


def test_courier_system_prompt_contains_emoji():
    assert "🚚" in COURIER_SYSTEM_PROMPT


def test_courier_system_prompt_explains_courier_road_goods():
    prompt_lower = COURIER_SYSTEM_PROMPT.lower()
    assert "courier" in prompt_lower
    assert "road" in prompt_lower


def test_courier_system_prompt_requires_analogy():
    """The prompt must instruct the LLM to always include the analogy."""
    assert "always" in COURIER_SYSTEM_PROMPT.lower() or "every" in COURIER_SYSTEM_PROMPT.lower()


def test_courier_system_prompt_covers_multiple_topics():
    """Multi-topic conversations must each get their own analogy."""
    assert "multiple" in COURIER_SYSTEM_PROMPT.lower() or "each" in COURIER_SYSTEM_PROMPT.lower()
