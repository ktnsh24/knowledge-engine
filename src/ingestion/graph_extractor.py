"""
Graph topic + relationship extractor — uses LLM to find entities in markdown.
"""
from pathlib import Path
from src.llm.base import BaseLLM
from src.graphstore.base import BaseGraphStore
from src.models import Topic, Relationship
import structlog

logger = structlog.get_logger()


async def extract_and_store(text: str, graph_store: BaseGraphStore, llm: BaseLLM) -> dict:
    """Extract topics and relationships from text and store them in the graph."""
    result = await llm.extract_topics_and_relations(text)
    topics = result.get("topics", [])
    relationships = result.get("relationships", [])

    topic_ids = set()
    for t in topics:
        topic = Topic(id=t["id"], name=t["name"], description=t.get("description", ""))
        await graph_store.upsert_topic(topic)
        topic_ids.add(t["id"])

    rel_count = 0
    for r in relationships:
        # Only add relationships where both endpoints exist
        if r["source_id"] in topic_ids and r["target_id"] in topic_ids:
            rel = Relationship(
                source_id=r["source_id"],
                target_id=r["target_id"],
                relation_type=r.get("relation_type", "RELATED_TO"),
                evidence=r.get("evidence", ""),
            )
            await graph_store.upsert_relationship(rel)
            rel_count += 1

    logger.info("graph_extracted", topics=len(topics), relationships=rel_count)
    return {"topics": len(topics), "relationships": rel_count}
