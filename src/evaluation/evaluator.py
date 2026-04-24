"""
Evaluation module — measures quality of the knowledge engine.

Tracks 3 core metrics (same pattern as rag-chatbot):
1. Retrieval score  — did we find relevant chunks?
2. Answer faithfulness — did the LLM stay grounded in context?
3. Topic coverage — did the graph expand to related topics?

🫏 Evaluation is the road inspector. The donkey (LLM) might think the road is fine,
but the inspector measures potholes, detours, and missing signs objectively.
Without the inspector, you only know the road is broken when the goods fall off.
"""
import json
import yaml
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from src.config import get_settings
import structlog

logger = structlog.get_logger()


@dataclass
class EvalResult:
    question: str
    expected_topics: list[str]
    actual_topics: list[str]
    answer: str
    retrieval_score: float
    topic_coverage: float       # % of expected topics found
    latency_ms: int
    provider: str
    passed: bool = False

    def __post_init__(self):
        self.passed = self.retrieval_score >= 0.5 and self.topic_coverage >= 0.5


@dataclass
class EvalSummary:
    total: int = 0
    passed: int = 0
    avg_retrieval: float = 0.0
    avg_topic_coverage: float = 0.0
    avg_latency_ms: float = 0.0
    provider: str = ""
    results: list[EvalResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0


def load_golden_questions() -> list[dict]:
    """Load golden Q&A pairs from YAML file."""
    path = Path("scripts") / "golden-questions.yaml"
    if not path.exists():
        logger.warning("golden_questions_not_found", path=str(path))
        return []
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("questions", [])


async def run_evaluation(chat_engine, n_questions: int = None) -> EvalSummary:
    """Run eval set against the chat engine and return summary."""
    from src.models import ChatRequest

    questions = load_golden_questions()
    if n_questions:
        questions = questions[:n_questions]

    if not questions:
        logger.warning("no_golden_questions_to_evaluate")
        return EvalSummary()

    settings = get_settings()
    results = []

    for q in questions:
        start = time.monotonic()
        request = ChatRequest(question=q["question"])
        response = await chat_engine.answer(request)
        latency = int((time.monotonic() - start) * 1000)

        expected = q.get("expected_topics", [])
        actual = response.topics or []
        coverage = (
            len(set(t.lower() for t in actual) & set(t.lower() for t in expected)) / len(expected)
            if expected else 1.0
        )

        result = EvalResult(
            question=q["question"],
            expected_topics=expected,
            actual_topics=actual,
            answer=response.answer[:200],
            retrieval_score=response.retrieval_score,
            topic_coverage=coverage,
            latency_ms=latency,
            provider=settings.cloud_provider.value,
        )
        results.append(result)
        logger.info("eval_question", question=q["question"][:50],
                    passed=result.passed, retrieval=round(result.retrieval_score, 3))

    summary = EvalSummary(
        total=len(results),
        passed=sum(1 for r in results if r.passed),
        avg_retrieval=sum(r.retrieval_score for r in results) / len(results),
        avg_topic_coverage=sum(r.topic_coverage for r in results) / len(results),
        avg_latency_ms=sum(r.latency_ms for r in results) / len(results),
        provider=settings.cloud_provider.value,
        results=results,
    )

    _save_results(summary)
    logger.info("eval_complete", pass_rate=round(summary.pass_rate, 3),
                passed=summary.passed, total=summary.total)
    return summary


def _save_results(summary: EvalSummary):
    """Save eval results to scripts/eval-results/ directory."""
    out_dir = Path("scripts") / "eval-results"
    out_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    filename = f"eval-{summary.provider}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    path = out_dir / filename
    data = {
        "pass_rate": summary.pass_rate,
        "passed": summary.passed,
        "total": summary.total,
        "avg_retrieval": round(summary.avg_retrieval, 4),
        "avg_topic_coverage": round(summary.avg_topic_coverage, 4),
        "avg_latency_ms": round(summary.avg_latency_ms, 1),
        "provider": summary.provider,
        "results": [asdict(r) for r in summary.results],
    }
    path.write_text(json.dumps(data, indent=2))
    logger.info("eval_results_saved", path=str(path))
