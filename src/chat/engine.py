"""
GraphRAG chat engine — combines vector search + graph traversal.

🫏 The chat engine is the donkey's dispatcher:
  1. Vector store (road map) finds the most relevant chunks
  2. Graph store (network map) expands context to connected topics
  3. Gap detector checks if the road exists at all — marks broken roads
  4. LLM (donkey) carries all of it to a final answer
  Without step 2, the donkey only knows about the street it's on.
  With step 2, it knows the whole city.
  With step 3, it knows which streets are missing entirely.
"""
import time
from src.llm.base import BaseLLM
from src.graphstore.base import BaseGraphStore
from src.vectorstore.base import BaseVectorStore
from src.chat.gap_detector import GapDetector
from src.models import ChatRequest, ChatResponse, ConfidenceLevel, ProviderType
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

    async def answer(self, request: ChatRequest) -> ChatResponse:
        start = time.monotonic()

        # Step 1: Vector search — find relevant chunks
        chunks = await self.vector_store.search(request.question, top_k=5)
        chunk_texts = [c.text for c in chunks]
        sources = list({c.source_file for c in chunks})

        # Step 2: Graph expansion — find connected topics
        topic_ids = list({tid for c in chunks for tid in c.topic_ids})
        connected_topics = []
        for tid in topic_ids[:3]:  # limit graph traversal
            neighbours = await self.graph_store.get_connected_topics(tid, max_hops=2)
            connected_topics.extend(neighbours)

        # Step 3: Gap detection — check if road exists
        top_score = chunks[0].embedding[0] if chunks and chunks[0].embedding else 0.0
        gap = self.gap_detector.assess_confidence(
            question=request.question,
            top_retrieval_score=top_score,
            chunk_count=len(chunks),
            topic_count=len(connected_topics),
        )
        if gap.confidence != ConfidenceLevel.HIGH:
            await self.gap_detector.save_gap(gap)

        # Step 4: Build enriched context
        topic_names = list({t.name for t in connected_topics})
        topic_context = ""
        if topic_names:
            topic_context = f"\n\nRELATED TOPICS (from knowledge graph): {', '.join(topic_names)}"

        # Add gap warning to context so LLM knows its coverage is thin
        gap_notice = ""
        if gap.confidence == ConfidenceLevel.GAP:
            gap_notice = "\n\n[NOTE: Coverage for this question is very thin. Acknowledge the knowledge gap honestly.]"
        elif gap.confidence == ConfidenceLevel.PARTIAL:
            gap_notice = "\n\n[NOTE: Coverage for this question is partial. Be explicit about what you do and don't know.]"

        context = "\n\n---\n\n".join(chunk_texts) + topic_context + gap_notice

        # Step 5: LLM generates answer (donkey analogy baked into system prompt)
        answer = await self.llm.complete(request.question, context)

        # Step 6: Extract donkey analogy from response
        donkey_start = answer.find("🫏")
        donkey_end = answer.find("\n", donkey_start + 1) if donkey_start != -1 else -1
        donkey = answer[donkey_start:donkey_end].strip() if donkey_start != -1 else "🫏 The LLM is the donkey carrying your question to an answer."

        latency = int((time.monotonic() - start) * 1000)
        logger.info("chat_answered", question=request.question[:50],
                    chunks=len(chunks), topics=len(topic_ids),
                    confidence=gap.confidence.value, latency_ms=latency)

        return ChatResponse(
            answer=answer,
            donkey_analogy=donkey,
            sources=sources,
            topics=topic_names,
            retrieval_score=top_score,
            latency_ms=latency,
            provider=ProviderType(get_settings().cloud_provider.value),
            session_id=request.session_id,
            confidence=gap.confidence,
            is_gap=gap.confidence != ConfidenceLevel.HIGH,
            gap_id=gap.id if gap.confidence != ConfidenceLevel.HIGH else None,
            gap_reason=gap.reason if gap.confidence != ConfidenceLevel.HIGH else "",
            gap_suggestion=gap.suggestion if gap.confidence != ConfidenceLevel.HIGH else "",
        )
