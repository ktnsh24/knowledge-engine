"""
DynamoDB graph store — AWS provider.
Stores the graph as adjacency lists (topics table + edges table).
No Neptune needed — keeps costs under €1/run.

🚚 DynamoDB is the road map printed on paper — not as fast as a GPS (Neo4j),
but it gets the courier to the destination without renting a car.
"""
import boto3
from src.graphstore.base import BaseGraphStore
from src.models import Topic, Relationship, KnowledgeGraph
from src.config import get_settings


class DynamoDBGraphStore(BaseGraphStore):

    def __init__(self):
        settings = get_settings()
        self.dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
        self.topics_table = self.dynamodb.Table(f"{settings.dynamodb_graph_table}-topics")
        self.edges_table = self.dynamodb.Table(f"{settings.dynamodb_graph_table}-edges")

    async def upsert_topic(self, topic: Topic) -> None:
        import asyncio
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.topics_table.put_item(Item={
                "topic_id": topic.id,
                "name": topic.name,
                "description": topic.description,
                "source_repos": topic.source_repos,
            })
        )

    async def upsert_relationship(self, rel: Relationship) -> None:
        import asyncio
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.edges_table.put_item(Item={
                "edge_id": f"{rel.source_id}#{rel.relation_type}#{rel.target_id}",
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "relation_type": rel.relation_type,
                "weight": str(rel.weight),
                "evidence": rel.evidence,
            })
        )

    async def get_topic(self, topic_id: str) -> Topic | None:
        import asyncio
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.topics_table.get_item(Key={"topic_id": topic_id})
        )
        item = result.get("Item")
        if not item:
            return None
        return Topic(id=item["topic_id"], name=item["name"],
                     description=item.get("description", ""),
                     source_repos=item.get("source_repos", []))

    async def get_connected_topics(self, topic_id: str, max_hops: int = 2) -> list[Topic]:
        import asyncio
        from boto3.dynamodb.conditions import Attr
        # Get direct neighbours (hop 1)
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.edges_table.scan(
                FilterExpression=Attr("source_id").eq(topic_id) | Attr("target_id").eq(topic_id)
            )
        )
        neighbour_ids = set()
        for item in result.get("Items", []):
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
        import asyncio
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.topics_table.scan()
        )
        return [Topic(id=i["topic_id"], name=i["name"],
                      description=i.get("description", ""))
                for i in result.get("Items", [])]

    async def get_full_graph(self) -> KnowledgeGraph:
        import asyncio
        topics = await self.get_all_topics()
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.edges_table.scan()
        )
        rels = [Relationship(
            source_id=i["source_id"], target_id=i["target_id"],
            relation_type=i["relation_type"],
            weight=float(i.get("weight", 1.0)),
            evidence=i.get("evidence", ""),
        ) for i in result.get("Items", [])]
        return KnowledgeGraph(topics=topics, relationships=rels)

    async def topic_count(self) -> int:
        topics = await self.get_all_topics()
        return len(topics)
