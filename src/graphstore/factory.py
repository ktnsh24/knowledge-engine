"""Factory — returns the right graph store for the configured provider."""
from src.config import get_settings, CloudProvider
from src.graphstore.base import BaseGraphStore


def create_graph_store() -> BaseGraphStore:
    settings = get_settings()
    if settings.cloud_provider == CloudProvider.AWS:
        from src.graphstore.dynamodb_graph import DynamoDBGraphStore
        return DynamoDBGraphStore()
    elif settings.cloud_provider == CloudProvider.AZURE:
        from src.graphstore.cosmos_graph import CosmosGraphStore
        return CosmosGraphStore()
    else:
        from src.graphstore.neo4j_store import Neo4jGraphStore
        return Neo4jGraphStore()
