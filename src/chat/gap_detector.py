"""
Gap detector — marks where the road is missing.

When the courier can't find a good route (low retrieval scores), it marks the broken road
on the map so you know where to build. Without this, you'd never know which questions
are silently being answered from the LLM's training data instead of your docs.

🚚 The gap detector is the courier's honest confession:
   "I tried my best, but the road ends here. Here's where you need to build more."

Three confidence levels:
  HIGH    — retrieval_score >= 0.70: good chunks found, answer is grounded
  PARTIAL — retrieval_score 0.40–0.69: some relevant chunks but coverage is thin
  GAP     — retrieval_score < 0.40: no meaningful chunks found — likely hallucination risk

Gaps are saved to wiki/gaps/unanswered.md for human review.
A gap can be "resolved" by adding docs and re-ingesting, or by verifying an LLM answer
and promoting it to verified-answers.md via 👍 feedback.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from src.models import KnowledgeGap, ConfidenceLevel
from src.config import get_settings
import structlog

logger = structlog.get_logger()

# Thresholds — tune these based on your embedding model
HIGH_CONFIDENCE_THRESHOLD = 0.70    # retrieval score above this = grounded answer
PARTIAL_CONFIDENCE_THRESHOLD = 0.40  # between this and HIGH = partial knowledge


class GapDetector:
    """
    Detects when a question is not well-covered by the ingested docs.

    Attached to the ChatEngine — runs after vector search, before LLM call.
    Saves gaps to wiki/gaps/unanswered.md and wiki/gaps/gaps.jsonl (machine-readable).
    """

    def __init__(self):
        settings = get_settings()
        self.gaps_path = Path(settings.wiki_output_path) / "gaps"
        self.gaps_path.mkdir(parents=True, exist_ok=True)
        self.gaps_file = self.gaps_path / "unanswered.md"
        self.gaps_jsonl = self.gaps_path / "gaps.jsonl"

    def assess_confidence(
        self,
        question: str,
        top_retrieval_score: float,
        chunk_count: int,
        topic_count: int,
    ) -> KnowledgeGap:
        """
        Assess how well the knowledge base covers this question.

        Returns a KnowledgeGap with confidence level and a human-readable reason.
        The gap is NOT saved here — call save_gap() only if you want to persist it.
        """
        gap_id = str(uuid.uuid4())[:8]

        if top_retrieval_score >= HIGH_CONFIDENCE_THRESHOLD and chunk_count >= 2:
            confidence = ConfidenceLevel.HIGH
            reason = f"Good coverage — top score {top_retrieval_score:.2f}, {chunk_count} chunks found"
            suggestion = ""

        elif top_retrieval_score >= PARTIAL_CONFIDENCE_THRESHOLD or chunk_count >= 1:
            confidence = ConfidenceLevel.PARTIAL
            reason = (
                f"Partial coverage — top score {top_retrieval_score:.2f}, "
                f"{chunk_count} chunk(s) found, {topic_count} connected topic(s). "
                "Answer may be incomplete or partially from LLM training data."
            )
            suggestion = (
                "Add more documentation about this topic and re-run ingestion. "
                "Or verify this answer with 👍 to promote it to the wiki."
            )

        else:
            confidence = ConfidenceLevel.GAP
            reason = (
                f"No meaningful coverage — top score {top_retrieval_score:.2f}, "
                f"only {chunk_count} chunk(s) found. "
                "Answer is likely generated from LLM training data, not your docs."
            )
            suggestion = (
                "This topic is missing from your knowledge base. "
                "Write a doc about it, add it to SOURCE_REPOS_PATH, and re-run ingestion."
            )

        return KnowledgeGap(
            id=gap_id,
            question=question,
            confidence=confidence,
            retrieval_score=top_retrieval_score,
            chunk_count=chunk_count,
            topic_count=topic_count,
            reason=reason,
            suggestion=suggestion,
        )

    async def save_gap(self, gap: KnowledgeGap) -> None:
        """Persist a PARTIAL or GAP entry to disk for human review."""
        if gap.confidence == ConfidenceLevel.HIGH:
            return  # nothing to save

        # Append to human-readable markdown
        label = "🔴 GAP" if gap.confidence == ConfidenceLevel.GAP else "🟡 PARTIAL"
        entry = f"""
## {label} — {gap.detected_at.strftime('%Y-%m-%d %H:%M UTC')} — `{gap.id}`

**Question:** {gap.question}

**Confidence:** `{gap.confidence.value}` | **Retrieval score:** `{gap.retrieval_score:.3f}` | **Chunks found:** `{gap.chunk_count}`

**Reason:** {gap.reason}

**Suggestion:** {gap.suggestion}

**Status:** `{gap.status}`

---
"""
        with open(self.gaps_file, "a") as f:
            f.write(entry)

        # Append to machine-readable JSONL (for API reads)
        with open(self.gaps_jsonl, "a") as f:
            f.write(json.dumps(gap.model_dump(mode="json")) + "\n")

        logger.warning(
            "knowledge_gap_detected",
            gap_id=gap.id,
            confidence=gap.confidence.value,
            retrieval_score=gap.retrieval_score,
            question=gap.question[:80],
        )

    def list_gaps(self, status_filter: str | None = None) -> list[KnowledgeGap]:
        """Read all gaps from the JSONL file, optionally filtered by status."""
        if not self.gaps_jsonl.exists():
            return []

        gaps = []
        with open(self.gaps_jsonl) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    gap = KnowledgeGap(**data)
                    if status_filter is None or gap.status == status_filter:
                        gaps.append(gap)
                except Exception:
                    continue

        return gaps

    def resolve_gap(self, gap_id: str) -> bool:
        """
        Mark a gap as resolved (re-write JSONL with updated status).
        Call this when you've added docs and re-ingested.
        Returns True if found and updated, False if not found.
        """
        if not self.gaps_jsonl.exists():
            return False

        gaps = []
        found = False
        with open(self.gaps_jsonl) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("id") == gap_id:
                        data["status"] = "resolved"
                        data["resolved_at"] = datetime.now(timezone.utc).isoformat()
                        found = True
                    gaps.append(data)
                except Exception:
                    continue

        if found:
            with open(self.gaps_jsonl, "w") as f:
                for g in gaps:
                    f.write(json.dumps(g) + "\n")

        return found

    def gap_summary(self) -> dict:
        """Summary counts for the health check / UI status panel."""
        all_gaps = self.list_gaps()
        open_gaps = [g for g in all_gaps if g.status == "open"]
        return {
            "total": len(all_gaps),
            "open": len(open_gaps),
            "red_gaps": sum(1 for g in open_gaps if g.confidence == ConfidenceLevel.GAP),
            "yellow_partials": sum(1 for g in open_gaps if g.confidence == ConfidenceLevel.PARTIAL),
            "resolved": len(all_gaps) - len(open_gaps),
        }
