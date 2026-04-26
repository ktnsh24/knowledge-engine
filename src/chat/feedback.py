"""
Feedback processor — the learning loop.

When you 👍 an answer → add Q&A pair to wiki as "Verified Answer"
When you 👎 an answer → flag topic for wiki improvement + add to eval set

🚚 Feedback is the courier's memory. Without it, the courier forgets every delivery.
With it, the courier remembers: "Last time someone asked about caching,
the short answer wasn't enough — give more detail next time."
"""
import json
from pathlib import Path
from datetime import datetime
from src.models import FeedbackSignal
from src.config import get_settings
import structlog

logger = structlog.get_logger()


class FeedbackProcessor:

    def __init__(self):
        settings = get_settings()
        self.feedback_path = Path(settings.wiki_output_path) / "feedback"
        self.feedback_path.mkdir(parents=True, exist_ok=True)
        self.eval_set_path = Path("scripts") / "golden-questions.yaml"

    async def process(self, feedback: FeedbackSignal) -> dict:
        """Process feedback signal — update wiki or flag for review."""
        result = {"action": "none", "message": ""}

        if feedback.thumbs_up:
            # Good answer → save as verified Q&A in wiki
            await self._save_verified_qa(feedback)
            result = {"action": "wiki_updated",
                      "message": "Answer saved to wiki as verified Q&A."}
            logger.info("feedback_positive", question=feedback.question[:50])
        else:
            # Bad answer → save to eval set as failing case
            await self._save_to_eval_set(feedback)
            result = {"action": "eval_set_updated",
                      "message": "Question added to evaluation set for improvement."}
            logger.warning("feedback_negative", question=feedback.question[:50],
                           correction=feedback.correction[:100] if feedback.correction else "")

        # Always save raw feedback
        await self._save_raw_feedback(feedback)
        return result

    async def _save_verified_qa(self, feedback: FeedbackSignal) -> None:
        """Append verified Q&A to wiki feedback log."""
        qa_file = self.feedback_path / "verified-answers.md"
        entry = f"""
## {feedback.timestamp.strftime('%Y-%m-%d %H:%M')} — Verified Answer

**Q:** {feedback.question}

**A:** {feedback.answer}

---
"""
        with open(qa_file, "a") as f:
            f.write(entry)

    async def _save_to_eval_set(self, feedback: FeedbackSignal) -> None:
        """Append failing question to golden questions YAML for future eval."""
        entry = f"""
  - question: "{feedback.question}"
    expected_topics: []
    correction: "{feedback.correction}"
    added_from_feedback: true
    added_at: "{feedback.timestamp.isoformat()}"
"""
        with open(self.eval_set_path, "a") as f:
            f.write(entry)

    async def _save_raw_feedback(self, feedback: FeedbackSignal) -> None:
        feedback_file = self.feedback_path / "raw-feedback.jsonl"
        with open(feedback_file, "a") as f:
            f.write(json.dumps(feedback.model_dump(mode="json")) + "\n")
