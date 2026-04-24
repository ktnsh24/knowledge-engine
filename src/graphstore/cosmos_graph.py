"""
Azure Cosmos DB graph store — Azure provider.

Uses Cosmos DB NoSQL API with adjacency list pattern.
Two containers: 'topics' and 'edges' — same pattern as DynamoDB graph store.
No Gremlin/Graph API needed (saves cost and complexity).

🫏 Cosmos DB is the donkey's cross-border road map — it works globally,
auto-scales, and the donkey never gets stuck at a traffic jam.
"""
import asyncio
from azure.cosmos.aio import CosmosClient
from src.graphstore.base import BaseGraphStore
from src.models import Topic, Relationship, KnowledgeGraph
from src.config import get_settings
import structlog

logger = structlog.get_logger()


class CosmosGraphStore(BaseGraphStore):

    def __init__(self):
        settings = get_settings()
        self._settings = settings
        self.client = CosmosClient(
            url=settings.azure_cosmos_endpoint,
            credential=settings.azure_cosmos_key,
        )
        self._db = None
        self._topics = None
        self._edges = None

    async def _ensure_containers(self):
        if self._topics is not None:
            return
        db = self.client.get_database_client(self._settings.azure_cosmos_database)
        self._topics = db.get_container_client("topics")
        self._edges = db.get_container_client("edges")

    async def upsert_topic(self, topic: Topic) -> None:
        await self._ensure_containers()
        await self._topics.upsert_item({
            "id": topic.id,
            "name": topic.name,
            "description": topic.description,
            "source_repos": topic.source_repos,
        })

    async def upsert_relationship(self, rel: Relationship) -> None:
        await self._ensure_containers()
        edge_id = f"{rel.source_id}__{rel.relation_type}__{rel.target_id}"
        await self._edges.upsert_item({
            "id": edge_id,
            "source_id": rel.source_id,
            "target_id": rel.target_id,
            "relation_type": rel.relation_type,
            "weight": rel.weight,
            "evidence": rel.evidence,
        })

    async def get_topic(self, topic_id: str) -> Topic | None:
        await self._ensure_containers()
        try:
            item = await self._topics.read_item(item=topic_id, partition_key=topic_id)
            return Topic(id=item["id"], name=item["name"],
                         description=item.get("description", ""),
                         source_repos=item.get("source_repos", []))
        except Exception:
            return None

    async def get_connected_topics(self, topic_id: str, max_hops: int = 2) -> list[Topic]:
        await self._ensure_containers()
        query = (
            "SELECT * FROM c WHERE c.source_id = @id OR c.target_id = @id"
        )
        items = [item async for item in self._edges.query_items(
            query=query,
            parameters=[{"name": "@id", "value": topic_id}],
        )]
        neighbour_ids = set()
        for item in items:
            if item["source_id"] != topic_id:
                neighbour_ids.add(item["source_id"])
            if item["target_id"] != topic_id:
                neighbour_ids.add(item["target_id"])

        topics = []
        for nid in neighbour_ids:
            t = await self.get_topic(nid)
            if t:
                topics.append(t)
        return topics

    async def get_all_topics(self) -> list[Topic]:
        await self._ensure_containers()
        items = [item async for item in self._topics.query_items("SELECT * FROM c")]
        return [Topic(id=i["id"], name=i["name"],
                      description=i.get("description", ""),
                      source_repos=i.get("source_repos", []))
                for i in items]

    async def get_full_graph(self) -> KnowledgeGraph:
        await self._ensure_containers()
        topics = await self.get_all_topics()
        edge_items = [item async for item in self._edges.query_items("SELECT * FROM c")]
        rels = [Relationship(
            source_id=i["source_id"], target_id=i["target_id"],
            relation_type=i["relation_type"],
            weight=float(i.get("weight", 1.0)),
            evidence=i.get("evidence", ""),
        ) for i in edge_items]
        return KnowledgeGraph(topics=topics, relationships=rels)

    async def topic_count(self) -> int:
        topics = await self.get_all_topics()
        return len(topics)

    async def close(self):
        await self.client.close()
