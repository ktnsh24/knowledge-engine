#!/usr/bin/env python3
"""
🧪 Knowledge Engine — Hands-On Labs Automation Runner

Runs ALL hands-on lab experiments (Phase 1-3) programmatically against the
knowledge-engine API server and generates filled-in markdown reports with
real results, including all 9 metrics (5 of which were MISSING from rag-chatbot).

Usage:
    # Run all labs against local server (default):
    python scripts/run_all_labs.py

    # Run against AWS-deployed server:
    python scripts/run_all_labs.py --env aws --base-url http://your-aws-server:8200

    # Run against Azure-deployed server:
    python scripts/run_all_labs.py --env azure --base-url http://your-azure-server:8200

    # Dry-run (show what would run, no API calls):
    python scripts/run_all_labs.py --dry-run

    # Only run specific phases:
    python scripts/run_all_labs.py --phases 1,2

    # Only run specific experiments:
    python scripts/run_all_labs.py --only 1a,2c,4b

    # Skip ingestion check (if already ingested):
    python scripts/run_all_labs.py --skip-ingest

What it does:
    1. Checks API health and ingestion status
    2. Runs all experiments for Phase 1 (vector + graph), Phase 2 (missing metrics), Phase 3 (production)
    3. Captures all 9 metric scores + latencies + answers
    4. Generates filled-in markdown reports in scripts/lab-results/<env>/
    5. Creates a summary JSON with comparison_with_rag_chatbot section
    6. Prints a final pass/fail table to terminal

🚚 Courier Analogy:
    This script is the inspector who follows the courier on every delivery,
    measures the time, checks the package quality, and writes the full report.
    You don't have to manually fill in tables anymore — the inspector does it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8200"
DEFAULT_TIMEOUT = 120  # seconds per request
OUTPUT_DIR = Path("scripts") / "lab-results"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ExperimentResult:
    """Result of a single lab experiment."""
    id: str                          # e.g. "1a", "4b"
    phase: int
    lab: int
    description: str
    question: str = ""
    answer: str = ""
    scores: dict = field(default_factory=dict)
    latency_ms: int = 0
    topics: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    courier_analogy: str = ""
    passed: bool = False
    error: str = ""
    skipped: bool = False
    timestamp: str = field(default_factory=lambda: _now())

    @property
    def status_icon(self) -> str:
        if self.skipped: return "⏭"
        if self.error:   return "❌"
        if self.passed:  return "✅"
        return "⚠️"

    def score(self, key: str, default: float = 0.0) -> float:
        return round(float(self.scores.get(key, default)), 3)


@dataclass
class RunSummary:
    env: str
    start_time: str
    end_time: str = ""
    total_experiments: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[ExperimentResult] = field(default_factory=list)
    eval_summary: dict = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        ran = self.total_experiments - self.skipped
        return self.passed / ran if ran > 0 else 0.0


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class LabAPIClient:

    def __init__(self, base_url: str, timeout: int = DEFAULT_TIMEOUT, dry_run: bool = False):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.dry_run = dry_run
        self._client = httpx.Client(timeout=timeout)

    def health(self) -> dict:
        if self.dry_run:
            return {"status": "healthy", "provider": "local", "vector_store_chunks": 0, "graph_topics": 0}
        return self._client.get(f"{self.base_url}/health/").json()

    def chat(self, question: str) -> dict:
        if self.dry_run:
            return {
                "answer": f"[DRY RUN] Answer for: {question}",
                "courier_analogy": "🚚 [DRY RUN]",
                "sources": [], "topics": [], "latency_ms": 0,
                "provider": "local",
            }
        resp = self._client.post(
            f"{self.base_url}/chat/",
            json={"question": question},
        )
        resp.raise_for_status()
        return resp.json()

    def ingest_status(self) -> dict:
        if self.dry_run:
            return {"chunks": 100, "topics": 20}
        return self._client.get(f"{self.base_url}/ingest/status").json()

    def run_ingest(self) -> dict:
        if self.dry_run:
            return {"status": "started"}
        return self._client.post(f"{self.base_url}/ingest/run").json()

    def run_eval(self, n_questions: int = None) -> dict:
        if self.dry_run:
            return {
                "pass_rate": 0.72, "passed": 8, "total": 11,
                "provider": "local",
                "metrics": {
                    "avg_retrieval": 0.71, "avg_context_precision": 0.68,
                    "avg_context_recall": 0.65, "avg_faithfulness": 0.82,
                    "avg_answer_relevance": 0.74, "avg_answer_correctness": 0.60,
                    "avg_completeness": 0.70, "hallucination_rate_pct": 9.1,
                    "avg_cost_per_query_usd": 0.0,
                },
                "avg_latency_ms": 1240.0,
                "comparison_with_rag_chatbot": {
                    "rag_chatbot_had": {"avg_faithfulness": 0.75},
                    "NEW_in_knowledge_engine": {
                        "avg_context_recall": 0.65,
                        "avg_answer_correctness": 0.60,
                        "avg_completeness": 0.70,
                        "hallucination_rate_pct": 9.1,
                        "avg_cost_per_query_usd": 0.0,
                        "faithfulness_upgraded_to_llm_as_judge": True,
                    }
                },
                "results": [],
            }
        body = {}
        if n_questions:
            body["n_questions"] = n_questions
        resp = self._client.post(f"{self.base_url}/eval/run", json=body)
        resp.raise_for_status()
        return resp.json()

    def list_topics(self) -> list:
        if self.dry_run:
            return [{"id": "rag", "name": "RAG"}, {"id": "graphrag", "name": "GraphRAG"}]
        return self._client.get(f"{self.base_url}/wiki/topics").json().get("topics", [])

    def submit_feedback(self, question: str, answer: str, thumbs_up: bool, correction: str = "") -> dict:
        if self.dry_run:
            return {"action": "wiki_updated" if thumbs_up else "eval_set_updated", "message": "[DRY RUN]"}
        resp = self._client.post(f"{self.base_url}/feedback/", json={
            "question": question, "answer": answer,
            "thumbs_up": thumbs_up, "correction": correction,
            "session_id": "run-all-labs",
            "timestamp": _now(),
        })
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_header(text: str):
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")


def _print_result(r: ExperimentResult):
    status = r.status_icon
    overall = r.scores.get("overall", r.scores.get("pass_rate", "—"))
    latency = f"{r.latency_ms}ms" if r.latency_ms else "—"
    print(f"  {status} [{r.id}] {r.description[:55]:<55} | overall={overall} | {latency}")
    if r.error:
        print(f"       ⚠ ERROR: {r.error[:80]}")


def _chat_experiment(
    client: LabAPIClient,
    exp_id: str,
    phase: int,
    lab: int,
    description: str,
    question: str,
) -> ExperimentResult:
    """Run a chat experiment, capture all scores."""
    result = ExperimentResult(
        id=exp_id, phase=phase, lab=lab,
        description=description, question=question,
    )
    print(f"  ▶ [{exp_id}] {description[:55]}...", flush=True, end="")
    try:
        t0 = time.monotonic()
        data = client.chat(question)
        result.latency_ms = data.get("latency_ms") or int((time.monotonic() - t0) * 1000)
        result.answer = data.get("answer", "")
        result.courier_analogy = data.get("courier_analogy", "")
        result.sources = data.get("sources", [])
        result.topics = data.get("topics", [])
        result.scores = {
            "retrieval_score": data.get("retrieval_score", 0.0),
            "provider": data.get("provider", "local"),
        }
        result.passed = bool(result.answer) and "🚚" in (result.courier_analogy or result.answer)
        print(f" ✓ ({result.latency_ms}ms)")
    except Exception as e:
        result.error = str(e)
        print(f" ✗ ERROR: {e}")
    return result


def _eval_experiment(
    client: LabAPIClient,
    exp_id: str,
    phase: int,
    lab: int,
    description: str,
    n_questions: int = None,
) -> ExperimentResult:
    """Run eval suite, capture all 9 metrics."""
    result = ExperimentResult(
        id=exp_id, phase=phase, lab=lab,
        description=description,
        question=f"Eval suite ({n_questions or 'all'} questions)",
    )
    print(f"  ▶ [{exp_id}] {description[:55]}...", flush=True, end="")
    try:
        t0 = time.monotonic()
        data = client.run_eval(n_questions)
        result.latency_ms = int((time.monotonic() - t0) * 1000)
        metrics = data.get("metrics", {})
        result.scores = {
            "pass_rate": data.get("pass_rate", 0.0),
            "passed": data.get("passed", 0),
            "total": data.get("total", 0),
            **metrics,
        }
        result.passed = data.get("pass_rate", 0.0) >= 0.65
        result.answer = json.dumps(data.get("comparison_with_rag_chatbot", {}), indent=2)
        print(f" ✓ pass_rate={data.get('pass_rate', '?')}")
    except Exception as e:
        result.error = str(e)
        print(f" ✗ ERROR: {e}")
    return result


# ---------------------------------------------------------------------------
# Phase 1: GraphRAG Foundation
# ---------------------------------------------------------------------------

def run_phase_1(client: LabAPIClient) -> list[ExperimentResult]:
    _print_header("📘 PHASE 1 — GraphRAG Foundation (Labs 1-3)")
    results = []

    # Lab 1 — Vector search
    results.append(_chat_experiment(client, "1a", 1, 1,
        "Baseline retrieval — general RAG question",
        "What is RAG and why is it used?"))

    results.append(_chat_experiment(client, "1b", 1, 1,
        "Specific technical question — Titan normalization",
        "Why did AWS Titan embeddings score low and how was the normalization fix applied?"))

    results.append(_chat_experiment(client, "1c", 1, 1,
        "Out-of-domain question — expect refusal not hallucination",
        "What is the best recipe for Dutch stroopwafel?"))

    # Lab 2 — Graph traversal
    results.append(_chat_experiment(client, "2a", 1, 2,
        "Graph-connected topic — GraphRAG explanation",
        "Explain GraphRAG and what makes it different from plain vector search"))

    results.append(_chat_experiment(client, "2b", 1, 2,
        "Multi-hop question — spans 2 graph hops",
        "How does the feedback loop in the knowledge engine connect to the evaluation system?"))

    results.append(_chat_experiment(client, "2c", 1, 2,
        "Cross-topic question — tests graph expansion",
        "How does the knowledge engine improve over time with user feedback?"))

    # Lab 3 — Full eval baseline
    results.append(_eval_experiment(client, "3a", 1, 3,
        "Baseline eval — 5 golden questions", n_questions=5))

    results.append(_eval_experiment(client, "3b", 1, 3,
        "Full eval — all 11 golden questions", n_questions=11))

    for r in results:
        _print_result(r)
    return results


# ---------------------------------------------------------------------------
# Phase 2: Missing Metrics
# ---------------------------------------------------------------------------

def run_phase_2(client: LabAPIClient) -> list[ExperimentResult]:
    _print_header("📗 PHASE 2 — Missing Metrics (5 gaps from rag-chatbot)")
    results = []

    # Lab 4 — LLM-as-Judge faithfulness
    results.append(_chat_experiment(client, "4a", 2, 4,
        "Faithfulness — factual question (expect high score)",
        "What embedding model was used in the rag-chatbot project?"))

    results.append(_chat_experiment(client, "4b", 2, 4,
        "Faithfulness — out-of-context trick question",
        "What was the weather in Amsterdam when the rag-chatbot was built?"))

    results.append(_eval_experiment(client, "4c", 2, 4,
        "Faithfulness eval — LLM-as-Judge vs keyword comparison", n_questions=3))

    # Lab 5 — Answer correctness (semantic)
    results.append(_chat_experiment(client, "5a", 2, 5,
        "Answer correctness — RAG definition question",
        "What is RAG and why is it used instead of fine-tuning?"))

    results.append(_chat_experiment(client, "5b", 2, 5,
        "Answer correctness — vector DB question",
        "What does the vector database store?"))

    # Lab 6 — Completeness
    results.append(_chat_experiment(client, "6a", 2, 6,
        "Completeness — multi-aspect question (WHAT/HOW/WHY)",
        "What is GraphRAG, how does it combine vector and graph stores, and why does it improve answer quality?"))

    results.append(_chat_experiment(client, "6b_single", 2, 6,
        "Completeness — single aspect (for comparison)",
        "What is a vector database?"))

    results.append(_chat_experiment(client, "6b_multi", 2, 6,
        "Completeness — multi-aspect (for comparison)",
        "What is a vector database, why do we need it, and how is it different from a graph database?"))

    # Lab 7 — Hallucination rate
    results.append(_eval_experiment(client, "7a", 2, 7,
        "Hallucination rate — full eval suite", n_questions=11))

    results.append(_chat_experiment(client, "7b", 2, 7,
        "Force hallucination — unknowable question",
        "What was Ketan Sahu doing on March 15th 2020?"))

    # Lab 8 — Cost per query
    results.append(_chat_experiment(client, "8a_short", 2, 8,
        "Cost — short answer prompt",
        "Define RAG in one sentence."))

    results.append(_chat_experiment(client, "8a_long", 2, 8,
        "Cost — long answer prompt",
        "Explain the entire knowledge-engine architecture in detail including all components, how they interact, the evaluation framework, the cloud deployment options, and the courier analogy."))

    for r in results:
        _print_result(r)
    return results


# ---------------------------------------------------------------------------
# Phase 3: Production
# ---------------------------------------------------------------------------

def run_phase_3(client: LabAPIClient, output_dir: Path) -> list[ExperimentResult]:
    _print_header("📕 PHASE 3 — Production (Feedback, Multi-Cloud, CI/CD Gate)")
    results = []

    # Lab 9 — Feedback loops
    # 9a: positive feedback
    r9a = ExperimentResult(id="9a", phase=3, lab=9,
        description="Positive feedback (👍) — verify wiki updated")
    print(f"  ▶ [9a] Submitting positive feedback...", flush=True, end="")
    try:
        resp = client.submit_feedback(
            question="What is the courier analogy in this project?",
            answer="The LLM is the courier carrying your question to an answer.",
            thumbs_up=True,
        )
        r9a.scores = {"action": resp.get("action", ""), "feedback_type": "positive"}
        r9a.passed = resp.get("action") == "wiki_updated"
        r9a.answer = resp.get("message", "")
        print(f" ✓ action={resp.get('action')}")
    except Exception as e:
        r9a.error = str(e)
        print(f" ✗ {e}")
    results.append(r9a)

    # 9b: negative feedback
    r9b = ExperimentResult(id="9b", phase=3, lab=9,
        description="Negative feedback (👎) — verify eval set updated")
    print(f"  ▶ [9b] Submitting negative feedback...", flush=True, end="")
    try:
        resp = client.submit_feedback(
            question="What AWS services does the knowledge engine use?",
            answer="It uses EC2 and RDS.",
            thumbs_up=False,
            correction="It uses DynamoDB for graph and vector store, and Bedrock for LLM.",
        )
        r9b.scores = {"action": resp.get("action", ""), "feedback_type": "negative"}
        r9b.passed = resp.get("action") == "eval_set_updated"
        r9b.answer = resp.get("message", "")
        print(f" ✓ action={resp.get('action')}")
    except Exception as e:
        r9b.error = str(e)
        print(f" ✗ {e}")
    results.append(r9b)

    # 9c: re-run eval after feedback
    results.append(_eval_experiment(client, "9c", 3, 9,
        "Eval after feedback — golden set should have grown"))

    # Lab 10 — Graph traversal quality
    results.append(_eval_experiment(client, "10a", 3, 10,
        "Graph traversal quality — 5 questions", n_questions=5))

    results.append(_chat_experiment(client, "10b", 3, 10,
        "Multi-hop graph question — tests 2-hop traversal",
        "How are embeddings, vector search, and cosine similarity all related?"))

    # Lab 11 — Provider info (just records what provider is running)
    r11 = ExperimentResult(id="11a", phase=3, lab=11,
        description="Provider check — what is currently running?")
    print(f"  ▶ [11a] Checking provider...", flush=True, end="")
    try:
        health = client.health()
        r11.scores = {
            "provider": health.get("provider", "unknown"),
            "chunks": health.get("vector_store_chunks", 0),
            "topics": health.get("graph_topics", 0),
        }
        r11.passed = health.get("status") == "healthy"
        r11.answer = f"Provider: {health.get('provider')}, Chunks: {health.get('vector_store_chunks')}, Topics: {health.get('graph_topics')}"
        print(f" ✓ {r11.answer}")
    except Exception as e:
        r11.error = str(e)
        print(f" ✗ {e}")
    results.append(r11)

    # Full final eval
    results.append(_eval_experiment(client, "12a", 3, 12,
        "Final eval — CI/CD gate simulation (pass >= 0.70?)", n_questions=11))

    for r in results:
        _print_result(r)
    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_summary_report(
    all_results: list[ExperimentResult],
    eval_data: dict,
    env: str,
    output_dir: Path,
) -> Path:
    """Generate a filled-in markdown report with all results."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    provider = env.upper()
    metrics = eval_data.get("metrics", {})
    comparison = eval_data.get("comparison_with_rag_chatbot", {})
    new_metrics = comparison.get("NEW_in_knowledge_engine", {})
    old_metrics = comparison.get("rag_chatbot_had", {})

    def _val(key: str, default: str = "—") -> str:
        v = metrics.get(key)
        return str(round(v, 4)) if v is not None else default

    def _pct(key: str) -> str:
        v = metrics.get(key)
        return f"{v}%" if v is not None else "—"

    # Build per-experiment table rows
    rows = []
    for r in all_results:
        overall = r.scores.get("pass_rate", r.scores.get("overall", "—"))
        rows.append(
            f"| {r.id} | {r.description[:50]} | "
            f"{r.status_icon} | {overall} | {r.latency_ms}ms |"
        )

    rows_md = "\n".join(rows)

    report = f"""# 🧪 Knowledge Engine Lab Results — {provider} Environment

> **Generated:** {ts}
> **Provider:** {provider}
> **API:** {DEFAULT_BASE_URL}

---

## 📊 Evaluation Summary — All 9 Metrics

### Metrics present in rag-chatbot (for comparison)

| Metric | rag-chatbot score | knowledge-engine ({provider}) |
|--------|------------------|------------------------------|
| `avg_retrieval` | *not recorded* | **{_val("avg_retrieval")}** |
| `avg_context_precision` | *not recorded* | **{_val("avg_context_precision")}** |
| `avg_faithfulness` | {old_metrics.get("faithfulness_keyword_based", "—")} (keyword) | **{_val("avg_faithfulness")}** (LLM-as-Judge ✅) |
| `avg_answer_relevance` | *basic* | **{_val("avg_answer_relevance")}** |

### NEW metrics — missing from rag-chatbot

| Metric | Was in rag-chatbot? | {provider} Score | Pass threshold |
|--------|--------------------|--------------------|----------------|
| `avg_context_recall` | ❌ Missing | **{_val("avg_context_recall")}** | > 0.60 |
| `avg_answer_correctness` | ❌ Missing | **{_val("avg_answer_correctness")}** | > 0.60 |
| `avg_completeness` | ❌ Missing (exercise only) | **{_val("avg_completeness")}** | > 0.60 |
| `hallucination_rate_pct` | ❌ per-query boolean only | **{_pct("hallucination_rate_pct")}** | < 10% |
| `avg_cost_per_query_usd` | ❌ documented, never tracked | **${metrics.get("avg_cost_per_query_usd", 0.0):.6f}** | < $0.002 |

### Overall

| Metric | Value |
|--------|-------|
| **Pass rate** | **{eval_data.get("pass_rate", "—")}** ({eval_data.get("passed", "—")}/{eval_data.get("total", "—")}) |
| **Avg latency** | {eval_data.get("avg_latency_ms", "—")}ms |
| **Provider** | {env} |
| **Total cost** | ${metrics.get("total_cost_usd", 0.0):.4f} |

---

## 🧪 Experiment Results — All Labs

| ID | Description | Status | Score | Latency |
|----|-------------|--------|-------|---------|
{rows_md}

---

## Phase 1 — GraphRAG Foundation

### Lab 1: Vector Search

| Experiment | Question | Retrieval Score | Latency | Has 🚚? |
|------------|----------|----------------|---------|---------|
"""
    for r in all_results:
        if r.id in ("1a", "1b", "1c"):
            has_courier = "✅" if r.courier_analogy or "🚚" in r.answer else "❌"
            report += f"| {r.id} | {r.question[:45]} | {r.score('retrieval_score'):.3f} | {r.latency_ms}ms | {has_courier} |\n"

    report += """
### Lab 2: Graph Traversal

| Experiment | Topics Returned | Answer Preview |
|------------|----------------|----------------|
"""
    for r in all_results:
        if r.id in ("2a", "2b", "2c"):
            topics = ", ".join(r.topics[:3]) or "—"
            preview = r.answer[:80].replace("\n", " ") if r.answer else "—"
            report += f"| {r.id} | {topics} | {preview}... |\n"

    report += f"""
### Lab 3: Baseline Eval

| Experiment | Pass Rate | Questions | Avg Latency |
|------------|-----------|-----------|-------------|
"""
    for r in all_results:
        if r.id in ("3a", "3b"):
            report += (
                f"| {r.id} | {r.scores.get('pass_rate', '—')} | "
                f"{r.scores.get('total', '—')} | {r.latency_ms}ms |\n"
            )

    report += f"""
---

## Phase 2 — Missing Metrics (5 gaps from rag-chatbot)

### Lab 4: LLM-as-Judge Faithfulness

| Experiment | Faithfulness | Has Hallucination | Method |
|------------|-------------|-------------------|--------|
"""
    for r in all_results:
        if r.id in ("4a", "4b"):
            report += (
                f"| {r.id} — {r.description[:40]} | "
                f"{r.score('faithfulness', r.score('retrieval_score'))} | "
                f"{'❌ YES' if r.scores.get('has_hallucination') else '✅ NO'} | "
                f"LLM-as-Judge |\n"
            )

    report += """
### Lab 5: Answer Correctness (Semantic)

| Experiment | Question | Answer Correctness | Answer Relevance (keyword) |
|------------|----------|-------------------|---------------------------|
"""
    for r in all_results:
        if r.id in ("5a", "5b"):
            report += (
                f"| {r.id} | {r.question[:40]} | "
                f"{r.score('answer_correctness')} | {r.score('answer_relevance')} |\n"
            )

    report += """
### Lab 6: Completeness Score

| Experiment | Type | Completeness | Aspects in Q | Aspects Answered |
|------------|------|-------------|--------------|-----------------|
"""
    for r in all_results:
        if r.id in ("6a", "6b_single", "6b_multi"):
            q_type = "Multi-aspect" if "multi" in r.id or "GraphRAG" in r.question else "Single"
            report += (
                f"| {r.id} | {q_type} | {r.score('completeness')} | "
                f"{r.scores.get('aspects_in_question', '—')} | {r.scores.get('aspects_answered', '—')} |\n"
            )

    report += f"""
### Lab 7: Hallucination Rate

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| `hallucination_rate_pct` | {_pct("hallucination_rate_pct")} | < 10% | {'✅ PASS' if (metrics.get("hallucination_rate_pct") or 100) < 10 else '⚠️ NEEDS TUNING'} |

### Lab 8: Cost Per Query

| Prompt Type | Total Tokens | Cost (USD) |
|-------------|-------------|------------|
"""
    for r in all_results:
        if r.id in ("8a_short", "8a_long"):
            tokens = r.scores.get("total_tokens", "—")
            cost = r.scores.get("cost_usd", "—")
            label = "Short" if "short" in r.id else "Long"
            report += f"| {label} | {tokens} | ${cost} |\n"

    report += f"""
---

## Phase 3 — Production

### Lab 9: Feedback Loops

| Experiment | Feedback Type | Action | Status |
|------------|--------------|--------|--------|
"""
    for r in all_results:
        if r.id in ("9a", "9b"):
            fb_type = r.scores.get("feedback_type", "—")
            action = r.scores.get("action", "—")
            report += f"| {r.id} | {fb_type} | {action} | {r.status_icon} |\n"

    # CI gate simulation
    gate_result = next((r for r in all_results if r.id == "12a"), None)
    gate_pass = gate_result and gate_result.scores.get("pass_rate", 0) >= 0.70
    report += f"""
### Lab 12: CI/CD Eval Gate Simulation

| Threshold | Actual Pass Rate | Gate Result |
|-----------|-----------------|-------------|
| 70% | {gate_result.scores.get("pass_rate", "—") if gate_result else "—"} | {'✅ WOULD PASS' if gate_pass else '❌ WOULD BLOCK DEPLOY'} |

---

## 🚚 Courier Analogy Spot-Check

All answers should contain a courier analogy. Checking Lab 1-3 answers:

| Experiment | Contains 🚚? | Analogy Preview |
|------------|-------------|----------------|
"""
    for r in all_results:
        if r.id in ("1a", "2a", "3a"):
            has = "✅" if r.courier_analogy or "🚚" in r.answer else "❌"
            preview = (r.courier_analogy or "—")[:80]
            report += f"| {r.id} | {has} | {preview} |\n"

    report += f"""
---

## 📁 Output Files

Results saved to: `scripts/lab-results/{env}/`
- `run-results.json` — full raw results
- `eval-summary.json` — 9-metric eval summary
- `lab-results-report.md` — this file

---

## 🔁 Comparison With rag-chatbot

```json
{json.dumps(comparison, indent=2)}
```
"""

    # Save report
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "lab-results-report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# Final terminal summary
# ---------------------------------------------------------------------------

def print_final_summary(summary: RunSummary):
    _print_header("📋 FINAL SUMMARY")
    total_ran = summary.total_experiments - summary.skipped
    print(f"\n  Environment : {summary.ENV if hasattr(summary, 'ENV') else summary.env.upper()}")
    print(f"  Start time  : {summary.start_time}")
    print(f"  End time    : {summary.end_time}")
    print(f"  Experiments : {total_ran} ran / {summary.skipped} skipped")
    print(f"  Results     : ✅ {summary.passed} passed | ⚠️ {summary.failed} failed")
    print(f"  Pass rate   : {summary.pass_rate:.1%}")

    if summary.eval_summary:
        metrics = summary.eval_summary.get("metrics", {})
        print(f"\n  📊 9-Metric Eval Results:")
        print(f"     {'Metric':<35} Value    Was in rag-chatbot?")
        print(f"     {'──────':<35} ─────    ──────────────────")
        pairs = [
            ("avg_retrieval",            True),
            ("avg_context_precision",    True),
            ("avg_faithfulness",         True),
            ("avg_answer_relevance",     True),
            ("avg_context_recall",       False),
            ("avg_answer_correctness",   False),
            ("avg_completeness",         False),
            ("hallucination_rate_pct",   False),
            ("avg_cost_per_query_usd",   False),
        ]
        for key, was_in_rag in pairs:
            val = metrics.get(key)
            if val is None:
                continue
            tag = "   (existed)" if was_in_rag else "🆕 (NEW!)"
            if key == "hallucination_rate_pct":
                display = f"{val}%"
            elif key == "avg_cost_per_query_usd":
                display = f"${val:.6f}"
            else:
                display = f"{val:.4f}"
            print(f"     {key:<35} {display:<8} {tag}")

        pass_rate = summary.eval_summary.get("pass_rate", 0)
        gate_status = "✅ CI gate would PASS" if pass_rate >= 0.70 else "❌ CI gate would BLOCK deploy"
        print(f"\n  Overall pass rate : {pass_rate:.1%}  → {gate_status}")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run all knowledge-engine hands-on labs and generate reports"
    )
    parser.add_argument("--env", default="local", choices=["local", "aws", "azure"],
                        help="Environment name (for report labelling)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help=f"API base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--phases", default="1,2,3",
                        help="Phases to run, comma-separated (default: 1,2,3)")
    parser.add_argument("--only", default=None,
                        help="Run only specific experiment IDs, e.g. --only 1a,4b")
    parser.add_argument("--skip-ingest", action="store_true",
                        help="Skip ingestion check (docs already ingested)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would run without making API calls")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()

    phases = [int(p) for p in args.phases.split(",")]
    only = set(args.only.split(",")) if args.only else None
    output_dir = OUTPUT_DIR / args.env
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🧪 Knowledge Engine Lab Runner")
    print(f"   Environment : {args.env.upper()}")
    print(f"   API URL     : {args.base_url}")
    print(f"   Phases      : {phases}")
    print(f"   Dry run     : {args.dry_run}")
    print(f"   Output      : {output_dir}")

    client = LabAPIClient(args.base_url, timeout=args.timeout, dry_run=args.dry_run)

    # Health check
    print("\n⏳ Checking API health...", flush=True, end="")
    try:
        health = client.health()
        status = health.get("status", "unknown")
        chunks = health.get("vector_store_chunks", 0)
        topics = health.get("graph_topics", 0)
        print(f" ✓ {status} | {chunks} chunks | {topics} topics | provider={health.get('provider')}")
    except Exception as e:
        print(f"\n❌ API not reachable: {e}")
        print("   Run: docker compose up -d && poetry run start")
        sys.exit(1)

    # Ingestion check
    if not args.skip_ingest:
        status_data = client.ingest_status()
        if status_data.get("chunks", 0) == 0:
            print("\n⏳ No chunks found — running ingestion first...")
            client.run_ingest()
            print("   Ingestion started. Waiting 30s for initial chunks...")
            time.sleep(30)
            status_data = client.ingest_status()
            print(f"   Chunks: {status_data.get('chunks', 0)}, Topics: {status_data.get('topics', 0)}")

    summary = RunSummary(env=args.env, start_time=_now())
    all_results: list[ExperimentResult] = []

    # Run phases
    if 1 in phases:
        all_results.extend(run_phase_1(client))
    if 2 in phases:
        all_results.extend(run_phase_2(client))
    if 3 in phases:
        all_results.extend(run_phase_3(client, output_dir))

    # Apply --only filter
    if only:
        all_results = [r for r in all_results if r.id in only]

    # Tally
    summary.total_experiments = len(all_results)
    summary.passed = sum(1 for r in all_results if r.passed and not r.skipped)
    summary.failed = sum(1 for r in all_results if not r.passed and not r.skipped and not r.error)
    summary.skipped = sum(1 for r in all_results if r.skipped)
    summary.end_time = _now()

    # Get final eval summary (last eval result)
    eval_results = [r for r in all_results if "pass_rate" in r.scores]
    if eval_results:
        last_eval = eval_results[-1]
        summary.eval_summary = {
            "pass_rate": last_eval.scores.get("pass_rate", 0),
            "metrics": {k: v for k, v in last_eval.scores.items()
                        if k not in ("pass_rate", "passed", "total")},
        }

    # Save raw results
    raw_path = output_dir / "run-results.json"
    raw_path.write_text(json.dumps(
        [asdict(r) for r in all_results], indent=2, default=str
    ))

    # Save eval summary
    eval_path = output_dir / "eval-summary.json"
    if eval_results:
        # Get the most complete eval result (from full 11-question run)
        full_eval = next(
            (r for r in reversed(eval_results) if r.scores.get("total", 0) >= 11),
            eval_results[-1]
        )
        # Re-run eval to get the comparison_with_rag_chatbot field
        try:
            full_eval_data = client.run_eval(n_questions=11)
            eval_path.write_text(json.dumps(full_eval_data, indent=2))
            summary.eval_summary = full_eval_data
        except Exception:
            eval_path.write_text(json.dumps(summary.eval_summary, indent=2))

    # Generate report
    eval_data = summary.eval_summary or {}
    report_path = generate_summary_report(all_results, eval_data, args.env, output_dir)

    # Print final summary
    print_final_summary(summary)
    print(f"📄 Report saved: {report_path}")
    print(f"📦 Raw results : {raw_path}")
    print(f"📊 Eval summary: {eval_path}")

    client.close()

    # Exit code: 0 if CI gate would pass, 1 if it would block
    pass_rate = eval_data.get("pass_rate", 0.0) if isinstance(eval_data, dict) else 0.0
    sys.exit(0 if pass_rate >= 0.70 else 1)


if __name__ == "__main__":
    main()
