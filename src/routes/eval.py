"""API route — evaluation endpoint."""
from fastapi import APIRouter, Request, BackgroundTasks
from src.evaluation.evaluator import KnowledgeEngineEvaluator, run_evaluation, EvalSummary
import structlog

router = APIRouter()
logger = structlog.get_logger()


@router.post("/run")
async def run_eval(request: Request, n_questions: int = None):
    """Run evaluation against golden questions. Returns full summary with all 9 metrics."""
    chat_engine = request.app.state.chat_engine
    llm = request.app.state.llm
    vector_store = request.app.state.vector_store
    evaluator = KnowledgeEngineEvaluator(llm=llm)

    summary = await run_evaluation(chat_engine, evaluator, n_questions=n_questions)

    return {
        "pass_rate": round(summary.pass_rate, 3),
        "passed": summary.passed,
        "total": summary.total,
        "provider": summary.provider,
        "metrics": {
            # Same as rag-chatbot
            "avg_retrieval": round(summary.avg_retrieval, 4),
            "avg_context_precision": round(summary.avg_context_precision, 4),
            "avg_faithfulness": round(summary.avg_faithfulness, 4),
            "avg_answer_relevance": round(summary.avg_answer_relevance, 4),
            # NEW — was missing from rag-chatbot
            "avg_context_recall": round(summary.avg_context_recall, 4),
            "avg_answer_correctness": round(summary.avg_answer_correctness, 4),
            "avg_completeness": round(summary.avg_completeness, 4),
            "hallucination_rate_pct": round(summary.hallucination_rate * 100, 1),
            "avg_cost_per_query_usd": round(summary.avg_cost_per_query_usd, 6),
            "total_cost_usd": round(summary.total_cost_usd, 4),
        },
        "avg_latency_ms": round(summary.avg_latency_ms, 1),
        "comparison_with_rag_chatbot": summary.compare_with_rag_chatbot(),
        "results": [r.to_dict() for r in summary.results],
    }
