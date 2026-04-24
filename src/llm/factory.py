"""Factory — returns the right LLM for the configured provider."""
from src.config import get_settings, CloudProvider
from src.llm.base import BaseLLM


def create_llm() -> BaseLLM:
    settings = get_settings()
    if settings.cloud_provider == CloudProvider.AWS:
        from src.llm.bedrock import BedrockLLM
        return BedrockLLM()
    elif settings.cloud_provider == CloudProvider.AZURE:
        from src.llm.azure_openai import AzureOpenAILLM
        return AzureOpenAILLM()
    else:
        from src.llm.ollama import OllamaLLM
        return OllamaLLM()
