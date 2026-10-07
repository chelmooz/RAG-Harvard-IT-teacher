"""Tests G2-T05 — RAG Engine adaptation to use LlamaCppClient.

Contrat (ticket 05 + GO XZ) :
- RAGEngine reçoit un LLMClient injecté (via dépendances) et ne crée
  aucun client Ollama en interne.
- Les méthodes generate, check_llm_health, close délèguent au client
  LLM injecté.
- Aucun paramètre Ollama (host, model) n'est lu dans RAGEngine.
- Aucun LLAMA_MODEL n'est introduit.
- Le comportement RAG (retrieval, indexation) reste fondé sur les
  dépendances injectées (EmbeddingProvider, pool DB).

TDD : ces tests sont écrits avant de vérifier l'état actuel (devrait
être GREEN si l'adaptation T04/T05 est correcte).
"""
from unittest.mock import AsyncMock

import pytest

from api.rag_engine import RAGEngine
from api.dependencies import LlamaCppClient


class DummyEmbeddingProvider:
    """EmbeddingProvider factice pour les tests."""

    async def encode(self, texts):
        # retourne un tableau de shape (len(texts), 1024) filled with 0.5
        import numpy as np
        return np.full((len(texts), 1024), 0.5, dtype=np.float32)

    async def encode_single(self, text):
        return await self.encode([text])

    @property
    def batch_size(self):
        return 32


@pytest.fixture
def dummy_embedding_provider():
    return DummyEmbeddingProvider()


@pytest.fixture
def dummy_llm_client():
    """LLMClient factice qui enregistre les appels."""
    client = AsyncMock()
    client.generate = AsyncMock(return_value="Réponse factice")
    client.check_health = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


def test_construction_reussit(dummy_embedding_provider):
    """RAGEngine peut être construit avec des dépendances factices."""
    from unittest.mock import AsyncMock
    llm_client = AsyncMock()
    engine = RAGEngine(
        db_url="postgresql://user:pass@localhost/db",
        embedding_provider=dummy_embedding_provider,
        llm_client=llm_client,
    )
    assert engine is not None
    assert engine.embedding_provider is dummy_embedding_provider
    assert engine.llm_client is llm_client


@pytest.mark.asyncio
async def test_generate_delegue_au_client(dummy_embedding_provider, dummy_llm_client):
    """generate() transmet la requête au llm_client injecté."""
    engine = RAGEngine(
        db_url="postgresql://user:pass@localhost/db",
        embedding_provider=dummy_embedding_provider,
        llm_client=dummy_llm_client,
    )
    await engine.generate("query", "system")
    dummy_llm_client.generate.assert_awaited_once()
    args, kwargs = dummy_llm_client.generate.call_args
    # args[0] = full_prompt, args[1] = system_prompt
    assert isinstance(args[0], str)
    assert isinstance(args[1], str)


@pytest.mark.asyncio
async def test_check_llm_health_delegue(dummy_embedding_provider, dummy_llm_client):
    """check_llm_health() transmet au llm_client."""
    engine = RAGEngine(
        db_url="postgresql://user:pass@localhost/db",
        embedding_provider=dummy_embedding_provider,
        llm_client=dummy_llm_client,
    )
    await engine.check_llm_health()
    dummy_llm_client.check_health.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_delegue_si_present(dummy_embedding_provider, dummy_llm_client):
    """close() ferme le llm_client s'il possède une méthode close."""
    engine = RAGEngine(
        db_url="postgresql://user:pass@localhost/db",
        embedding_provider=dummy_embedding_provider,
        llm_client=dummy_llm_client,
    )
    await engine.close()
    dummy_llm_client.close.assert_awaited_once()


def test_aucun_ollama_dans_attributs(dummy_embedding_provider, dummy_llm_client):
    """RAGEngine ne stocke aucun attribut relatif à Ollama."""
    engine = RAGEngine(
        db_url="postgresql://user:pass@localhost/db",
        embedding_provider=dummy_embedding_provider,
        llm_client=dummy_llm_client,
    )
    assert not hasattr(engine, "ollama_host")
    assert not hasattr(engine, "model_name")
    assert not hasattr(engine, "OllamaLLMClient")


def test_llm_client_est_llama_cpp_client(dummy_embedding_provider):
    """Le wiring de dépendances fournit bien un LlamaCppClient."""
    # On utilise la vraie factory pour s'assurer du type
    from api.dependencies import get_llm_client
    # get_llm_client dépend de get_settings_cached() qui nécessite l'env.
    # Pour ce test, on mocke get_settings_cached pour éviter les effets de bord.
    from unittest.mock import patch
    with patch("api.dependencies.get_settings_cached") as mock_get_settings:
        mock_settings = mock_get_settings.return_value
        mock_settings.LLAMA_SERVER_URL = "http://fake:8081"
        mock_settings.LLAMA_TEMPERATURE = 0.3
        mock_settings.LLAMA_TOP_P = 0.9
        mock_settings.LLAMA_TOP_K = 40
        mock_settings.LLAMA_MAX_TOKENS = 1024
        client = get_llm_client()
        assert isinstance(client, LlamaCppClient)
        # nettoyer
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(client.close())

