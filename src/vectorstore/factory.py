"""Factory — returns the right vector store for the configured provider."""
from src.config import get_settings, CloudProvider
from src.vectorstore.base import BaseVectorStore


def create_vector_store() -> BaseVectorStore:
    settings = get_settings()
    if settings.cloud_provider == CloudProvider.AWS:
        from src.vectorstore.dynamodb import DynamoDBVectorStore
        return DynamoDBVectorStore()
    elif settings.cloud_provider == CloudProvider.AZURE:
        from src.vectorstore.azure_search import AzureSearchVectorStore
        return AzureSearchVectorStore()
    else:
        from src.vectorstore.chroma import ChromaVectorStore
        return ChromaVectorStore()
