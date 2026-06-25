"""Ollama LLM client using LangChain ChatOllama."""
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel
from lib.config import settings


def get_llm(temperature: float = 0.1) -> BaseChatModel:
    """Return a ChatOllama instance configured for the hotel model."""
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_api_url,
        temperature=temperature,
    )