"""Tests for evaluation module."""
import pytest
import asyncio
from src.evaluation.evaluator import EvalResult, EvalSummary, load_golden_questions


def test_eval_result_passes_when_scores_good():
    result = EvalResult(
        question="What is RAG?",
        expected_topics=["rag"],
        actual_topics=["rag", "retrieval"],
        answer="RAG is...",
        retrieval_score=0.8,
        topic_coverage=1.0,
        latency_ms=350,
        provider="local",
    )
    assert result.passed is True


def test_eval_result_fails_when_retrieval_low():
    result = EvalResult(
        question="What is RAG?",
        expected_topics=["rag"],
        actual_topics=[],
        answer="I don't know",
        retrieval_score=0.1,
        topic_coverage=0.0,
        latency_ms=100,
        provider="local",
    )
    assert result.passed is False


def test_eval_summary_pass_rate():
    summary = EvalSummary(total=10, passed=7)
    assert summary.pass_rate == pytest.approx(0.7)


def test_eval_summary_zero_total():
    summary = EvalSummary(total=0, passed=0)
    assert summary.pass_rate == 0.0


def test_golden_questions_yaml_structure(tmp_path, monkeypatch):
    """golden-questions.yaml must have the right shape."""
    import yaml
    from pathlib import Path

    yaml_content = {
        "questions": [
            {"question": "What is RAG?", "expected_topics": ["rag"]},
        ]
    }
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "golden-questions.yaml").write_text(yaml.dump(yaml_content))

    # Patch Path to resolve to tmp_path
    monkeypatch.chdir(tmp_path)
    questions = load_golden_questions()
    assert len(questions) == 1
    assert questions[0]["question"] == "What is RAG?"
