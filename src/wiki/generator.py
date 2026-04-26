"""
Wiki generator — reads graph + vector store, generates wiki pages with LLM.

🚚 The wiki generator is the courier that builds the road itself.
It reads all the scattered docs (raw materials), extracts topics (bricks),
finds connections (road layout), then asks the LLM to pave each section.
The more docs you add, the better the road becomes.
"""
import asyncio
from pathlib import Path
from src.llm.base import BaseLLM
from src.graphstore.base import BaseGraphStore
from src.vectorstore.base import BaseVectorStore
from src.models import WikiPage, Topic
from src.config import get_settings
import structlog

logger = structlog.get_logger()


class WikiGenerator:

    def __init__(self, llm: BaseLLM, vector_store: BaseVectorStore,
                 graph_store: BaseGraphStore):
        self.llm = llm
        self.vector_store = vector_store
        self.graph_store = graph_store
        settings = get_settings()
        self.output_path = Path(settings.wiki_output_path) / "topics"
        self.output_path.mkdir(parents=True, exist_ok=True)

    async def generate_all(self) -> list[WikiPage]:
        """Generate wiki pages for all topics in the graph."""
        topics = await self.graph_store.get_all_topics()
        logger.info("wiki_generation_started", topics=len(topics))

        pages = []
        for topic in topics:
            try:
                page = await self.generate_page(topic)
                pages.append(page)
                logger.info("wiki_page_generated", topic=topic.name)
            except Exception as e:
                logger.error("wiki_page_failed", topic=topic.name, error=str(e))

        await self._generate_index(pages)
        logger.info("wiki_generation_complete", pages=len(pages))
        return pages

    async def generate_page(self, topic: Topic) -> WikiPage:
        """Generate a single wiki page for a topic."""
        settings = get_settings()
        # Get relevant chunks from vector store
        # Use a wider net for wiki generation than for chat (need more context)
        wiki_top_k = max(settings.rag_top_k, 8)
        chunks = await self.vector_store.search(topic.name, top_k=wiki_top_k)
        context = "\n\n---\n\n".join([c.text for c in chunks])
        sources = list({c.source_file for c in chunks})

        # Get connected topics from graph
        connected = await self.graph_store.get_connected_topics(topic.id, max_hops=2)
        connected_names = [t.name for t in connected]

        # Ask LLM to generate the page
        result = await self.llm.generate_wiki_page(topic.name, context)
        content = result["content"]
        courier = result["courier_analogy"]

        # Add navigation footer
        if connected_names:
            footer = f"\n\n## 🔗 Connected Topics\n\n"
            footer += "\n".join(f"- [{t}]({t.lower().replace(' ', '-')}.md)" for t in connected_names)
            content += footer

        page = WikiPage(
            topic_id=topic.id,
            title=topic.name,
            content=content,
            courier_analogy=courier,
            sources=sources,
            connected_topics=[t.id for t in connected],
        )

        # Write to disk
        filename = f"{topic.id}.md"
        (self.output_path / filename).write_text(content, encoding="utf-8")
        return page

    async def _generate_index(self, pages: list[WikiPage]) -> None:
        """Generate the wiki index page."""
        lines = ["# 📚 Knowledge Engine Wiki\n",
                 "> Auto-generated from your AI portfolio repos. Gets smarter every time you use it.\n",
                 "\n## Topics\n"]
        for page in sorted(pages, key=lambda p: p.title):
            lines.append(f"- [{page.title}](topics/{page.topic_id}.md)")

        index = Path(self.output_path).parent / "index.md"
        index.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """CLI entry point for the wiki generator (poetry script `build-wiki`)."""
    import sys

    print("build-wiki: WikiGenerator must be invoked via the API or programmatically.", file=sys.stderr)
    print("See docs/architecture-and-design/api-routes/wiki-endpoint-explained.md", file=sys.stderr)
    sys.exit(0)
