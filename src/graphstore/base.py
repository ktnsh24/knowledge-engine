"""
Graph store base interface.

🚚 The knowledge graph is the map the courier uses to navigate.
Without it, the courier wanders between unconnected topics.
With it, a question about "RAG" automatically surfaces
"Embeddings", "Vector Store", and "Retrieval" — 2 hops away.
"""
from abc import ABC, abstractmethod
from src.models import Topic, Relationship, KnowledgeGraph


class BaseGraphStore(ABC):

    @abstractmethod
    async def upsert_topic(self, topic: Topic) -> None:
        """Add or update a topic node."""
        ...

    @abstractmethod
    async def upsert_relationship(self, rel: Relationship) -> None:
        """Add or update a relationship edge."""
        ...

    @abstractmethod
    async def get_topic(self, topic_id: str) -> Topic | None:
        ...

    @abstractmethod
    async def get_connected_topics(self, topic_id: str, max_hops: int = 2) -> list[Topic]:
        """Traverse the graph to find related topics within N hops."""
        ...

    @abstractmethod
    async def get_all_topics(self) -> list[Topic]:
        ...

    @abstractmethod
    async def get_full_graph(self) -> KnowledgeGraph:
        """Return all topics and relationships for visualization."""
        ...

    @abstractmethod
    async def topic_count(self) -> int:
        ...
