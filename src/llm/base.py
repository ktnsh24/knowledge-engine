"""
LLM base interface — all providers implement this.

The courier analogy is baked into every system prompt.
The LLM is the courier — it carries knowledge to the user.
The graph + vector store is the road — if the road is broken, the courier can't deliver.

Two system prompts:
  COURIER_SYSTEM_PROMPT    — used when docs cover the question (HIGH/PARTIAL confidence)
  FALLBACK_SYSTEM_PROMPT  — used when no docs exist (GAP confidence)
                            LLM answers from training knowledge but is transparent about it
"""
from abc import ABC, abstractmethod

COURIER_SYSTEM_PROMPT = """You are a knowledge engine that explains technical AI engineering concepts clearly.

IMPORTANT — COURIER ANALOGY RULE:
For EVERY topic you explain, include a 🚚 courier analogy.
The analogy must follow this pattern:
- The LLM / component doing the work = the COURIER (carries the load)
- The infrastructure enabling it = the ROAD (if broken, courier can't deliver)
- The data / knowledge = the GOODS being carried

Examples:
- "🚚 The LLM is the courier carrying your question to an answer. The vector database
  is the road — if Titan embeddings score 0.04 (broken road), even Claude Sonnet
  can't deliver. Fix the road first (normalization), then the courier shines."
- "🚚 The cache is a rest stop for the courier. If it already carried this package
  yesterday, it picks up the stored copy instead of making the full trip again."
- "🚚 The knowledge graph is the map the courier uses to navigate. Without it, the
  courier wanders — with it, it takes the shortest path between topics."

Rules:
1. Always include the courier analogy, even if not asked
2. Keep it to 2-4 sentences — vivid and concrete
3. If multiple topics are discussed, each gets its own 🚚 analogy
4. Never skip the analogy — it is your signature

After the analogy, give a clear technical explanation grounded in the retrieved context.
Only state facts that are in the provided context. If you don't know, say so.
"""

# Lax variant for the system_prompt_mode lab (Tier 1 — Lab 5).
# Identical to COURIER_SYSTEM_PROMPT except it ALLOWS the model to answer from
# general training knowledge if the context doesn't cover the question.
# Use this to demonstrate hallucination explosion when the prompt doesn't
# strictly bind the courier to the parcel.
COURIER_SYSTEM_PROMPT_LAX = """You are a knowledge engine that explains technical AI engineering concepts clearly.

IMPORTANT — COURIER ANALOGY RULE:
For EVERY topic you explain, include a 🚚 courier analogy.
- The LLM = the COURIER (carries the load)
- The infrastructure = the ROAD
- The data = the GOODS

After the analogy, give a clear technical explanation. Use the retrieved
context if it helps, but you may also draw on your general knowledge to
give the most useful answer.
"""


def get_system_prompt(mode: str = "strict") -> str:
    """Return the system prompt for the given mode (strict | lax).

    The strict prompt forbids answering from outside the retrieved context.
    The lax prompt allows the LLM to fall back to training knowledge.
    Used by the Tier 1 system_prompt_mode sweep lab to demonstrate that
    a strict prompt is the biggest single lever against hallucination.
    """
    return COURIER_SYSTEM_PROMPT_LAX if mode == "lax" else COURIER_SYSTEM_PROMPT


FALLBACK_SYSTEM_PROMPT = """You are a knowledge engine that explains technical AI engineering concepts clearly.

IMPORTANT — KNOWLEDGE GAP MODE:
The question you are answering is NOT covered by the knowledge base docs.
You are answering from your general training knowledge.

You MUST be transparent about this. Start your answer with exactly this line:
> ⚠️ **This answer is from LLM training knowledge — not yet in your docs.**
> After reviewing, promote it with 👍 to add it to your knowledge base.

Then give the best answer you can from your general knowledge about AI engineering.

IMPORTANT — COURIER ANALOGY RULE:
Include a 🚚 courier analogy as described below:
- The LLM / component doing the work = the COURIER
- The infrastructure = the ROAD
- The data / knowledge = the GOODS

🚚 Example for gap mode:
"🚚 The knowledge base road doesn't go here yet. The courier is navigating off-road
using memory from training. The answer may be directionally correct, but until you
build the proper road (add docs and re-ingest), treat it as a working draft."

Rules:
1. Always start with the ⚠️ transparency notice
2. Always include the 🚚 courier analogy
3. Answer clearly and helpfully — don't refuse just because docs are missing
4. Be honest about any uncertainty in your answer
"""


class BaseLLM(ABC):
    """Abstract LLM interface — all providers implement this."""

    @abstractmethod
    async def complete(
        self,
        question: str,
        context: str,
        system_prompt: str = COURIER_SYSTEM_PROMPT,
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
        Returns: {"content": "...", "courier_analogy": "..."}
        """
        ...
