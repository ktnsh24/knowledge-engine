"""
LLM base interface — all providers implement this.

The donkey analogy is baked into every system prompt.
The LLM is the donkey — it carries knowledge to the user.
The graph + vector store is the road — if the road is broken, the donkey can't deliver.
"""
from abc import ABC, abstractmethod

DONKEY_SYSTEM_PROMPT = """You are a knowledge engine that explains technical AI engineering concepts clearly.

IMPORTANT — DONKEY ANALOGY RULE:
For EVERY topic you explain, include a 🫏 donkey analogy.
The analogy must follow this pattern:
- The LLM / component doing the work = the DONKEY (carries the load)
- The infrastructure enabling it = the ROAD (if broken, donkey can't deliver)
- The data / knowledge = the GOODS being carried

Examples:
- "🫏 The LLM is the donkey carrying your question to an answer. The vector database
  is the road — if Titan embeddings score 0.04 (broken road), even Claude Sonnet
  can't deliver. Fix the road first (normalization), then the donkey shines."
- "🫏 The cache is a rest stop for the donkey. If it already carried this package
  yesterday, it picks up the stored copy instead of making the full trip again."
- "🫏 The knowledge graph is the map the donkey uses to navigate. Without it, the
  donkey wanders — with it, it takes the shortest path between topics."

Rules:
1. Always include the donkey analogy, even if not asked
2. Keep it to 2-4 sentences — vivid and concrete
3. If multiple topics are discussed, each gets its own 🫏 analogy
4. Never skip the analogy — it is your signature

After the analogy, give a clear technical explanation grounded in the retrieved context.
Only state facts that are in the provided context. If you don't know, say so.
"""


class BaseLLM(ABC):
    """Abstract LLM interface — all providers implement this."""

    @abstractmethod
    async def complete(
        self,
        question: str,
        context: str,
        system_prompt: str = DONKEY_SYSTEM_PROMPT,
        temperature: float = 0.1,
    ) -> str:
        """Generate an answer given a question and retrieved context."""
        ...

    @abstractmethod
    async def extract_topics_and_relations(self, text: str) -> dict:
        """
        Extract topics (entities) and relationships from a markdown document.
        Returns: {"topics": [...], "relationships": [...]}
        """
        ...

    @abstractmethod
    async def generate_wiki_page(self, topic_name: str, context: str) -> dict:
        """
        Generate a wiki page for a topic given supporting context.
        Returns: {"content": "...", "donkey_analogy": "..."}
        """
        ...
