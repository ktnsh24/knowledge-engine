"""
GraphRAG chat engine — combines vector search + graph traversal + fallback.

🚚 The chat engine is the courier's dispatcher:
  1. Vector store finds the most relevant chunks
  2. Graph store expands context to connected topics
  3. Gap detector checks confidence: HIGH / PARTIAL / GAP
  4. HIGH/PARTIAL  → LLM answers from docs (grounded)
     GAP           → LLM answers from training knowledge (fallback)
                   → answer saved as CANDIDATE for human review
                   → promote with 👍 → answer joins docs → gap closes
  Without step 3+4, the courier silently answers from memory and you never know.
  With step 3+4, the courier marks the broken road AND still delivers — honestly.
"""
import time
from src.llm.base import (
    BaseLLM,
    COURIER_SYSTEM_PROMPT,
    FALLBACK_SYSTEM_PROMPT,
    get_system_prompt,
)
from src.graphstore.base import BaseGraphStore
from src.vectorstore.base import BaseVectorStore
from src.chat.gap_detector import GapDetector
from src.chat.candidate_store import CandidateStore
from src.models import (
    ChatRequest, ChatResponse, ConfidenceLevel, AnswerSource, ProviderType
)
from src.config import get_settings
import structlog

logger = structlog.get_logger()


class ChatEngine:

    def __init__(self, llm: BaseLLM, vector_store: BaseVectorStore,
                 graph_store: BaseGraphStore):
        self.llm = llm
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.gap_detector = GapDetector()
        self.candidate_store = CandidateStore()

    async def answer(self, request: ChatRequest) -> ChatResponse:
        start = time.monotonic()
        settings = get_settings()

        # Step 1: Vector search — find relevant chunks
        chunks = await self.vector_store.search(request.question, top_k=settings.rag_top_k)
        chunk_texts = [c.text for c in chunks]
        sources = list({c.source_file for c in chunks})

        # Step 2: Graph expansion — find connected topics
        topic_ids = list({tid for c in chunks for tid in c.topic_ids})
        connected_topics = []
        for tid in topic_ids[:3]:
            neighbours = await self.graph_store.get_connected_topics(tid, max_hops=2)
            connected_topics.extend(neighbours)

        # Step 3: Gap detection — assess confidence
        top_score = chunks[0].embedding[0] if chunks and chunks[0].embedding else 0.0
        gap = self.gap_detector.assess_confidence(
            question=request.question,
            top_retrieval_score=top_score,
            chunk_count=len(chunks),
            topic_count=len(connected_topics),
        )
        if gap.confidence != ConfidenceLevel.HIGH:
            await self.gap_detector.save_gap(gap)

        topic_names = list({t.name for t in connected_topics})
        candidate_id = None
        answer_source = AnswerSource.DOCS

        # Step 4: Route to correct answer strategy
        if gap.confidence == ConfidenceLevel.GAP:
            # ── FALLBACK MODE ─────────────────────────────────────────────
            # No meaningful docs found — LLM answers from training knowledge.
            # Answer is saved as a candidate awaiting human review.
            answer_source = AnswerSource.LLM_KNOWLEDGE
            answer_text = await self.llm.complete(
                question=request.question,
                context="",  # no doc context — pure LLM knowledge
                system_prompt=FALLBACK_SYSTEM_PROMPT,
                temperature=settings.llm_temperature,
            )
            candidate = await self.candidate_store.save_candidate(
                question=request.question,
                answer=answer_text,
                courier_analogy=_extract_courier(answer_text),
                gap_id=gap.id,
            )
            candidate_id = candidate.id
            logger.info("chat_fallback_answer", question=request.question[:50],
                        candidate_id=candidate_id, gap_id=gap.id)

        else:
            # ── GROUNDED MODE (HIGH or PARTIAL) ───────────────────────────
            # Docs found — build enriched context and answer from them.
            answer_source = (
                AnswerSource.DOCS if gap.confidence == ConfidenceLevel.HIGH
                else AnswerSource.DOCS_PARTIAL
            )
            topic_context = ""
            if topic_names:
                topic_context = f"\n\nRELATED TOPICS (from knowledge graph): {', '.join(topic_names)}"

            gap_notice = ""
            if gap.confidence == ConfidenceLevel.PARTIAL:
                gap_notice = (
                    "\n\n[NOTE: Coverage for this question is partial. "
                    "Be explicit about what you do and don't know from the context.]"
                )

            context = "\n\n---\n\n".join(chunk_texts) + topic_context + gap_notice
            answer_text = await self.llm.complete(
                question=request.question,
                context=context,
                system_prompt=get_system_prompt(settings.system_prompt_mode),
                temperature=settings.llm_temperature,
            )

        latency = int((time.monotonic() - start) * 1000)
        logger.info("chat_answered", question=request.question[:50],
                    chunks=len(chunks), topics=len(topic_ids),
                    confidence=gap.confidence.value,
                    answer_source=answer_source.value,
                    latency_ms=latency)

        return ChatResponse(
            answer=answer_text,
            courier_analogy=_extract_courier(answer_text),
            sources=sources,
            topics=topic_names,
            retrieval_score=top_score,
            latency_ms=latency,
            provider=ProviderType(get_settings().cloud_provider.value),
            session_id=request.session_id,
            confidence=gap.confidence,
            is_gap=gap.confidence == ConfidenceLevel.GAP,
            gap_id=gap.id if gap.confidence != ConfidenceLevel.HIGH else None,
            gap_reason=gap.reason if gap.confidence != ConfidenceLevel.HIGH else "",
            gap_suggestion=gap.suggestion if gap.confidence != ConfidenceLevel.HIGH else "",
            answer_source=answer_source,
            candidate_id=candidate_id,
        )


def _extract_courier(answer: str) -> str:
    """Extract the 🚚 courier analogy line from an answer."""
    start = answer.find("🚚")
    if start == -1:
        return "🚚 The LLM is the courier carrying your question to an answer."
    end = answer.find("\n", start + 1)
    return answer[start:end].strip() if end != -1 else answer[start:].strip()
