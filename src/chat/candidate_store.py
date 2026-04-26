"""
Candidate store — LLM-generated answers waiting for human review.

When a question has GAP confidence (no docs cover it), the LLM answers from
its training knowledge. That answer is saved here as a CANDIDATE — not trusted
yet, not discarded either.

You review it:
  👍 Promote  → saved to wiki/feedback/verified-answers.md
              → next /ingest/run picks it up, chunks it, embeds it
              → future identical questions are answered from YOUR docs (not LLM training)
              → gap closes itself over time
  👎 Discard  → question stays open in gaps, candidate removed

🚚 The candidate store is the courier's notebook:
   "I couldn't find a road for this trip, so I made one up.
   Check if my route is correct before I draw it on the official map."
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from src.models import WikiCandidate
from src.config import get_settings
import structlog

logger = structlog.get_logger()


class CandidateStore:
    """Stores LLM-generated candidate answers for human review."""

    def __init__(self):
        settings = get_settings()
        self.candidates_path = Path(settings.wiki_output_path) / "candidates"
        self.candidates_path.mkdir(parents=True, exist_ok=True)
        self.candidates_jsonl = self.candidates_path / "candidates.jsonl"
        self.candidates_md = self.candidates_path / "pending-review.md"
        # Verified answers file — same one FeedbackProcessor uses for 👍
        self.verified_answers_path = Path(settings.wiki_output_path) / "feedback" / "verified-answers.md"
        self.verified_answers_path.parent.mkdir(parents=True, exist_ok=True)

    async def save_candidate(self, question: str, answer: str, courier_analogy: str,
                              gap_id: str) -> WikiCandidate:
        """Save an LLM-generated answer as a pending candidate."""
        candidate = WikiCandidate(
            id=str(uuid.uuid4())[:8],
            question=question,
            answer=answer,
            courier_analogy=courier_analogy,
            gap_id=gap_id,
        )

        # Append to JSONL (machine-readable)
        with open(self.candidates_jsonl, "a") as f:
            f.write(json.dumps(candidate.model_dump(mode="json")) + "\n")

        # Append to markdown (human-readable review doc)
        entry = f"""
## 🔵 CANDIDATE `{candidate.id}` — {candidate.created_at.strftime('%Y-%m-%d %H:%M UTC')}

> ⚠️ This answer comes from LLM training knowledge — **NOT from your docs**.
> Review it carefully. Promote if correct, discard if wrong.

**Question:** {candidate.question}

**Answer:**
{candidate.answer}

**Courier Analogy:** {candidate.courier_analogy}

**Gap ID:** `{candidate.gap_id}` | **Status:** `{candidate.status}`

To promote: `DELETE /wiki/candidates/{candidate.id}/promote`
To discard:  `DELETE /wiki/candidates/{candidate.id}/discard`

---
"""
        with open(self.candidates_md, "a") as f:
            f.write(entry)

        logger.info("candidate_saved", candidate_id=candidate.id,
                    question=question[:80], gap_id=gap_id)
        return candidate

    async def promote(self, candidate_id: str) -> WikiCandidate | None:
        """
        Promote a candidate to verified knowledge.

        Writes the Q&A to verified-answers.md — same file 👍 feedback uses.
        Next time /ingest/run is called, this becomes part of the knowledge base.
        """
        candidate = self._find(candidate_id)
        if not candidate or candidate.status != "pending":
            return None

        # Write to verified answers (same format as FeedbackProcessor._save_verified_qa)
        entry = f"""
## {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} — Promoted Candidate `{candidate_id}`

> Source: LLM knowledge (was a knowledge gap — promoted after human review)

**Q:** {candidate.question}

**A:** {candidate.answer}

---
"""
        with open(self.verified_answers_path, "a") as f:
            f.write(entry)

        # Update status in JSONL
        candidate.status = "promoted"
        candidate.promoted_at = datetime.now(timezone.utc)
        self._update_status(candidate_id, "promoted")

        logger.info("candidate_promoted", candidate_id=candidate_id,
                    question=candidate.question[:80])
        return candidate

    async def discard(self, candidate_id: str) -> WikiCandidate | None:
        """Discard a candidate — it was wrong. Gap stays open."""
        candidate = self._find(candidate_id)
        if not candidate or candidate.status != "pending":
            return None

        self._update_status(candidate_id, "discarded")
        logger.info("candidate_discarded", candidate_id=candidate_id)
        return candidate

    def list_candidates(self, status_filter: str | None = "pending") -> list[WikiCandidate]:
        """List candidates, optionally filtered by status."""
        if not self.candidates_jsonl.exists():
            return []

        candidates = []
        with open(self.candidates_jsonl) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    c = WikiCandidate(**data)
                    if status_filter is None or c.status == status_filter:
                        candidates.append(c)
                except Exception:
                    continue
        return candidates

    def summary(self) -> dict:
        """Summary counts for the UI status panel."""
        all_candidates = self.list_candidates(status_filter=None)
        return {
            "pending": sum(1 for c in all_candidates if c.status == "pending"),
            "promoted": sum(1 for c in all_candidates if c.status == "promoted"),
            "discarded": sum(1 for c in all_candidates if c.status == "discarded"),
            "total": len(all_candidates),
        }

    def _find(self, candidate_id: str) -> WikiCandidate | None:
        for c in self.list_candidates(status_filter=None):
            if c.id == candidate_id:
                return c
        return None

    def _update_status(self, candidate_id: str, new_status: str) -> None:
        if not self.candidates_jsonl.exists():
            return
        rows = []
        with open(self.candidates_jsonl) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("id") == candidate_id:
                        data["status"] = new_status
                        if new_status == "promoted":
                            data["promoted_at"] = datetime.now(timezone.utc).isoformat()
                    rows.append(data)
                except Exception:
                    continue
        with open(self.candidates_jsonl, "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
