"""
Neo4j graph store — local provider via Docker.
Production-grade graph DB for development and testing.
"""
from neo4j import AsyncGraphDatabase
from src.graphstore.base import BaseGraphStore
from src.models import Topic, Relationship, KnowledgeGraph
from src.config import get_settings
import structlog

logger = structlog.get_logger()


class Neo4jGraphStore(BaseGraphStore):

    def __init__(self):
        settings = get_settings()
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    async def upsert_topic(self, topic: Topic) -> None:
        async with self.driver.session() as session:
            await session.run(
                """MERGE (t:Topic {id: $id})
                   SET t.name = $name,
                       t.description = $description,
                       t.source_repos = $source_repos,
                       t.updated_at = datetime()""",
                id=topic.id, name=topic.name,
                description=topic.description,
                source_repos=topic.source_repos,
            )

    async def upsert_relationship(self, rel: Relationship) -> None:
        async with self.driver.session() as session:
            await session.run(
                f"""MATCH (a:Topic {{id: $src}}), (b:Topic {{id: $tgt}})
                    MERGE (a)-[r:{rel.relation_type}]->(b)
                    SET r.weight = $weight, r.evidence = $evidence""",
                src=rel.source_id, tgt=rel.target_id,
                weight=rel.weight, evidence=rel.evidence,
            )

    async def get_topic(self, topic_id: str) -> Topic | None:
        async with self.driver.session() as session:
            result = await session.run(
                "MATCH (t:Topic {id: $id}) RETURN t", id=topic_id
            )
            record = await result.single()
            if not record:
                return None
            node = record["t"]
            return Topic(id=node["id"], name=node["name"],
                         description=node.get("description", ""),
                         source_repos=list(node.get("source_repos", [])))

    async def get_connected_topics(self, topic_id: str, max_hops: int = 2) -> list[Topic]:
        async with self.driver.session() as session:
            result = await session.run(
                f"""MATCH (start:Topic {{id: $id}})-[*1..{max_hops}]-(connected:Topic)
                    WHERE connected.id <> $id
                    RETURN DISTINCT connected""",
                id=topic_id,
            )
            topics = []
            async for record in result:
                node = record["connected"]
                topics.append(Topic(id=node["id"], name=node["name"],
                                    description=node.get("description", "")))
            return topics

    async def get_all_topics(self) -> list[Topic]:
        async with self.driver.session() as session:
            result = await session.run("MATCH (t:Topic) RETURN t")
            topics = []
            async for record in result:
                node = record["t"]
                topics.append(Topic(id=node["id"], name=node["name"],
                                    description=node.get("description", "")))
            return topics

    async def get_full_graph(self) -> KnowledgeGraph:
        topics = await self.get_all_topics()
        async with self.driver.session() as session:
            result = await session.run(
                "MATCH (a:Topic)-[r]->(b:Topic) RETURN a.id, type(r), b.id, r.weight, r.evidence"
            )
            rels = []
            async for record in result:
                rels.append(Relationship(
                    source_id=record["a.id"], target_id=record["b.id"],
                    relation_type=record["type(r)"],
                    weight=record.get("r.weight", 1.0),
                    evidence=record.get("r.evidence", ""),
                ))
        return KnowledgeGraph(topics=topics, relationships=rels)

    async def topic_count(self) -> int:
        async with self.driver.session() as session:
            result = await session.run("MATCH (t:Topic) RETURN count(t) AS c")
            record = await result.single()
            return record["c"] if record else 0

    async def close(self):
        await self.driver.close()
